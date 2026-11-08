from __future__ import annotations
import logging, os, re, shutil, smtplib, threading, time, uuid, subprocess, json
from collections import defaultdict
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from urllib.request import Request as HttpRequest, urlopen
from typing import Literal
import yt_dlp
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT=Path(__file__).resolve().parent
MEDIA=Path(os.getenv("MEDIA_DIR","/tmp/converter-media")); MEDIA.mkdir(parents=True,exist_ok=True)
MAX_ACTIVE=max(1,int(os.getenv("MAX_ACTIVE_JOBS","2")))
DAILY_LIMIT=max(1,int(os.getenv("DAILY_LIMIT","20")))
FILE_LIMIT=max(10,int(os.getenv("MAX_FILE_MB","512")))*1024*1024
TTL=max(300,int(os.getenv("FILE_TTL_SECONDS","3600")))
MAX_UPLOAD_BYTES=max(5,int(os.getenv("MAX_UPLOAD_MB","100")))*1024*1024
UPLOAD_EXTENSIONS={".mp4",".mov",".m4v",".webm",".mkv",".mp3",".m4a",".wav",".flac",".ogg",".aac"}
ID=re.compile(r"^[A-Za-z0-9_-]{11}$")
HOSTS={"youtube.com","www.youtube.com","m.youtube.com","music.youtube.com","youtube-nocookie.com","www.youtube-nocookie.com","youtu.be","www.youtu.be"}
DURATION_LIMIT={"mp3":14400,"mp4":1800}
QUALITIES={"mp3":(128,192,320),"mp4":(360,720,1080)}
jobs={}; quota=defaultdict(list); contact_quota=defaultdict(list); mutex=threading.RLock()
log=logging.getLogger("converter")
app=FastAPI(title="Converter API",docs_url=None,redoc_url=None)
app.mount("/assets",StaticFiles(directory=ROOT/"static"),name="assets")

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
    fields=("id","state","progress","message","title","thumbnail","duration","format","quality","error")
    data={key:job.get(key) for key in fields}
    if job["state"]=="ready": data["download_url"]="/api/download/"+job["id"]
    return data

def change(jid,**kwargs):
    with mutex:
        if jid in jobs: jobs[jid].update(kwargs)

def cleanup():
    now=time.time()
    with mutex:
        expired=[k for k,j in jobs.items() if j["state"] in ("ready","error") and now-j.get("ended",now)>TTL]
        for k in expired: jobs.pop(k,None)
        for bucket in (quota,contact_quota):
            for ip in list(bucket):
                bucket[ip]=[t for t in bucket[ip] if now-t<86400]
                if not bucket[ip]: bucket.pop(ip,None)
    for k in expired: shutil.rmtree(MEDIA/k,ignore_errors=True)

def janitor():
    while True:
        time.sleep(300)
        cleanup()

threading.Thread(target=janitor,daemon=True,name="media-cleanup").start()

class ConvertRequest(BaseModel):
    url:str=Field(min_length=1,max_length=2048)
    format:Literal["mp3","mp4"]="mp3"
    quality:int=192
    rights_confirmed:bool=False

class ContactRequest(BaseModel):
    name:str=Field(min_length=1,max_length=80)
    email:str=Field(min_length=3,max_length=254)
    message:str=Field(min_length=8,max_length=3000)

