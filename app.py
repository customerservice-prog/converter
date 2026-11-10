from __future__ import annotations
import logging, os, re, shutil, smtplib, threading, time, uuid, subprocess, json, zipfile, hmac, html, hashlib, secrets
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from urllib.request import Request as HttpRequest, urlopen
from typing import Literal
import yt_dlp
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import FileResponse, Response, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from durable import StateStore, database_path

ROOT=Path(__file__).resolve().parent
MEDIA=Path(os.getenv("MEDIA_DIR","/tmp/converter-media")); MEDIA.mkdir(parents=True,exist_ok=True)
MAX_ACTIVE=max(1,int(os.getenv("MAX_ACTIVE_JOBS","2")))
DAILY_LIMIT=max(100,int(os.getenv("DAILY_LIMIT","120")))
FILE_LIMIT=max(10,int(os.getenv("MAX_FILE_MB","4096")))*1024*1024
TTL=max(300,int(os.getenv("FILE_TTL_SECONDS","3600")))
MAX_UPLOAD_BYTES=max(5,int(os.getenv("MAX_UPLOAD_MB","100")))*1024*1024
UPLOAD_EXTENSIONS={".mp4",".mov",".m4v",".webm",".mkv",".mp3",".m4a",".wav",".flac",".ogg",".aac"}
ID=re.compile(r"^[A-Za-z0-9_-]{11}$")
HOSTS={"youtube.com","www.youtube.com","m.youtube.com","music.youtube.com","youtube-nocookie.com","www.youtube-nocookie.com","youtu.be","www.youtu.be"}
DURATION_LIMIT={"mp3":14400,"mp4":14400}
QUALITIES={"mp3":(0,128,192,320),"mp4":(0,360,720,1080,1440,2160)}
STORE=StateStore(database_path(MEDIA))
jobs=STORE.load("job")
batches=STORE.load("batch")
quota=defaultdict(list,STORE.load("quota"))
contact_quota=defaultdict(list,STORE.load("contact_quota"))
mutex=threading.RLock()
_last_saved={}
MAX_QUEUE_JOBS=max(100,int(os.getenv("MAX_QUEUE_JOBS","128")))
MIN_FREE_MB=max(100,int(os.getenv("MIN_FREE_MB","200")))
MAX_BATCH_LINKS=min(100,max(2,int(os.getenv("MAX_BATCH_LINKS","100"))))
conversion_slots=threading.BoundedSemaphore(MAX_ACTIVE)
log=logging.getLogger("converter")
app=FastAPI(title="Converter API",docs_url=None,redoc_url=None)
app.mount("/assets",StaticFiles(directory=ROOT/"static"),name="assets")

SESSION_SECRET=os.getenv("SESSION_SECRET") or os.getenv("ADMIN_TOKEN") or secrets.token_urlsafe(48)
SESSION_COOKIE="cc_session"


def session_signature(sid:str)->str:
    return hmac.new(SESSION_SECRET.encode(),sid.encode(),hashlib.sha256).hexdigest()[:32]


def verified_session(request:Request)->str|None:
    cookie=request.cookies.get(SESSION_COOKIE,"")
    if len(cookie)>80 or "." not in cookie:return None
    sid,signature=cookie.split(".",1)
    if re.fullmatch(r"[0-9a-f]{32}",sid) and hmac.compare_digest(
        signature,session_signature(sid)):
        return sid
    return None


def client_key(request:Request)->str:
    """Stable, signed anonymous-browser bucket, with IP fallback for API callers."""
    sid=verified_session(request)
    if sid:return "session:"+sid
    return "ip:"+(request.client.host if request.client else "unknown")


def video_id(raw:str)->str:
    raw=(raw or "").strip()
    if len(raw)>2048: raise ValueError("The link is too long.")
    if ID.fullmatch(raw): return raw
    try:
        p=urlparse(raw)
        host=(p.hostname or "").lower().rstrip(".")
        if p.scheme not in ("http","https") or p.username or p.password or p.port:
            raise ValueError("Enter a valid YouTube URL.")
        if host not in HOSTS: raise ValueError("Only YouTube video links are supported.")
        parts=[x for x in p.path.split("/") if x]
        if host in ("youtu.be","www.youtu.be"): found=parts[0] if len(parts)==1 else ""
        elif len(parts)==2 and parts[0] in ("shorts","live","embed","v"): found=parts[1]
        elif p.path in ("/watch","/watch/"): found=parse_qs(p.query).get("v",[""])[0]
        else: found=""
        if not ID.fullmatch(found): raise ValueError("That YouTube video link isn't valid.")
        return found
    except ValueError: raise
    except Exception as exc: raise ValueError("Enter a valid YouTube URL.") from exc

def public(job):
    fields=("id","state","progress","message","title","thumbnail","duration","format","quality","actual_quality","audio_codec","audio_channels","error")
    data={key:job.get(key) for key in fields}
    if job["state"]=="error" and job.get("video_id") and not job.get("batch_id") and int(job.get("retry_count",0))<2:
        data["retry_url"]="/api/jobs/"+job["id"]+"/retry"
    if job["state"] in ("queued","working"):
        waiting=[k for k,v in jobs.items() if v.get("state") in ("queued","working")]
        waiting.sort(key=lambda k: jobs[k].get("created",0))
        data["queue_position"]=waiting.index(job["id"])+1 if job["id"] in waiting else None
    if job["state"]=="ready":
        data["download_url"]="/api/download/"+job["id"]
        data["folder_url"]="/api/download/"+job["id"]+"/folder"
    return data

def save_job(jid,force=False):
    job=jobs.get(jid)
    if not job:return
    now=time.time()
    last=_last_saved.get(jid,0)
    if force or now-last>2:
        STORE.put("job",jid,job)
        _last_saved[jid]=now


def change(jid,**kwargs):
    with mutex:
        if jid in jobs:
            previous=jobs[jid].get("state")
            jobs[jid].update(kwargs)
            current=jobs[jid].get("state")
            if current in ("ready","error") and current!=previous:
                category="converted" if current=="ready" else "failed"
                STORE.increment(category)
                STORE.increment(jobs[jid].get("format","unknown")+"_"+category)
            save_job(jid,force=("state" in kwargs and kwargs["state"]!=previous)
                     or kwargs.get("state") in ("ready","error"))

def cleanup():
    now=time.time()
    with mutex:
        expired=[k for k,j in jobs.items() if j["state"] in ("ready","error") and now-j.get("ended",now)>TTL]
        for k in expired:
            jobs.pop(k,None)
            _last_saved.pop(k,None)
            STORE.drop("job",k)
        expired_batches=[bid for bid,b in batches.items()
            if b["state"] in ("complete","partial","failed") and now-b.get("ended",now)>TTL]
        for bid in expired_batches:
            batches.pop(bid,None)
            STORE.drop("batch",bid)
        for bucket in (quota,contact_quota):
            for ip in list(bucket):
                bucket[ip]=[t for t in bucket[ip] if now-t<86400]
                kind="quota" if bucket is quota else "contact_quota"
                if not bucket[ip]:
                    bucket.pop(ip,None)
                    STORE.drop(kind,ip)
                else:
                    STORE.put(kind,ip,bucket[ip])
    for k in expired: shutil.rmtree(MEDIA/k,ignore_errors=True)
    for bid in expired_batches: shutil.rmtree(MEDIA/("batch-"+bid),ignore_errors=True)
    # Support submissions are private and have a defined retention window.
    STORE.prune("contact",90*86400)


