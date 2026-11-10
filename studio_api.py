"""Isolated Shorts Studio upload/render API. No third-party watermark stripping."""
from __future__ import annotations
import os, shutil, threading, time, uuid
from pathlib import Path
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from shorts_studio import render_short

router=APIRouter(prefix="/api/studio")
ROOT=Path(os.getenv("MEDIA_DIR","/tmp/converter-media"))/"studio"
ROOT.mkdir(parents=True,exist_ok=True)
MAX_UPLOAD=min(int(os.getenv("STUDIO_MAX_UPLOAD_MB","200")),512)*1024*1024
LIMIT=threading.BoundedSemaphore(1)
LOCK=threading.RLock()
JOBS={}
ALLOWED={".mp4",".mov",".m4v",".webm",".mkv"}
LOGOS={".png",".webp"}

def _get(jid):
    with LOCK:
        job=JOBS.get(jid)
        if not job or time.time()-job["created"]>3600:
            raise HTTPException(404,"Studio job expired or not found")
        return job

def _render(jid,src,logo,mode,start,duration):
    with LIMIT:
        with LOCK: JOBS[jid].update(state="working")
        try:
            render_short(str(src),str(src.parent/"branded.mp4"),
                         logo=str(logo) if logo else None,
                         mode=mode,start=start,duration=duration)
            with LOCK: JOBS[jid].update(state="ready")
        except Exception:
            with LOCK: JOBS[jid].update(state="error",error="Video rendering failed")

@router.post("/render",status_code=202)
async def create_render(video:UploadFile=File(...),logo:UploadFile|None=File(None),
                        mode:str=Form("fit"),start:float=Form(0),
                        duration:float|None=Form(None),rights_confirmed:bool=Form(False)):
    if not rights_confirmed: raise HTTPException(400,"Confirm you own or are authorized to edit this video.")
    if mode not in ("fit","fill") or start<0 or start>86400 or duration is not None and not 0<duration<=14400:
        raise HTTPException(400,"Invalid render settings")
    suffix=Path(video.filename or "").suffix.lower()
    if suffix not in ALLOWED: raise HTTPException(400,"Unsupported video file type")
    if logo and Path(logo.filename or "").suffix.lower() not in LOGOS:
        raise HTTPException(400,"Logo must be PNG or WebP")
    with LOCK:
        if sum(j["state"] in ("queued","working") for j in JOBS.values())>=3:
            raise HTTPException(503,"Studio queue is full")
    jid=uuid.uuid4().hex
    directory=ROOT/jid
    directory.mkdir(parents=True)
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
            extension=Path(logo.filename or "").suffix.lower()
            brand=directory/("logo"+extension)
            data=await logo.read(5*1024*1024+1)
            if not data or len(data)>5*1024*1024: raise HTTPException(413,"Logo exceeds 5 MB")
            brand.write_bytes(data)
        with LOCK: JOBS[jid]={"id":jid,"state":"queued","created":time.time(),"error":None}
        threading.Thread(target=_render,args=(jid,src,brand,mode,start,duration),daemon=True).start()
        return {"id":jid,"state":"queued","status_url":"/api/studio/jobs/"+jid}
    except Exception:
        shutil.rmtree(directory,ignore_errors=True)
        raise

@router.get("/jobs/{jid}")
def status(jid:str):
    job=_get(jid)
    return {"id":jid,"state":job["state"],"error":job["error"],
            "download_url":"/api/studio/jobs/"+jid+"/download" if job["state"]=="ready" else None}

@router.get("/jobs/{jid}/download")
def download(jid:str):
    job=_get(jid)
    output=ROOT/jid/"branded.mp4"
    if job["state"]!="ready" or not output.is_file():
        raise HTTPException(404,"Rendered file is not ready")
    return FileResponse(output,media_type="video/mp4",filename="clipconvert-short.mp4")
