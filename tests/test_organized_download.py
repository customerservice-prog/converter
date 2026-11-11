import io
import os
import struct
import time
import unittest
import wave
import zipfile
from fastapi.testclient import TestClient
from app import app, safe_media_name

client=TestClient(app)

def small_wav():
    raw=io.BytesIO()
    with wave.open(raw,"wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"".join(struct.pack("<h",int(10000*((i%61)/61-.5))) for i in range(44100)))
    return raw.getvalue()

class OrganizedDownloadTests(unittest.TestCase):
    def test_windows_safe_name(self):
        value=safe_media_name('../<con>: bad\\name|.mp4')
        self.assertNotIn("/",value)
        self.assertNotIn("\\",value)
        self.assertNotIn(":",value)
        self.assertTrue(value)

    def test_folder_not_available_before_job(self):
        result=client.get("/api/download/doesnotexist/folder")
        self.assertEqual(result.status_code,404)

    def test_zip_contains_folder_and_byte_identical_media(self):
        response=client.post("/api/upload",data={
            "format":"mp3","quality":"128","rights_confirmed":"true"},
            files={"file":("My Test Audio.wav",small_wav(),"audio/wav")})
        self.assertEqual(response.status_code,202,response.text)
        jid=response.json()["id"]
        for _ in range(100):
            job=client.get("/api/jobs/"+jid).json()
            if job["state"] in ("ready","error"):break
            time.sleep(.1)
        self.assertEqual(job["state"],"ready",job)
        self.assertIn("/folder",job["folder_url"])
        z=client.get(job["folder_url"])
        self.assertEqual(z.status_code,200)
        self.assertEqual(z.headers["content-type"],"application/zip")
        self.assertIn(".zip",z.headers["content-disposition"])
        with zipfile.ZipFile(io.BytesIO(z.content)) as archive:
            items=archive.namelist()
            self.assertEqual(len(items),2)
            self.assertEqual(len({p.split("/")[0] for p in items}),1)
            self.assertTrue(items[0].endswith(".mp3"))
            self.assertTrue(items[1].endswith("Video Info.txt"))
            self.assertEqual(archive.getinfo(items[0]).compress_type,zipfile.ZIP_STORED)
            self.assertTrue(archive.read(items[0]))
            info=archive.read(items[1]).decode()
            self.assertIn("Actual quality:",info)
            self.assertIn("My Test Audio",info)
        self.assertEqual(client.get("/api/jobs/"+jid).json()["state"],"downloaded")
        self.assertEqual(client.get(job["folder_url"]).status_code,404)
        self.assertFalse((__import__("app").MEDIA/jid).exists())

if __name__=="__main__":
    unittest.main()