def ensure_disk_space():
    try:
        if shutil.disk_usage(MEDIA).free < MIN_FREE_MB*1024*1024:
            raise HTTPException(503,"Temporary storage is full. Please try again later.")
    except OSError as exc:
        raise HTTPException(503,"Media storage is unavailable.") from exc


def restore_jobs():
    """Resume incomplete jobs after a deploy/restart; preserve completed files."""
    with mutex:
        resume_batches=[]
        standalone=[]
        for jid,j in list(jobs.items()):
            if j.get("state")=="ready" and not Path(j.get("file","/nonexistent")).is_file():
                j.update(state="error",error="File was not retained after restart.",
                         message="Download expired",ended=time.time())
                save_job(jid,True)
            elif j.get("state") in ("working","queued","receiving"):
                if j.get("state")=="receiving":
                    j.update(state="error",error="Upload was interrupted. Please upload again.",
                             message="Upload interrupted",ended=time.time())
                    save_job(jid,True)
                elif not j.get("batch_id"):
                    standalone.append((jid,j))
        for bid,b in batches.items():
            if b.get("state")=="working":
                resume_batches.append(bid)
    for jid,j in standalone:
        vid=j.get("video_id")
        if vid:
            threading.Thread(target=run_queued_conversion,
                args=(jid,vid,j["format"],j["quality"]),daemon=True).start()
        elif j.get("upload_extension") and (MEDIA/jid/("source"+j["upload_extension"])).exists():
            threading.Thread(target=run_queued_upload,
                args=(jid,j["upload_extension"],j.get("title") or "Upload",
                      j["format"],j["quality"]),daemon=True).start()
        else:
            change(jid,state="error",error="Source is no longer available. Please retry.",
                   message="Conversion interrupted",ended=time.time())
    for bid in resume_batches:
        threading.Thread(target=convert_batch,args=(bid,),daemon=True).start()


@app.on_event("startup")
def resume_persistent_jobs():
    cleanup()
    restore_jobs()


def janitor():
    while True:
        time.sleep(300)
        cleanup()
        flush_contact_notifications()

threading.Thread(target=janitor,daemon=True,name="media-cleanup").start()

class ConvertRequest(BaseModel):
    url:str=Field(min_length=1,max_length=2048)
    format:Literal["mp3","mp4"]="mp3"
    quality:int=0
    rights_confirmed:bool=False

class BatchRequest(BaseModel):
    links:list[str]=Field(min_length=2,max_length=MAX_BATCH_LINKS)
    format:Literal["mp3","mp4"]="mp3"
    quality:int=0
    rights_confirmed:bool=False


class ContactRequest(BaseModel):
    name:str=Field(min_length=1,max_length=80)
    email:str=Field(min_length=3,max_length=254)
    message:str=Field(min_length=8,max_length=3000)


class CopyrightRequest(BaseModel):
    name:str=Field(min_length=2,max_length=120)
    email:str=Field(min_length=3,max_length=254)
    work:str=Field(min_length=8,max_length=1200)
    material_url:str=Field(min_length=8,max_length=2048)
    details:str=Field(min_length=8,max_length=3000)
    signature:str=Field(min_length=2,max_length=120)
    good_faith:bool=False
    accuracy:bool=False


class ContactStatusRequest(BaseModel):
    status:Literal["new","reviewed","closed"]

def quality_label(path:Path,fmt:str)->str|None:
    """Report the actual produced file's video height or MP3 bitrate."""
    try:
        probe=subprocess.run(
            ["ffprobe","-v","error","-show_entries","stream=codec_type,height,bit_rate",
             "-of","json",str(path)],capture_output=True,text=True,timeout=20)
        if probe.returncode: return None
        streams=json.loads(probe.stdout).get("streams",[])
        if fmt=="mp4":
            stream=next((s for s in streams if s.get("codec_type")=="video"),None)
            return str(stream["height"])+"p" if stream and stream.get("height") else None
        stream=next((s for s in streams if s.get("codec_type")=="audio"),None)
        bitrate=int((stream or {}).get("bit_rate") or 0)//1000
        return str(bitrate)+" kbps" if bitrate else None
    except (OSError,ValueError,TypeError,subprocess.TimeoutExpired):
        return None



def mp4_audio_info(path:Path)->dict:
    """Inspect real streams, not just the MP4 extension."""
    probe=subprocess.run(
        ["ffprobe","-v","error","-show_entries",
         "stream=codec_type,codec_name,channels,sample_rate",
         "-of","json",str(path)],
        capture_output=True,text=True,timeout=30,check=False)
    if probe.returncode!=0:
        raise ValueError("The video file could not be inspected for sound.")
    streams=json.loads(probe.stdout).get("streams",[])
    if not any(stream.get("codec_type")=="video" for stream in streams):
        raise ValueError("The completed MP4 is missing its video track.")
    audio=next((stream for stream in streams
                if stream.get("codec_type")=="audio" and int(stream.get("channels") or 0)>0),None)
    if not audio:
        raise ValueError("The MP4 has no audio track. Please check whether the source video contains sound.")
    return audio


def ensure_mp4_audio(path:Path)->dict:
    """Make MP4 sound widely compatible without recompressing the video.

    YouTube's highest-quality audio is frequently Opus. Opus in an MP4
    container plays silently on some devices. Preserve 4K video untouched,
    but convert non-AAC or multichannel audio to stereo AAC.
    """
    audio=mp4_audio_info(path)
    codec=audio.get("codec_name")
    channels=int(audio.get("channels") or 0)
    if codec!="aac" or channels>2:
        temp=path.with_name(path.stem+"-aac"+path.suffix)
        try:
            command=["ffmpeg","-nostdin","-hide_banner","-loglevel","error","-y",
                     "-i",str(path),"-map","0:v:0","-map","0:a:0",
                     "-c:v","copy","-c:a","aac","-b:a","256k","-ar","48000",
                     "-ac","2","-movflags","+faststart",str(temp)]
            result=subprocess.run(command,capture_output=True,text=True,timeout=900,check=False)
            if result.returncode!=0 or not temp.is_file() or temp.stat().st_size<1024:
                log.warning("MP4 AAC repair failed: %s",result.stderr[-700:])
                raise ValueError("The video's audio could not be made compatible with MP4.")
            if temp.stat().st_size>FILE_LIMIT:
                raise ValueError("The MP4 exceeds the maximum download size.")
            verified=mp4_audio_info(temp)
            if verified.get("codec_name")!="aac":
                raise ValueError("The audio could not be encoded as AAC.")
            temp.replace(path)
            audio=verified
        finally:
            temp.unlink(missing_ok=True)
    # Decode audio samples to catch corrupt or unreadable audio tracks,
    # without decoding/re-encoding the video stream.
    playback=subprocess.run(
        ["ffmpeg","-nostdin","-hide_banner","-v","error","-xerror",
         "-i",str(path),"-map","0:a:0","-t","3","-f","null","-"],
        stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True,
        timeout=45,check=False)
    if playback.returncode!=0:
        raise ValueError("The MP4 audio track could not be decoded correctly.")
    return {"audio_codec":"aac","audio_channels":int(audio.get("channels") or 2)}


