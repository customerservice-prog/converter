from __future__ import annotations
import logging, os, re, shutil, smtplib, threading, time, uuid
from collections import defaultdict
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from urllib.request import Request as HttpRequest, urlopen
from typing import Literal
import yt_dlp
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT=Path(__file__).resolve().parent
MEDIA=Path(os.getenv("MEDIA_DIR","/tmp/converter-media")); MEDIA.mkdir(parents=True,exist_ok=True)
MAX_ACTIVE=max(1,int(os.getenv("MAX_ACTIVE_JOBS","2")))
DAILY_LIMIT=max(1,int(os.getenv("DAILY_LIMIT","20")))
FILE_LIMIT=max(10,int(os.getenv("MAX_FILE_MB","512")))*1024*1024
TTL=max(300,int(os.getenv("FILE_TTL_SECONDS","3600")))
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
        opts={"js_runtimes":{"node":{}},"quiet":True,"no_warnings":True,"noplaylist":True,"ignoreerrors":False,
              "cachedir":False,"socket_timeout":20,"retries":2,"fragment_retries":2,
              "outtmpl":str(directory/"%(id)s.%(ext)s"),"restrictfilenames":True}
        with yt_dlp.YoutubeDL({**opts,"skip_download":True}) as ydl:
            info=ydl.extract_info(url,download=False)
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
        msg=str(exc) if isinstance(exc,ValueError) else "Conversion failed. YouTube may have restricted this video or this server."
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
    return {"status":"ok","ffmpeg":bool(shutil.which("ffmpeg")),"yt_dlp":yt_dlp.version.__version__}

@app.post("/api/jobs",status_code=202)
def create(payload:ConvertRequest,request:Request):
    if not payload.rights_confirmed: raise HTTPException(400,"Confirm that you have permission to download this media.")
    try: vid=video_id(payload.url)
    except ValueError as exc: raise HTTPException(400,str(exc)) from exc
    if payload.quality not in QUALITIES[payload.format]: raise HTTPException(400,"Unsupported format quality.")
    cleanup()
    now=time.time(); ip=request.client.host if request.client else "unknown"
    with mutex:
        if sum(j["state"] in ("queued","working") for j in jobs.values())>=MAX_ACTIVE:
            raise HTTPException(503,"The converter is busy. Please try again.")
        if len(quota[ip])>=DAILY_LIMIT: raise HTTPException(429,"Daily download limit reached.")
        quota[ip].append(now); jid=uuid.uuid4().hex
        job={"id":jid,"state":"queued","progress":0,"message":"Starting…","title":"",
             "thumbnail":None,"duration":None,"format":payload.format,"quality":payload.quality,
             "error":None,"created":now}
        jobs[jid]=job
    threading.Thread(target=convert,args=(jid,vid,payload.format,payload.quality),daemon=True).start()
    return public(job)

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