def convert(jid,vid,fmt,quality):
    directory=MEDIA/jid; directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    url="https://www.youtube.com/watch?v="+vid
    try:
        change(jid,state="working",progress=3,message="Checking video…")
        opts={"source_address":"::" if os.getenv("PREFER_IPV6")=="1" else "0.0.0.0","js_runtimes":{"node":{}},"quiet":True,"no_warnings":True,"noplaylist":True,"ignoreerrors":False,
              "cachedir":False,"socket_timeout":20,"retries":2,"fragment_retries":2,
              "outtmpl":str(directory/"%(id)s.%(ext)s"),"restrictfilenames":True}
        # Try a small, bounded selection of ordinary, public YouTube playback
        # clients. These do not authorize content that requires a sign-in, and
        # they cannot guarantee access from a datacenter IP address.
        clients_to_try=(None, ("tv", "web_safari"), ("web_embedded",), ("android_vr",))
        for index,clients in enumerate(clients_to_try):
            check_opts={**opts,"skip_download":True}
            if clients:
                check_opts["extractor_args"]={"youtube":{"player_client":list(clients)}}
                change(jid,message="Checking available video formats…")
            try:
                with yt_dlp.YoutubeDL(check_opts) as ydl:
                    info=ydl.extract_info(url,download=False)
                if clients:
                    opts["extractor_args"]={"youtube":{"player_client":list(clients)}}
                break
            except yt_dlp.utils.DownloadError as e:
                reason=str(e).lower()
                challenge=any(term in reason for term in (
                    "sign in to confirm", "not a bot", "not available on this app",
                    "this video is unavailable", "video unavailable"))
                if index+1<len(clients_to_try) and challenge:
                    log.info("Public playback profile %d rejected video %s; trying next profile",index,vid)
                    continue
                raise
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
                change(jid,progress=90,message="Finalizing your file…")
        options={**opts,"progress_hooks":[progress]}
        if fmt=="mp3":
            options["format"]="bestaudio/best"
            options["postprocessors"]=[{"key":"FFmpegExtractAudio","preferredcodec":"mp3","preferredquality":str(quality)}]
        else:
            options["format"]=("bestvideo[ext=mp4][height<="+str(quality)+"]+bestaudio[ext=m4a]/"
                               "best[ext=mp4][height<="+str(quality)+"]")
            options["merge_output_format"]="mp4"
        with yt_dlp.YoutubeDL(options) as ydl: ydl.download([url])
        files=sorted(directory.glob("*."+fmt))
        if not files: raise ValueError("No compatible output is available for this video.")
        if files[0].stat().st_size>FILE_LIMIT: raise ValueError("Converted file is too large.")
        change(jid,state="ready",progress=100,message="Ready to download",file=str(files[0]),ended=time.time())
    except Exception as exc:
        log.warning("Job %s failed: %s",jid,type(exc).__name__)
        text=str(exc).lower()
        if "sign in to confirm" in text or "not a bot" in text:
            msg=("YouTube is requiring sign-in verification from this server. "
                 "This link cannot be converted here right now. If you have the media file, "
                 "choose Upload File to convert it instead.")
        else:
            msg=str(exc) if isinstance(exc,ValueError) else "Conversion failed. This video may be restricted or temporarily unavailable."
        change(jid,state="error",progress=0,message="Conversion failed",error=msg,ended=time.time())
        shutil.rmtree(directory,ignore_errors=True)

@app.middleware("http")
async def headers(request:Request,call_next):
    result=await call_next(request)
    result.headers["X-Content-Type-Options"]="nosniff"
    result.headers["X-Frame-Options"]="DENY"
    result.headers["Referrer-Policy"]="strict-origin-when-cross-origin"
    result.headers["Permissions-Policy"]="camera=(),microphone=(),geolocation=()"
    if request.url.path.startswith("/api/"): result.headers["Cache-Control"]="no-store"
    return result

@app.get("/api/health")
def health():
    return {"status":"ok","ffmpeg":bool(shutil.which("ffmpeg")),"yt_dlp":yt_dlp.version.__version__, "features":["upload","youtube","thumbnail"]}

@app.post("/api/jobs",status_code=202)
def create(payload:ConvertRequest,request:Request):
    if not payload.rights_confirmed: raise HTTPException(400,"Confirm that you have permission to download this media.")
    try: vid=video_id(payload.url)
    except ValueError as exc: raise HTTPException(400,str(exc)) from exc
    if payload.quality not in QUALITIES[payload.format]: raise HTTPException(400,"Unsupported format quality.")
    cleanup()
    now=time.time(); ip=request.client.host if request.client else "unknown"
    with mutex:
        if sum(j["state"] in ("receiving","queued","working") for j in jobs.values())>=MAX_ACTIVE:
            raise HTTPException(503,"The converter is busy. Please try again.")
        if len(quota[ip])>=DAILY_LIMIT: raise HTTPException(429,"Daily download limit reached.")
        quota[ip].append(now); jid=uuid.uuid4().hex
        job={"id":jid,"state":"queued","progress":0,"message":"Starting…","title":"YouTube video",
             "thumbnail":"https://i.ytimg.com/vi/"+vid+"/hqdefault.jpg","duration":None,"format":payload.format,"quality":payload.quality,
             "error":None,"created":now}
        jobs[jid]=job
    threading.Thread(target=convert,args=(jid,vid,payload.format,payload.quality),daemon=True).start()
    return public(job)