def youtube_output_options(fmt:str,quality:int)->dict:
    """Pick best available streams for Auto (0), or enforce a user-selected cap."""
    if fmt=="mp3":
        bitrate=320 if quality==0 else quality
        return {"format":"bestaudio/best",
                "postprocessors":[{"key":"FFmpegExtractAudio",
                                   "preferredcodec":"mp3",
                                   "preferredquality":str(bitrate)}]}
    if quality==0:
        # Match yt-dlp's default best-video-plus-best-audio selection.
        # No height cap: may select 1440p, 2160p, or higher source video.
        return {"format":"bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
                "format_sort":["res","fps","hdr:12","vcodec","acodec"],
                "merge_output_format":"mp4"}
    cap=str(quality)
    return {"format":("bestvideo[ext=mp4][height<="+cap+"]+bestaudio[ext=m4a]/"
                      "bestvideo[height<="+cap+"]+bestaudio/"
                      "best[height<="+cap+"]"),
            "merge_output_format":"mp4"}



def youtube_access_challenge(exc:Exception)->bool:
    """Only retry another public client/network family for access challenges."""
    reason=str(exc).lower()
    return any(term in reason for term in (
        "sign in to confirm", "not a bot", "bot verification",
        "this app is not supported", "not available on this app",
        "http error 429", "too many requests"))


def fetch_public_video_info(url:str,opts:dict,fmt:str,quality:int,notify=None)->tuple[dict,dict]:
    """Resolve a public YouTube video with bounded, ordinary client fallbacks.

    The first attempt preserves Railway's previously successful IPv6 address.
    If both public playback clients reject that address, try IPv4, where it is
    available. Never use cookies, account credentials, paid proxies or tokens.
    """
    preferred=opts.get("source_address","0.0.0.0")
    other="0.0.0.0" if preferred=="::" else "::"
    addresses=[preferred]
    if os.getenv("YOUTUBE_IP_FALLBACK","1")=="1":
        addresses.append(other)
    # Avoid rapid requests that may trigger extra rate limiting.
    profiles=(None,("tv","web_safari"))
    last_error=None
    for address in addresses:
        for clients in profiles:
            check_opts={**opts,**youtube_output_options(fmt,quality),
                        "source_address":address}
            check_opts.pop("extractor_args",None)
            if clients:
                check_opts["extractor_args"]={
                    "youtube":{"player_client":list(clients)}}
            try:
                if notify:
                    notify("Checking available video formats…")
                with yt_dlp.YoutubeDL(check_opts) as extractor:
                    info=extractor.extract_info(url,download=False)
                if not info:
                    raise ValueError("No usable video metadata was returned.")
                final_opts={"source_address":address}
                if clients:
                    final_opts["extractor_args"]={
                        "youtube":{"player_client":list(clients)}}
                return info,final_opts
            except yt_dlp.utils.DownloadError as exc:
                if not youtube_access_challenge(exc):
                    raise
                last_error=exc
                # No specific URL or account data is added to public logs.
                log.info("YouTube public playback challenged; address_family=%s profile=%s",
                         "ipv6" if address=="::" else "ipv4",
                         "alternate" if clients else "default")
                if clients:
                    time.sleep(1)
    if last_error:
        raise last_error
    raise ValueError("Could not retrieve public video information.")


