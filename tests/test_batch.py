import io
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
import app as module

client=TestClient(module.app)
V1="NY6acnscmwo"
V2="aqz-KE-bpKQ"
V3="dQw4w9WgXcQ"


def mock_conversion(jid,vid,fmt,quality):
    folder=module.MEDIA/jid
    folder.mkdir(mode=0o700,parents=True,exist_ok=True)
    output=folder/("video."+fmt)
    output.write_bytes(("test converted media for "+vid).encode()*100)
    module.change(jid,state="ready",progress=100,message="Ready to download",
                  file=str(output),title="Test "+vid,actual_quality="320 kbps",
                  ended=time.time())


def wait_batch(bid):
    for _ in range(200):
        r=client.get("/api/batches/"+bid)
        if r.status_code!=200:
            raise AssertionError(r.text)
        b=r.json()
        if b["state"] in ("complete","partial","failed"):
            return b
        time.sleep(.02)
    raise AssertionError("Batch did not finish")


class BatchTests(unittest.TestCase):
    def test_requires_rights(self):
        r=client.post("/api/batches",json={
            "links":["https://youtu.be/"+V1,"https://youtu.be/"+V2],"format":"mp3"})
        self.assertEqual(r.status_code,400)

    def test_rejects_invalid_urls_without_creating_any_jobs(self):
        before=len(module.jobs)
        r=client.post("/api/batches",json={
            "links":["https://youtu.be/"+V1,"http://127.0.0.1/admin"],
            "format":"mp3","rights_confirmed":True})
        self.assertEqual(r.status_code,400)
        self.assertEqual(len(module.jobs),before)

    def test_duplicate_video_ids_are_rejected_if_only_one_unique(self):
        r=client.post("/api/batches",json={
            "links":["https://youtu.be/"+V1,"https://youtube.com/watch?v="+V1],
            "format":"mp3","rights_confirmed":True})
        self.assertEqual(r.status_code,400)
        self.assertIn("different",r.text.lower())

    def test_maximum_hundred_links(self):
        r=client.post("/api/batches",json={
            "links":["https://youtu.be/"+V1]*101,
            "format":"mp3","rights_confirmed":True})
        self.assertEqual(r.status_code,422)

    def test_two_video_batch_and_combined_zip(self):
        payload={"links":["https://youtu.be/"+V1,"https://youtu.be/"+V2],
                 "format":"mp3","quality":0,"rights_confirmed":True}
        with patch.object(module,"convert",mock_conversion):
            r=client.post("/api/batches",json=payload)
            self.assertEqual(r.status_code,202,r.text)
            bid=r.json()["id"]
            batch=wait_batch(bid)
        self.assertEqual(batch["state"],"complete",batch)
        self.assertEqual(batch["succeeded"],2)
        self.assertEqual(batch["failed"],0)
        self.assertEqual(len(batch["items"]),2)
        self.assertTrue(batch["download_url"])
        for j in batch["items"]:
            self.assertEqual(j["state"],"ready")
            self.assertEqual(j["quality"],0)
            self.assertEqual(client.get(j["download_url"]).status_code,200)
            self.assertEqual(client.get(j["folder_url"]).status_code,200)
        result=client.get(batch["download_url"])
        self.assertEqual(result.status_code,200,result.text[:400])
        self.assertIn("application/zip",result.headers["content-type"])
        with zipfile.ZipFile(io.BytesIO(result.content)) as z:
            names=z.namelist()
            self.assertEqual(len(names),5,names)
            self.assertIn("Batch Results.txt",names)
            files=[x for x in names if x.endswith(".mp3")]
            self.assertEqual(len(files),2)
            self.assertTrue(files[0].startswith("01 - "))
            self.assertTrue(files[1].startswith("02 - "))
            self.assertNotEqual(files[0].split("/")[0],files[1].split("/")[0])
            self.assertTrue(all(z.getinfo(p).compress_type==zipfile.ZIP_STORED for p in files))
            self.assertIn("2 of 2 videos ready",z.read("Batch Results.txt").decode())
            self.assertEqual(z.read(files[0]),("test converted media for "+V1).encode()*100)

    def test_thirty_two_video_zip_streams_without_archive_disk_space(self):
        # Reproduce the 32-link failure without contacting YouTube.
        ids=[str(i).zfill(11) for i in range(32)]
        with patch.object(module,"convert",mock_conversion):
            response=client.post("/api/batches",json={
                "links":["https://youtu.be/"+vid for vid in ids],
                "format":"mp4","rights_confirmed":True})
            self.assertEqual(response.status_code,202,response.text)
            bid=response.json()["id"]
            batch=wait_batch(bid)
        self.assertEqual(batch["succeeded"],32)
        old_archive=module.MEDIA/("batch-"+bid)/"all-videos.zip"
        self.assertFalse(old_archive.exists())
        # A full disk must not prevent downloading already completed media.
        with patch.object(module.shutil,"disk_usage",side_effect=OSError("disk full")):
            downloaded=client.get(batch["download_url"])
        self.assertEqual(downloaded.status_code,200)
        self.assertFalse(old_archive.exists())
        with zipfile.ZipFile(io.BytesIO(downloaded.content)) as archive:
            self.assertIsNone(archive.testzip())
            files=[name for name in archive.namelist() if name.endswith(".mp4")]
            self.assertEqual(len(files),32)
            self.assertIn("32 of 32 videos ready",archive.read("Batch Results.txt").decode())

    def test_partial_failure_produces_downloadable_successes(self):
        def fake(jid,vid,fmt,quality):
            if vid==V2:
                module.change(jid,state="error",progress=0,error="Test source unavailable",
                              message="Conversion failed",ended=time.time())
            else:
                mock_conversion(jid,vid,fmt,quality)
        with patch.object(module,"convert",fake):
            r=client.post("/api/batches",json={
                "links":["https://youtu.be/"+V1,"https://youtu.be/"+V2],
                "format":"mp3","rights_confirmed":True})
            self.assertEqual(r.status_code,202,r.text)
            b=wait_batch(r.json()["id"])
        self.assertEqual(b["state"],"partial",b)
        self.assertEqual(b["succeeded"],1)
        self.assertEqual(b["failed"],1)
        zip_response=client.get(b["download_url"])
        self.assertEqual(zip_response.status_code,200)
        with zipfile.ZipFile(io.BytesIO(zip_response.content)) as z:
            names=z.namelist()
            self.assertEqual(len([p for p in names if p.endswith(".mp3")]),1)
            self.assertIn("FAILED",z.read("Batch Results.txt").decode())


if __name__=="__main__":
    unittest.main()
