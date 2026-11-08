import io
import math
import struct
import subprocess
import shutil
import tempfile
import time
import unittest
import wave

from fastapi.testclient import TestClient
from app import app

client=TestClient(app)


def sample_wav():
    mem=io.BytesIO()
    with wave.open(mem,"wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(16000)
        samples=b"".join(
            struct.pack("<h",int(6000*math.sin(2*math.pi*440*i/16000)))
            for i in range(16000)
        )
        writer.writeframes(samples)
    return mem.getvalue()


class UploadTests(unittest.TestCase):
    def test_upload_requires_rights(self):
        res=client.post("/api/upload",data={"format":"mp3","quality":128},
                        files={"file":("tone.wav",sample_wav(),"audio/wav")})
        self.assertEqual(res.status_code,400)

    def test_upload_rejects_disallowed_extension(self):
        res=client.post("/api/upload",data={"format":"mp3","quality":128,"rights_confirmed":"true"},
                        files={"file":("test.exe",b"x"*2000,"application/octet-stream")})
        self.assertEqual(res.status_code,400)

    def test_upload_rejects_invalid_quality(self):
        res=client.post("/api/upload",data={"format":"mp3","quality":600,"rights_confirmed":"true"},
                        files={"file":("tone.wav",sample_wav(),"audio/wav")})
        self.assertEqual(res.status_code,400)

    def test_wav_to_mp3_and_download(self):
        res=client.post("/api/upload",data={"format":"mp3","quality":128,"rights_confirmed":"true"},
                        files={"file":("tone.wav",sample_wav(),"audio/wav")})
        self.assertEqual(res.status_code,202,res.text)
        jid=res.json()["id"]
        for _ in range(100):
            state=client.get("/api/jobs/"+jid).json()
            if state["state"] in ("ready","error"):
                break
            time.sleep(.1)
        self.assertEqual(state["state"],"ready",state)
        self.assertEqual(state["progress"],100)
        download=client.get(state["download_url"])
        self.assertEqual(download.status_code,200)
        self.assertIn("audio/mpeg",download.headers["content-type"])
        self.assertGreater(len(download.content),4000)

    def test_audio_only_cannot_convert_to_video(self):
        res=client.post("/api/upload",data={"format":"mp4","quality":360,"rights_confirmed":"true"},
                        files={"file":("tone.wav",sample_wav(),"audio/wav")})
        self.assertEqual(res.status_code,202,res.text)
        jid=res.json()["id"]
        for _ in range(100):
            state=client.get("/api/jobs/"+jid).json()
            if state["state"] in ("ready","error"):break
            time.sleep(.1)
        self.assertEqual(state["state"],"error",state)
        self.assertIn("video track",state["error"].lower())


    @unittest.skipUnless(shutil.which("ffmpeg"),"FFmpeg is not available")
    def test_mp4_upload_and_download(self):
        with tempfile.TemporaryDirectory() as directory:
            path=directory+"/short.mp4"
            ffmpeg=subprocess.run([
                "ffmpeg","-hide_banner","-loglevel","error","-y",
                "-f","lavfi","-i","testsrc=size=160x90:rate=8",
                "-f","lavfi","-i","sine=frequency=440:sample_rate=16000",
                "-t","1","-c:v","libx264","-pix_fmt","yuv420p",
                "-c:a","aac","-shortest",path
            ],capture_output=True,timeout=35)
            if ffmpeg.returncode!=0:
                self.skipTest("Runner cannot synthesize an H264 source")
            with open(path,"rb") as infile:
                data=infile.read()
        res=client.post("/api/upload",data={"format":"mp4","quality":360,"rights_confirmed":"true"},
                        files={"file":("short.mp4",data,"video/mp4")})
        self.assertEqual(res.status_code,202,res.text)
        jid=res.json()["id"]
        for _ in range(200):
            state=client.get("/api/jobs/"+jid).json()
            if state["state"] in ("ready","error"): break
            time.sleep(.1)
        self.assertEqual(state["state"],"ready",state)
        response=client.get(state["download_url"])
        self.assertEqual(response.status_code,200)
        self.assertIn("video/mp4",response.headers["content-type"])
        self.assertGreater(len(response.content),2000)


if __name__=="__main__":unittest.main()