def convert(jid,vid,fmt,quality):
    directory=MEDIA/jid; directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    url="https://www.youtube.com/watch?v="+vid
    try:
        change(jid,state="working",progress=3,message="Checking video…")
        opts={"source_address":"::" if os.getenv("PREFER_IPV6")=="1" else "0.0.0.0","js_runtimes":{"node":{}},"quiet":True,"no_warnings":True,"noplaylist":True,"ignoreerrors":False,
              "cachedir":False,"socket_timeout":20,"retries":2,"fragment_retries":2,
              "concurrent_fragment_downloads":min(8,max(1,int(os.getenv("DOWNLOAD_FRAGMENTS","6")))),
              "outtmpl":str(directory/"%(id)s.%(ext)s"),"restrictfilenames":True}
        # Resolve once, fall back to the other IP family only when the
        # preferred public access path is challenged by YouTube.
        info,access_opts=fetch_public_video_info(
            url,opts,fmt,quality,
            notify=lambda message:change(jid,message=message))
        opts.update(access_opts)
        if not info or info.get("is_live") or info.get("live_status") in ("is_live","is_upcoming"):
            raise ValueError("Live videos can only be converted after they end.")
        duration=info.get("duration")
        if not isinstance(duration,(int,float)) or duration<=0:
            raise ValueError("Video duration could not be verified.")
        if duration>DURATION_LIMIT[fmt]:
            raise ValueError("The maximum "+fmt.upper()+" video length is "+str(DURATION_LIMIT[fmt]//60)+" minutes.")
        change(jid,title=str(info.get("title") or "YouTube video")[:180],
               thumbnail="https://i.ytimg.com/vi/"+vid+"/hqdefault.jpg",
               duration=int(duration),progress=10,message="Preparing conversion…")
        def progress(x):
            if x.get("status")=="downloading":
                downloaded=x.get("downloaded_bytes") or 0
                if downloaded>FILE_LIMIT: raise ValueError("Source file is too large.")
                total=x.get("total_bytes") or x.get("total_bytes_estimate") or 0
                percent=min(88,10+int(75*downloaded/total)) if total else 35
                change(jid,progress=percent,message="Downloading media…")
            elif x.get("status")=="finished":
                change(jid,progress=89,message="Download complete. Preparing media…")
        def postprocess_progress(x):
            if x.get("status")=="started":
                change(jid,progress=90,message="Merging video and audio…")
            elif x.get("status")=="finished":
                change(jid,progress=94,message="Verifying finished media…")
        options={**opts,"progress_hooks":[progress],
                 "postprocessor_hooks":[postprocess_progress],
                 **youtube_output_options(fmt,quality)}
        # process_info downloads the selected formats without repeating extraction.
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.process_info(info)
        files=sorted(directory.glob("*."+fmt))
        if not files: raise ValueError("No compatible output is available for this video.")
        if files[0].stat().st_size>FILE_LIMIT: raise ValueError("Converted file is too large.")
        change(jid,progress=96,message="Checking audio compatibility…")
        audio_meta=ensure_mp4_audio(files[0]) if fmt=="mp4" else {}
        change(jid,state="ready",progress=100,message="Ready to download",file=str(files[0]),
               actual_quality=quality_label(files[0],fmt),**audio_meta,ended=time.time())
    except Exception as exc:
        log.warning("Job %s failed: %s",jid,type(exc).__name__)
        text=str(exc).lower()
        if youtube_access_challenge(exc):
            msg=("YouTube is requiring sign-in verification from this server. "
                 "This link cannot be converted here right now. If you have the media file, "
                 "choose Upload File to convert it instead.")
        else:
            msg=str(exc) if isinstance(exc,ValueError) else "Conversion failed. This video may be restricted or temporarily unavailable."
        change(jid,state="error",progress=0,message="Conversion failed",error=msg,ended=time.time())
        shutil.rmtree(directory,ignore_errors=True)

@app.middleware("http")
async def headers(request:Request,call_next):
    # Reject oversized browser uploads before Starlette parses/spools the
    # multipart payload. Enforce actual bytes again inside the upload handler.
    if request.url.path=="/api/upload" and request.method=="POST":
        raw=request.headers.get("content-length","")
        if raw.isdecimal() and int(raw)>MAX_UPLOAD_BYTES+1048576:
            return Response('{"detail":"Upload exceeds the 100 MB limit."}',
                            status_code=413,media_type="application/json",
                            headers={"Cache-Control":"no-store"})
    result=await call_next(request)
    result.headers["X-Content-Type-Options"]="nosniff"
    result.headers["X-Frame-Options"]="DENY"
    result.headers["Referrer-Policy"]="strict-origin-when-cross-origin"
    result.headers["Permissions-Policy"]="camera=(),microphone=(),geolocation=()"
    result.headers["Content-Security-Policy"]="frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'"
    if request.url.scheme=="https" or os.getenv("SITE_URL","").startswith("https://"):
        result.headers["Strict-Transport-Security"]="max-age=31536000"
    if request.url.path.startswith(("/api/","/admin")):
        result.headers["X-Robots-Tag"]="noindex, nofollow"
    if request.method=="GET" and not request.url.path.startswith(("/api/","/assets/","/admin")):
        if not verified_session(request):
            sid=uuid.uuid4().hex
            cookie=sid+"."+session_signature(sid)
            result.set_cookie(SESSION_COOKIE,cookie,max_age=86400*30,httponly=True,
                              secure=os.getenv("SITE_URL","").startswith("https://"),
                              samesite="lax")
    if request.url.path.startswith("/api/"): result.headers["Cache-Control"]="no-store"
    return result

@app.get("/api/health")
def health():
    return {"status":"ok","ffmpeg":bool(shutil.which("ffmpeg")),
            "storage_ready":STORE.path.is_file(),
            "storage_free_mb":round(shutil.disk_usage(MEDIA).free/1024/1024),
            "yt_dlp":yt_dlp.version.__version__,
            "youtube_ip_fallback":os.getenv("YOUTUBE_IP_FALLBACK","1")=="1",
            "features":["upload","youtube","thumbnail","best_quality_auto",
                        "organized_folders","parallel_fragments","batch_links",
                        "aac_mp4_audio","durable_jobs","contact_inbox","retry"]}


def run_queued_conversion(jid:str,vid:str,fmt:str,quality:int)->None:
    # Shared slots keep individual and batch jobs within the same CPU limit.
    with conversion_slots:
        convert(jid,vid,fmt,quality)


def run_queued_upload(jid:str,extension:str,name:str,fmt:str,quality:int)->None:
    with conversion_slots:
        convert_upload(jid,extension,name,fmt,quality)


def public_batch(batch:dict)->dict:
    with mutex:
        items=[public(jobs[jid]) for jid in batch["job_ids"] if jid in jobs]
        done=sum(i["state"] in ("ready","error") for i in items)
        successes=sum(i["state"]=="ready" for i in items)
        result={"id":batch["id"],"state":batch["state"],"format":batch["format"],
                "quality":batch["quality"],"total":len(batch["job_ids"]),
                "processed":done,"succeeded":successes,"failed":sum(i["state"]=="error" for i in items),
                "items":items,"message":batch.get("message",""),
                "download_url":None}
        if batch["state"] in ("complete","partial") and successes:
            result["download_url"]="/api/batches/"+batch["id"]+"/download"
        return result


def convert_batch(batch_id:str)->None:
    """Process a bounded batch, preserving individual job and failure status."""
    with mutex:
        batch=batches.get(batch_id)
        if not batch:return
        batch["state"]="working"
        STORE.put("batch",batch_id,batch)
        ids=list(batch["job_ids"])
        fmt=batch["format"]
        quality=batch["quality"]
        pairs=[(jid,jobs[jid]["video_id"]) for jid in ids
               if jid in jobs and jobs[jid]["state"]!="ready" and jobs[jid]["state"]!="error"]
    try:
        with ThreadPoolExecutor(max_workers=min(2,MAX_ACTIVE),thread_name_prefix="clip-batch") as executor:
            futures=[executor.submit(run_queued_conversion,jid,vid,fmt,quality)
                     for jid,vid in pairs]
            for future in as_completed(futures):
                future.result()
    except Exception:
        log.exception("Batch conversion crashed")
    finally:
        with mutex:
            now=time.time()
            batch=batches.get(batch_id)
            if not batch:return
            for jid in ids:
                item=jobs.get(jid)
                if item:
                    if item["state"] not in ("ready","error"):
                        item.update(state="error",error="This conversion stopped unexpectedly.",
                                    progress=0,message="Conversion failed")
                    item["ended"]=now
                    save_job(jid,True)
            success=sum(jobs[jid]["state"]=="ready" for jid in ids if jid in jobs)
            batch["state"]="complete" if success==len(ids) else "partial" if success else "failed"
            batch["ended"]=now
            batch["message"]=f"{success} of {len(ids)} videos converted"
            STORE.put("batch",batch_id,batch)


@app.post("/api/batches",status_code=202)
def create_batch(payload:BatchRequest,request:Request):
    if not payload.rights_confirmed:
        raise HTTPException(400,"Confirm you have permission to download all videos in this batch.")
    if payload.quality not in QUALITIES[payload.format]:
        raise HTTPException(400,"Choose a supported quality.")
    # Reject invalid inputs atomically and deduplicate identical video IDs.
    ids=[]
    for link in payload.links:
        try: vid=video_id(link)
        except ValueError as exc: raise HTTPException(400,str(exc)) from exc
        if vid not in ids: ids.append(vid)
    if len(ids)<2:
        raise HTTPException(400,"Add at least two different YouTube videos.")
    cleanup()
    ensure_disk_space()
    ip=client_key(request)
    now=time.time()
    with mutex:
        if len(quota[ip])+len(ids)>DAILY_LIMIT:
            raise HTTPException(429,"The batch exceeds the remaining daily conversion limit.")
        waiting=sum(j["state"] in ("queued","working","receiving") for j in jobs.values())
        if waiting+len(ids)>MAX_QUEUE_JOBS:
            raise HTTPException(503,"The queue is full. Please try again shortly.")
        bid=uuid.uuid4().hex
        jids=[]
        for vid in ids:
            jid=uuid.uuid4().hex
            jids.append(jid)
            jobs[jid]={"id":jid,"state":"queued","progress":0,"message":"Waiting in batch…",
                       "title":"YouTube video","video_id":vid,
                       "thumbnail":"https://i.ytimg.com/vi/"+vid+"/hqdefault.jpg",
                       "duration":None,"format":payload.format,"quality":payload.quality,
                       "actual_quality":None,"error":None,"created":now,"batch_id":bid}
        quota[ip].extend([now]*len(ids))
        STORE.put("quota",ip,quota[ip])
        for jid in jids:save_job(jid,True)
        batches[bid]={"id":bid,"state":"working","created":now,
                      "message":"Preparing batch…","job_ids":jids,
                      "format":payload.format,"quality":payload.quality}
        STORE.put("batch",bid,batches[bid])
    threading.Thread(target=convert_batch,args=(bid,),daemon=True,
                     name="batch-"+bid[:8]).start()
    return public_batch(batches[bid])


@app.get("/api/batches/{bid}")
def get_batch(bid:str):
    cleanup()
    with mutex:
        batch=batches.get(bid)
        if not batch: raise HTTPException(404,"This batch has expired or does not exist.")
        return public_batch(batch)


@app.post("/api/jobs/{jid}/retry",status_code=202)
def retry_job(jid:str):
    with mutex:
        j=jobs.get(jid)
        if not j: raise HTTPException(404,"This conversion has expired.")
        if j.get("batch_id"):
            raise HTTPException(400,"Use Retry failed videos on the batch instead.")
        if j["state"]!="error":
            raise HTTPException(409,"Only failed jobs can be retried.")
        if not j.get("video_id"):
            raise HTTPException(400,"Upload an original media file again to retry.")
        if int(j.get("retry_count",0))>=2:
            raise HTTPException(429,"This video reached its retry limit.")
        if sum(x["state"] in ("queued","working","receiving") for x in jobs.values())>=MAX_QUEUE_JOBS:
            raise HTTPException(503,"The conversion queue is full.")
        j.update(state="queued",progress=0,error=None,
                 retry_count=int(j.get("retry_count",0))+1,
                 message="Retry queued…",ended=None)
        save_job(jid,True)
    threading.Thread(target=run_queued_conversion,
        args=(jid,j["video_id"],j["format"],j["quality"]),daemon=True).start()
    return public(j)


@app.post("/api/batches/{bid}/retry",status_code=202)
def retry_batch(bid:str):
    with mutex:
        b=batches.get(bid)
        if not b: raise HTTPException(404,"This batch has expired.")
        if b["state"] not in ("failed","partial"):
            raise HTTPException(409,"Only completed batches with failures can be retried.")
        items=[jobs[jid] for jid in b["job_ids"] if jid in jobs and jobs[jid]["state"]=="error"
               and int(jobs[jid].get("retry_count",0))<2]
        if not items:
            raise HTTPException(409,"No retryable failed videos remain.")
        waiting=sum(j["state"] in ("queued","working","receiving") for j in jobs.values())
        if waiting+len(items)>MAX_QUEUE_JOBS:
            raise HTTPException(503,"The queue is full.")
        for item in items:
            item.update(state="queued",progress=0,error=None,ended=None,
                        retry_count=int(item.get("retry_count",0))+1,
                        message="Retry queued…")
            save_job(item["id"],True)
        b.update(state="working",message="Retrying failed videos…",ended=None)
        STORE.put("batch",bid,b)
        # A previous partial ZIP must not be reused once new items complete.
        (MEDIA/("batch-"+bid)/"all-videos.zip").unlink(missing_ok=True)
    threading.Thread(target=convert_batch,args=(bid,),daemon=True).start()
    return public_batch(b)


@app.get("/api/batches/{bid}/download")
def download_batch(bid:str):
    cleanup()
    with mutex:
        batch=batches.get(bid)
        if not batch or batch["state"] not in ("complete","partial"):
            raise HTTPException(404,"The batch archive is not ready or has expired.")
        items=[jobs[jid] for jid in batch["job_ids"] if jid in jobs]
        ready=[(index,j) for index,j in enumerate(items,1)
               if j["state"]=="ready" and Path(j["file"]).is_file()]
        if not ready: raise HTTPException(404,"No completed files are available.")
        folder=MEDIA/("batch-"+bid)
        folder.mkdir(mode=0o700,parents=True,exist_ok=True)
        archive=folder/"all-videos.zip"
        if not archive.exists():
            temporary=folder/("build-"+uuid.uuid4().hex+".tmp")
            try:
                lines=[f"Batch results: {len(ready)} of {len(items)} videos ready",""]
                with zipfile.ZipFile(temporary,"w",compression=zipfile.ZIP_STORED,
                                     allowZip64=True) as z:
                    for index,job in enumerate(items,1):
                        title=safe_media_name(job.get("title") or "YouTube video")
                        if job["state"]=="ready" and Path(job["file"]).is_file():
                            dirname=f"{index:02d} - {title}"
                            media=Path(job["file"])
                            z.write(media,arcname=f"{dirname}/{title}.{job['format']}")
                            detail=(f"Title: {job.get('title') or 'YouTube video'}\n"
                                    f"Format: {job['format'].upper()}\n"
                                    f"Quality: {job.get('actual_quality') or 'Unknown'}\n"
                                    f"Source: https://www.youtube.com/watch?v={job['video_id']}\n")
                            z.writestr(f"{dirname}/Video Info.txt",detail)
                            lines.append(f"{index:02d}. OK — {job.get('title') or title}")
                        else:
                            lines.append(f"{index:02d}. FAILED — {job.get('title') or title}: {job.get('error') or 'File unavailable'}")
                    z.writestr("Batch Results.txt","\n".join(lines)+"\n")
                temporary.replace(archive)
            except Exception:
                temporary.unlink(missing_ok=True)
                raise
    return FileResponse(archive,media_type="application/zip",
                        filename="ClipConvert-"+bid[:8]+"-all-videos.zip")


@app.post("/api/jobs",status_code=202)
def create(payload:ConvertRequest,request:Request):
    if not payload.rights_confirmed: raise HTTPException(400,"Confirm that you have permission to download this media.")
    try: vid=video_id(payload.url)
    except ValueError as exc: raise HTTPException(400,str(exc)) from exc
    if payload.quality not in QUALITIES[payload.format]: raise HTTPException(400,"Unsupported format quality.")
    cleanup()
    ensure_disk_space()
    now=time.time(); ip=client_key(request)
    with mutex:
        if sum(j["state"] in ("receiving","queued","working") for j in jobs.values())>=MAX_QUEUE_JOBS:
            raise HTTPException(503,"The converter is busy. Please try again.")
        if len(quota[ip])>=DAILY_LIMIT: raise HTTPException(429,"Daily download limit reached.")
        quota[ip].append(now); jid=uuid.uuid4().hex
        job={"id":jid,"state":"queued","progress":0,"message":"Starting…","title":"YouTube video",
             "thumbnail":"https://i.ytimg.com/vi/"+vid+"/hqdefault.jpg","video_id":vid,"duration":None,"format":payload.format,"quality":payload.quality,"actual_quality":None,
             "error":None,"created":now}
        jobs[jid]=job
        STORE.put("quota",ip,quota[ip])
        save_job(jid,True)
    threading.Thread(target=run_queued_conversion,args=(jid,vid,payload.format,payload.quality),daemon=True).start()
    return public(job)

def convert_upload(jid: str, extension: str, name: str, fmt: str, quality: int) -> None:
    folder=MEDIA/jid
    source=folder/("source"+extension)
    output=folder/("converted."+fmt)
    try:
        change(jid,state="working",progress=8,message="Checking uploaded media…")
        probe=subprocess.run(
            ["ffprobe","-v","error","-show_entries","format=duration:stream=codec_type,codec_name,height",
             "-of","json",str(source)],capture_output=True,text=True,timeout=30,check=False)
        if probe.returncode != 0:
            raise ValueError("The uploaded file is not valid media or cannot be read.")
        try:
            metadata=json.loads(probe.stdout)
            duration=float(metadata.get("format",{}).get("duration","0"))
            streams=metadata.get("streams",[])
        except (ValueError,TypeError,KeyError) as exc:
            raise ValueError("Unable to read this file's media properties.") from exc
        if not 0 < duration <= DURATION_LIMIT[fmt]:
            raise ValueError("The maximum "+fmt.upper()+" duration is "+str(DURATION_LIMIT[fmt]//60)+" minutes.")
        has_audio=any(x.get("codec_type")=="audio" for x in streams)
        has_video=any(x.get("codec_type")=="video" for x in streams)
        if fmt=="mp3" and not has_audio:
            raise ValueError("This file has no audio track to convert.")
        if fmt=="mp4" and not has_video:
            raise ValueError("An MP4 video requires a source file with a video track.")
        change(jid,title=name,duration=int(duration),progress=15,message="Converting uploaded file…")
        cmd=["ffmpeg","-hide_banner","-nostdin","-loglevel","error",
             "-nostats","-progress","pipe:1","-y","-i",str(source)]
        if fmt=="mp3":
            cmd+=["-map","0:a:0","-vn","-c:a","libmp3lame","-b:a",str(320 if quality==0 else quality)+"k"]
        else:
            # Auto preserves compatible H.264/AAC or HEVC/AAC sources without
            # losing quality. Other codecs are converted at high quality,
            # retaining the full source resolution (no automatic downscale).
            video=next((s for s in streams if s.get("codec_type")=="video"),{})
            audio=next((s for s in streams if s.get("codec_type")=="audio"),{})
            can_copy=(quality==0 and video.get("codec_name") in ("h264","hevc")
                      and (not has_audio or audio.get("codec_name")=="aac"))
            cmd+=["-map","0:v:0","-map","0:a:0?"]
            if can_copy:
                cmd+=["-c:v","copy","-c:a","copy"]
            else:
                if quality!=0:
                    cmd+=["-vf","scale=-2:min(ih\\,"+str(quality)+")"]
                cmd+=["-c:v","libx264","-preset","veryfast",
                      "-crf","18" if quality==0 else "23","-pix_fmt","yuv420p",
                      "-c:a","aac","-b:a","256k" if quality==0 else "128k"]
            cmd+=["-movflags","+faststart"]
        cmd += [str(output)]
        timeout=max(120,min(21600,int(duration*5)))
        error_lines=[]
        with subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                              text=True,bufsize=1) as process:
            timer=threading.Timer(timeout,process.kill)
            timer.daemon=True
            timer.start()
            try:
                for line in process.stdout:
                    line=line.strip()
                    if line.startswith(("out_time_us=","out_time_ms=")):
                        try:
                            seconds=float(line.split("=",1)[1])/1_000_000
                            change(jid,progress=min(95,15+int(80*seconds/duration)))
                        except (ValueError,ZeroDivisionError):
                            pass
                    elif line and len(error_lines)<20:
                        error_lines.append(line[:250])
                    if output.exists() and output.stat().st_size>FILE_LIMIT:
                        process.kill()
                        raise ValueError("Converted file exceeds the maximum permitted size.")
                code=process.wait()
            finally:
                timer.cancel()
        if code!=0 or not output.is_file() or output.stat().st_size<1024:
            log.warning("Local media conversion failed for job %s: %s",jid," | ".join(error_lines)[-1000:])
            raise ValueError("FFmpeg could not convert this file. Check the media or try another format.")
        if output.stat().st_size>FILE_LIMIT:
            raise ValueError("Converted file exceeds the maximum permitted size.")
        audio_meta=ensure_mp4_audio(output) if fmt=="mp4" else {}
        source.unlink(missing_ok=True)
        change(jid,state="ready",progress=100,message="Ready to download",
               file=str(output),actual_quality=quality_label(output,fmt),
               **audio_meta,ended=time.time())
    except Exception as exc:
        log.warning("Uploaded media conversion %s failed (%s)",jid,type(exc).__name__)
        change(jid,state="error",progress=0,message="Conversion failed",
               error=str(exc) if isinstance(exc,ValueError) else "Could not convert this file.",
               ended=time.time())
        shutil.rmtree(folder,ignore_errors=True)


@app.post("/api/upload",status_code=202)
async def upload_media(
    request: Request,
    file: UploadFile = File(...),
    format: Literal["mp3","mp4"] = Form(...),
    quality: int = Form(0),
    rights_confirmed: bool = Form(False),
):
    if not rights_confirmed:
        raise HTTPException(400,"Confirm that you have permission to use this media.")
    if quality not in QUALITIES[format]:
        raise HTTPException(400,"Choose a supported format and quality.")
    name=Path(file.filename or "").name
    extension=Path(name).suffix.lower()
    if extension not in UPLOAD_EXTENSIONS:
        raise HTTPException(400,"Upload an MP4, MOV, WEBM, MKV, MP3, M4A, WAV, FLAC, OGG or AAC file.")
    length=request.headers.get("content-length","")
    if length.isdecimal() and int(length)>MAX_UPLOAD_BYTES+1048576:
        raise HTTPException(413,"The file is too large. Upload up to "+str(MAX_UPLOAD_BYTES//1048576)+" MB.")
    cleanup()
    ensure_disk_space()
    ip=client_key(request)
    now=time.time()
    with mutex:
        if sum(j["state"] in ("receiving","queued","working") for j in jobs.values())>=MAX_QUEUE_JOBS:
            raise HTTPException(503,"All converters are busy. Please try again.")
        if len(quota[ip])>=DAILY_LIMIT:
            raise HTTPException(429,"Daily conversion limit reached.")
        jid=uuid.uuid4().hex
        quota[ip].append(now)
        jobs[jid]={"id":jid,"state":"receiving","progress":1,
                   "message":"Receiving file…","title":Path(name).stem[:100] or "Uploaded media",
                   "thumbnail":None,"duration":None,"format":format,"quality":quality,"actual_quality":None,
                   "error":None,"created":now,"upload_extension":extension}
        STORE.put("quota",ip,quota[ip])
        save_job(jid,True)
    folder=MEDIA/jid
    folder.mkdir(mode=0o700,parents=True,exist_ok=True)
    source=folder/("source"+extension)
    size=0
    try:
        with source.open("wb") as dst:
            while True:
                chunk=await file.read(1024*1024)
                if not chunk: break
                size+=len(chunk)
                if size>MAX_UPLOAD_BYTES:
                    raise HTTPException(413,"The file exceeds the "+str(MAX_UPLOAD_BYTES//1048576)+" MB limit.")
                dst.write(chunk)
        if size<1024: raise HTTPException(400,"This media file is empty.")
    except Exception:
        with mutex:
            jobs.pop(jid,None)
            STORE.drop("job",jid)
        shutil.rmtree(folder,ignore_errors=True)
        raise
    finally:
        await file.close()
    change(jid,state="queued",progress=5,message="Processing upload…")
    thread=threading.Thread(target=run_queued_upload,
        args=(jid,extension,Path(name).stem[:100] or "Uploaded media",format,quality),daemon=True)
    thread.start()
    return public(jobs[jid])


@app.get("/api/jobs/{jid}")
def get_job(jid:str):
    cleanup()
    with mutex:
        if jid not in jobs: raise HTTPException(404,"This conversion has expired.")
        return public(jobs[jid])

@app.get("/api/download/{jid}")
def download(jid:str):
    cleanup()
    with mutex:
        job=jobs.get(jid)
        if not job or job["state"]!="ready": raise HTTPException(404,"The download is no longer available.")
        file=Path(job["file"]); title=job.get("title") or "download"
        name=(re.sub(r"[^a-zA-Z0-9._ -]","",title).strip()[:90] or "download")+"."+job["format"]
    if not file.is_file(): raise HTTPException(404,"The file is no longer available.")
    return FileResponse(file,media_type="audio/mpeg" if job["format"]=="mp3" else "video/mp4",filename=name)


def safe_media_name(value:str)->str:
    """Cross-platform filename that cannot create ZIP path traversal entries."""
    name=re.sub(r'[<>:"/\\|?*\x00-\x1f]',"_",str(value or ""))
    name=re.sub(r"\s+"," ",name).strip(" .")[:90]
    return name or "Video"


@app.get("/api/download/{jid}/folder")
def download_folder(jid:str):
    """One ZIP per video containing a named folder and the unmodified output."""
    cleanup()
    with mutex:
        job=jobs.get(jid)
        if not job or job["state"]!="ready":
            raise HTTPException(404,"The folder download has expired.")
        media=Path(job["file"])
        title=safe_media_name(job.get("title") or "Video")
        ext=job["format"]
        quality=job.get("actual_quality") or "Unknown"
        vid=job.get("video_id")
        jobdir=MEDIA/jid
        archive=jobdir/"organized.zip"
        folder=title+" - "+jid[:8]
        if not media.is_file():
            raise HTTPException(404,"The converted media is no longer available.")
        if not archive.is_file():
            temporary=jobdir/("organized-"+uuid.uuid4().hex+".tmp")
            try:
                details=(
                    f"Title: {job.get('title') or 'Video'}\n"
                    f"Format: {ext.upper()}\n"
                    f"Actual quality: {quality}\n"
                    f"Source: {'https://www.youtube.com/watch?v='+vid if vid else 'Uploaded media'}\n"
                    "Created by ClipConvert\n"
                )
                with zipfile.ZipFile(temporary,"w",compression=zipfile.ZIP_STORED,
                                     allowZip64=True) as z:
                    z.write(media,arcname=f"{folder}/{title}.{ext}")
                    z.writestr(f"{folder}/Video Info.txt",details)
                temporary.replace(archive)
            except Exception:
                temporary.unlink(missing_ok=True)
                raise
    return FileResponse(archive,media_type="application/zip",filename=folder+".zip")


@app.get("/api/thumbnail/{vid}")
def thumbnail(vid:str):
    if not ID.fullmatch(vid): raise HTTPException(400,"Invalid video ID.")
    try:
        req=HttpRequest("https://i.ytimg.com/vi/"+vid+"/hqdefault.jpg",headers={"User-Agent":"Converter/1.0"})
        with urlopen(req,timeout=10) as res:
            if res.headers.get("Content-Type","").split(";")[0]!="image/jpeg":
                raise ValueError("Not an image")
            data=res.read(3_000_001)
        if len(data)>3_000_000: raise ValueError("Image too large")
        return Response(data,media_type="image/jpeg",headers={"Content-Disposition":'attachment; filename="'+vid+'.jpg"'})
    except Exception as exc: raise HTTPException(502,"Could not retrieve the thumbnail.") from exc

def require_admin(request:Request):
    expected=os.getenv("ADMIN_TOKEN","")
    received=request.headers.get("X-Admin-Token","")
    if not expected:
        raise HTTPException(503,"Admin access is not configured.")
    if not received or not hmac.compare_digest(received,expected):
        raise HTTPException(401,"Invalid admin token.")


@app.get("/api/admin/contacts")
def admin_contacts(request:Request):
    require_admin(request)
    return {"messages":STORE.messages(100)}


@app.patch("/api/admin/contacts/{message_id}")
def admin_update_contact(message_id:str,payload:ContactStatusRequest,request:Request):
    require_admin(request)
    if not re.fullmatch(r"[a-f0-9]{32}",message_id):
        raise HTTPException(400,"Invalid message ID.")
    existing=STORE.load("contact").get(message_id)
    if not existing:
        raise HTTPException(404,"Contact request not found.")
    existing["status"]=payload.status
    existing["updated"]=time.time()
    STORE.put("contact",message_id,existing)
    return {"updated":True,"status":payload.status}


@app.delete("/api/admin/contacts/{message_id}")
def admin_delete_contact(message_id:str,request:Request):
    require_admin(request)
    if not re.fullmatch(r"[a-f0-9]{32}",message_id):
        raise HTTPException(400,"Invalid message ID.")
    STORE.drop("contact",message_id)
    return {"deleted":True}


@app.get("/api/admin/overview")
def admin_overview(request:Request):
    require_admin(request)
    with mutex:
        states={state:sum(j.get("state")==state for j in jobs.values())
                for state in ("queued","working","ready","error","receiving")}
        disk=shutil.disk_usage(MEDIA)
        return {"jobs":states,"batches":len(batches),
                "disk_free_mb":round(disk.free/1024/1024),
                "disk_used_mb":round(disk.used/1024/1024),
                "contact_messages":len(STORE.messages(200)),
                "unread_contacts":sum(m.get("status","new")=="new" for m in STORE.messages(200)),
                "email_notifications_configured":mail_configured(),
                "durable":True,"max_active":MAX_ACTIVE,"max_queued":MAX_QUEUE_JOBS}


@app.get("/api/admin/analytics")
def admin_analytics(request:Request):
    require_admin(request)
    return {"timezone":"UTC","daily":STORE.daily_summary(14)}


CONTACT_DELIVERY_LOCK=threading.Lock()


def mail_configured()->bool:
    if not all(os.getenv(k) for k in ("CONTACT_EMAIL","SMTP_HOST","SMTP_FROM")):
        return False
    return not os.getenv("SMTP_USER") or bool(os.getenv("SMTP_PASSWORD"))


def deliver_message(msg_id:str,record:dict)->bool:
    """Send a stored support notification, only through a configured dedicated sender."""
    if not mail_configured(): return False
    from_addr=os.environ["SMTP_FROM"]
    to_addr=os.environ["CONTACT_EMAIL"]
    email=EmailMessage()
    category=record.get("category","support")
    email["Subject"]="ClipConvert "+("copyright report" if category=="copyright" else "support")+" "+msg_id[:8]
    email["From"]=from_addr
    email["To"]=to_addr
    email["Reply-To"]=record.get("email","")
    email.set_content(
        "Reference: "+msg_id[:8]+"\nCategory: "+category+"\n"
        "Name: "+record.get("name","")+"\n"
        "Email: "+record.get("email","")+"\n\n"
        +record.get("message",""))
    port=int(os.getenv("SMTP_PORT","587"))
    if port==465:
        with smtplib.SMTP_SSL(os.environ["SMTP_HOST"],port,timeout=12) as client:
            if os.getenv("SMTP_USER"):
                client.login(os.environ["SMTP_USER"],os.getenv("SMTP_PASSWORD",""))
            client.send_message(email)
    else:
        with smtplib.SMTP(os.environ["SMTP_HOST"],port,timeout=12) as client:
            client.starttls()
            if os.getenv("SMTP_USER"):
                client.login(os.environ["SMTP_USER"],os.getenv("SMTP_PASSWORD",""))
            client.send_message(email)
    return True


def flush_contact_notifications():
    """Recover failed notifications after SMTP outages and future configuration."""
    if not mail_configured() or not CONTACT_DELIVERY_LOCK.acquire(blocking=False):
        return
    try:
        now=time.time()
        messages=STORE.load("contact")
        pending=sorted(((key,value) for key,value in messages.items()
                        if not value.get("emailed")),key=lambda kv:kv[1].get("created",0))
        for key,record in pending[:10]:
            # Exponential backoff; no repeat notifications for successfully sent mail.
            attempts=int(record.get("notification_attempts",0))
            last=float(record.get("last_notification_attempt",0))
            if last and now-last<min(86400,60*2**min(attempts,10)):
                continue
            record["notification_attempts"]=attempts+1
            record["last_notification_attempt"]=now
            STORE.put("contact",key,record)
            try:
                if deliver_message(key,record):
                    record["emailed"]=True
                    record["emailed_at"]=time.time()
                    STORE.put("contact",key,record)
            except Exception:
                log.warning("Support notification delivery was unavailable; retained for retry")
    finally:
        CONTACT_DELIVERY_LOCK.release()


def accept_contact_message(category:str,name:str,email:str,message:str,request:Request):
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",email):
        raise HTTPException(400,"Enter a valid email address.")
    now=time.time()
    ip=client_key(request)
    with mutex:
        contact_quota[ip]=[x for x in contact_quota[ip] if now-x<86400]
        if len(contact_quota[ip])>=3:
            raise HTTPException(429,"Too many messages. Please try again tomorrow.")
        contact_quota[ip].append(now)
        STORE.put("contact_quota",ip,contact_quota[ip])
    msg_id=uuid.uuid4().hex
    STORE.put("contact",msg_id,{
        "name":name,"email":email,"message":message,
        "category":category,"status":"new","created":now,"emailed":False})
    if mail_configured():
        threading.Thread(target=flush_contact_notifications,
                         daemon=True,name="support-notify").start()
    return {"received":True,"reference":msg_id[:8],
            "message":"Your report has been saved for review."}


@app.post("/api/contact")
def contact(payload:ContactRequest,request:Request):
    return accept_contact_message("support",payload.name,payload.email,payload.message,request)


@app.post("/api/copyright/report")
def copyright_report(payload:CopyrightRequest,request:Request):
    if not payload.good_faith or not payload.accuracy:
        raise HTTPException(400,"Confirm the good-faith and accuracy statements.")
    parsed=urlparse(payload.material_url.strip())
    if parsed.scheme not in ("https","http") or not parsed.hostname:
        raise HTTPException(400,"Enter the material URL using http:// or https://.")
    message=("Copyright work: "+payload.work+
             "\nMaterial URL: "+payload.material_url+
             "\nDetails: "+payload.details+
             "\nElectronic signature: "+payload.signature+
             "\nGood-faith statement: affirmed"+
             "\nAccuracy and authority statement: affirmed")
    return accept_contact_message("copyright",payload.name,payload.email,message,request)


@app.get("/admin",include_in_schema=False)
def admin_page():
    return FileResponse(ROOT/"static"/"admin.html")



SITE_URL=os.getenv("SITE_URL","https://clipconvert-web-production.up.railway.app").rstrip("/")
PUBLIC_PATHS=("", "faq", "add-on", "bookmarklet", "thumbnail", "contact",
              "privacy", "copyright", "terms")
SEO_PAGES={
    "":("ClipConvert — YouTube to MP3 & MP4",
        "Convert authorized YouTube videos into MP3 audio or MP4 video. Best available quality, multi-link batches and organized downloads."),
    "faq":("Frequently asked questions — ClipConvert",
           "Answers about ClipConvert audio and video conversion, formats, limits and downloads."),
    "add-on":("Browser extension — ClipConvert",
              "Use the ClipConvert browser extension for authorized YouTube conversions."),
    "bookmarklet":("Bookmarklets — ClipConvert",
                   "Convert a permitted YouTube video using convenient browser bookmarklets."),
    "thumbnail":("Thumbnail downloader — ClipConvert",
                 "Retrieve a thumbnail image from a public YouTube video."),
    "contact":("Contact support — ClipConvert",
               "Contact ClipConvert about conversions, rights concerns and error reports."),
    "privacy":("Privacy policy — ClipConvert",
               "Read how ClipConvert handles temporary files, job data and support submissions."),
    "copyright":("Copyright policy — ClipConvert",
                 "Learn about ClipConvert copyright compliance and reporting concerns."),
    "terms":("Terms of service — ClipConvert",
             "Review ClipConvert's acceptable-use terms and service limitations."),
}


@app.get("/robots.txt",include_in_schema=False)
def robots_txt():
    return Response(
        "User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /admin\n"
        "Sitemap: "+SITE_URL+"/sitemap.xml\n",
        media_type="text/plain",headers={"Cache-Control":"public, max-age=3600"})


@app.get("/sitemap.xml",include_in_schema=False)
def sitemap_xml():
    links=[SITE_URL+("/"+p if p else "/") for p in SEO_PAGES]
    xml='<?xml version="1.0" encoding="UTF-8"?>\n'
    xml+='<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for link in links:
        xml+="<url><loc>"+html.escape(link,quote=True)+"</loc></url>\n"
    xml+="</urlset>\n"
    return Response(xml,media_type="application/xml",
                    headers={"Cache-Control":"public, max-age=3600"})


@app.get("/{path:path}",include_in_schema=False)
def page(path:str):
    if path not in PUBLIC_PATHS:
        raise HTTPException(404,"Page not found.")
    title,description=SEO_PAGES[path]
    canonical=SITE_URL+("/"+path if path else "/")
    doc=(ROOT/"static"/"index.html").read_text(encoding="utf-8")
    # Hide the homepage in the first HTML response for secondary routes.
    # Do this before sending HTML, not after DOMContentLoaded, to avoid flashes.
    if path:
        doc=doc.replace('data-route="home"','data-route="secondary"',1)
        doc=doc.replace('<div id="homepage">','<div id="homepage" hidden>',1)
    # Server-rendered metadata for search engines that do not execute JS.
    doc=doc.replace('ClipConvert — YouTube to MP3 & MP4</title>',
                    html.escape(title)+"</title>",1)
    doc=doc.replace('content="Convert permitted YouTube videos to MP3 or MP4. Fast, simple, no account needed."',
                    'content="'+html.escape(description,quote=True)+'"',1)
    doc=doc.replace('content="ClipConvert — Simple MP3 & MP4 conversion"',
                    'content="'+html.escape(title,quote=True)+'"',1)
    doc=doc.replace('content="Paste a YouTube link, choose a format, and download."',
                    'content="'+html.escape(description,quote=True)+'"',1)
    doc=doc.replace('href="https://clipconvert-web-production.up.railway.app/"',
                    'href="'+html.escape(canonical,quote=True)+'"',1)
    doc=doc.replace('property="og:url" content="https://clipconvert-web-production.up.railway.app/"',
                    'property="og:url" content="'+html.escape(canonical,quote=True)+'"',1)
    return HTMLResponse(doc,headers={"Cache-Control":"no-cache, must-revalidate"})