def convert_upload(jid: str, extension: str, name: str, fmt: str, quality: int) -> None:
    folder=MEDIA/jid
    source=folder/("source"+extension)
    output=folder/("converted."+fmt)
    try:
        change(jid,state="working",progress=8,message="Checking uploaded media…")
        probe=subprocess.run(
            ["ffprobe","-v","error","-show_entries","format=duration:stream=codec_type",
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
            cmd+=["-map","0:a:0","-vn","-c:a","libmp3lame","-b:a",str(quality)+"k"]
        else:
            # Never upscale; keep dimensions compatible with H.264.
            cmd+=["-map","0:v:0","-map","0:a:0?","-vf",
                  "scale=-2:min(ih\\,"+str(quality)+")",
                  "-c:v","libx264","-preset","veryfast","-crf","23",
                  "-pix_fmt","yuv420p","-c:a","aac","-b:a","128k",
                  "-movflags","+faststart"]
        cmd += [str(output)]
        timeout=max(120,min(1800,int(duration*5)))
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
        source.unlink(missing_ok=True)
        change(jid,state="ready",progress=100,message="Ready to download",
               file=str(output),ended=time.time())
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
    quality: int = Form(...),
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
    ip=request.client.host if request.client else "unknown"
    now=time.time()
    with mutex:
        if sum(j["state"] in ("receiving","queued","working") for j in jobs.values())>=MAX_ACTIVE:
            raise HTTPException(503,"All converters are busy. Please try again.")
        if len(quota[ip])>=DAILY_LIMIT:
            raise HTTPException(429,"Daily conversion limit reached.")
        jid=uuid.uuid4().hex
        quota[ip].append(now)
        jobs[jid]={"id":jid,"state":"receiving","progress":1,
                   "message":"Receiving file…","title":Path(name).stem[:100] or "Uploaded media",
                   "thumbnail":None,"duration":None,"format":format,"quality":quality,
                   "error":None,"created":now}
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
        shutil.rmtree(folder,ignore_errors=True)
        raise
    finally:
        await file.close()
    change(jid,state="queued",progress=5,message="Processing upload…")
    thread=threading.Thread(target=convert_upload,
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

@app.post("/api/contact")
def contact(payload:ContactRequest,request:Request):
    recipient=os.getenv("CONTACT_EMAIL",""); smtp=os.getenv("SMTP_HOST","")
    if not recipient or not smtp: raise HTTPException(503,"The contact form is not configured.")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",payload.email):
        raise HTTPException(400,"Enter a valid email address.")
    now=time.time(); ip=request.client.host if request.client else "unknown"
    with mutex:
        contact_quota[ip]=[x for x in contact_quota[ip] if now-x<86400]
        if len(contact_quota[ip])>=3: raise HTTPException(429,"Too many messages.")
        contact_quota[ip].append(now)
    email=EmailMessage(); email["Subject"]="Converter website contact"
    email["To"]=recipient; email["From"]=os.getenv("SMTP_FROM",recipient)
    email["Reply-To"]=payload.email
    email.set_content("Name: "+payload.name+"\nEmail: "+payload.email+"\n\n"+payload.message)
    try:
        with smtplib.SMTP(smtp,int(os.getenv("SMTP_PORT","587")),timeout=12) as client:
            client.starttls()
            if os.getenv("SMTP_USER"): client.login(os.environ["SMTP_USER"],os.getenv("SMTP_PASSWORD",""))
            client.send_message(email)
    except Exception as exc:
        log.warning("Contact form delivery failed")
        raise HTTPException(502,"Message delivery failed.") from exc
    return {"sent":True}

@app.get("/{path:path}",include_in_schema=False)
def page(path:str):
    if path not in ("","faq","add-on","bookmarklet","thumbnail","contact","privacy","copyright","terms"):
        raise HTTPException(404,"Page not found.")
    return FileResponse(ROOT/"static"/"index.html")
