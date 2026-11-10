"""Shorts Studio: authorized uploads, private job tokens, bounded rendering."""
from __future__ import annotations
import json, os, secrets, shutil, threading, time, uuid
from pathlib import Path
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Query
from fastapi.responses import FileResponse
from shorts_studio import render_short

router=APIRouter(prefix="/api/studio")
ROOT=Path(os.getenv("MEDIA_DIR","/tmp/converter-media"))/"studio"
ROOT.mkdir(parents=True,exist_ok=True)
MAX_UPLOAD=max(5,min(int(os.getenv("STUDIO_MAX_UPLOAD_MB","200")),512))*1024*1024
MAX_LOGO=5*1024*1024
TTL=3600
LIMIT=threading.BoundedSemaphore(1)
LOCK=threading.RLock()
JOBS={}
ALLOWED={".mp4",".mov",".m4v",".webm",".mkv"}
LOGOS={".png",".webp"}

def _save(job):
    path=ROOT/job["id"]/"job.json"
    tmp=path.with_suffix(".tmp")
    tmp.write_text(json.dumps(job),encoding="utf-8")
    tmp.replace(path)

def _cleanup():
    now=time.time()
    with LOCK:
        for folder in ROOT.iterdir():
            if not folder.is_dir(): continue
            try:
                record=json.loads((folder/"job.json").read_text(encoding="utf-8"))
                expired=now-record["created"]>TTL
            except (OSError,ValueError,KeyError):
                expired=now-folder.stat().st_mtime>TTL
            if expired:
                JOBS.pop(folder.name,None)
                shutil.rmtree(folder,ignore_errors=True)

def _get(jid,token):
    if not len(jid)==32 or not all(c in "0123456789abcdef" for c in jid):
        raise HTTPException(404,"Job not found")
    with LOCK:
        job=JOBS.get(jid)
        if job is None:
            try: job=json.loads((ROOT/jid/"job.json").read_text(encoding="utf-8"))
            except (OSError,ValueError): raise HTTPException(404,"Job not found")
            JOBS[jid]=job
        if time.time()-job["created"]>TTL:
            raise HTTPException(404,"Job expired")
        if not secrets.compare_digest(token or "",job["token"]):
            raise HTTPException(404,"Job not found")
        return dict(job)

def _render(jid,src,logo,mode,start,duration):
    with LIMIT:
        with LOCK:
            job=JOBS[jid]
            job["state"]="working"
            _save(job)
        try:
            render_short(str(src),str(src.parent/"branded.mp4"),
                         logo=str(logo) if logo else None,
                         mode=mode,start=start,duration=duration)
            state,error="ready",None
        except Exception:
            state,error="error","Video rendering failed"
        with LOCK:
            job=JOBS[jid]
            job.update(state=state,error=error)
            _save(job)

@router.post("/render",status_code=202)
async def create_render(video:UploadFile=File(...),logo:UploadFile|None=File(None),
                        mode:str=Form("fit"),start:float=Form(0),
                        duration:float|None=Form(None),rights_confirmed:bool=Form(False)):
    if not rights_confirmed:
        raise HTTPException(400,"Confirm you own or are authorized to edit this video.")
    if mode not in ("fit","fill") or not 0<=start<=86400 or duration is not None and not 0<duration<=14400:
        raise HTTPException(400,"Invalid render settings")
    suffix=Path(video.filename or "").suffix.lower()
    if suffix not in ALLOWED: raise HTTPException(400,"Unsupported video file type")
    if logo and Path(logo.filename or "").suffix.lower() not in LOGOS:
        raise HTTPException(400,"Logo must be PNG or WebP")
    _cleanup()
    with LOCK:
        if sum(j["state"] in ("queued","working") for j in JOBS.values())>=3:
            raise HTTPException(503,"Studio queue is full")
        jid=uuid.uuid4().hex
        token=secrets.token_urlsafe(32)
        directory=ROOT/jid
        directory.mkdir(mode=0o700)
        job={"id":jid,"token":token,"state":"receiving","created":time.time(),"error":None}
        JOBS[jid]=job
        _save(job)
    try:
        src=directory/("source"+suffix)
        size=0
        with src.open("wb") as output:
            while chunk:=await video.read(1024*1024):
                size+=len(chunk)
                if size>MAX_UPLOAD: raise HTTPException(413,"Video exceeds upload limit")
                output.write(chunk)
        if size==0: raise HTTPException(400,"Video is empty")
        brand=None
        if logo:
            brand=directory/("logo"+Path(logo.filename or "").suffix.lower())
            data=await logo.read(MAX_LOGO+1)
            if not data or len(data)>MAX_LOGO: raise HTTPException(413,"Logo exceeds 5 MB")
            brand.write_bytes(data)
        with LOCK:
            job["state"]="queued"
            _save(job)
        threading.Thread(target=_render,args=(jid,src,brand,mode,start,duration),daemon=True).start()
        return {"id":jid,"state":"queued","status_url":f"/api/studio/jobs/{jid}?token={token}"}
    except Exception:
        with LOCK: JOBS.pop(jid,None)
        shutil.rmtree(directory,ignore_errors=True)
        raise

@router.get("/jobs/{jid}")
def status(jid:str,token:str=Query(...)):
    job=_get(jid,token)
    return {"id":jid,"state":job["state"],"error":job["error"],
            "download_url":f"/api/studio/jobs/{jid}/download?token={token}" if job["state"]=="ready" else None}

@router.get("/jobs/{jid}/download")
def download(jid:str,token:str=Query(...)):
    job=_get(jid,token)
    output=ROOT/jid/"branded.mp4"
    if job["state"]!="ready" or not output.is_file():
        raise HTTPException(404,"Rendered file is not ready")
    return FileResponse(output,media_type="video/mp4",filename="clipconvert-short.mp4",
                        headers={"Cache-Control":"private, no-store","Referrer-Policy":"no-referrer"})
