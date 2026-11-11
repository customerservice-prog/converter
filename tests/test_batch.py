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

    def test_daily_quota_history_cannot_block_new_batches(self):
        old_key="batch-unlimited-test"
        module.STORE.put("quota",old_key,[time.time()]*250)
        try:
            with patch.object(module,"client_key",return_value=old_key), patch.object(module,"convert",mock_conversion):
                r=client.post("/api/batches",json={
                    "links":["https://youtu.be/"+V1,"https://youtu.be/"+V2],
                    "format":"mp3","rights_confirmed":True})
                self.assertEqual(r.status_code,202,r.text)
                completed=wait_batch(r.json()["id"])
                self.assertEqual(completed["state"],"complete")
        finally:
            module.STORE.drop("quota",old_key)

    def test_stop_active_batch_preserves_ready_and_cancels_pending(self):
        import threading, uuid, shutil
        bid=uuid.uuid4().hex
        ready_id=uuid.uuid4().hex
        queued_id=uuid.uuid4().hex
        folder=module.MEDIA/ready_id
        folder.mkdir(parents=True,exist_ok=True)
        media=folder/"video.mp4"
        media.write_bytes(b"saved video"+b"x"*200)
        now=time.time()
        module.jobs[ready_id]={"id":ready_id,"state":"ready","file":str(media),
            "title":"Preserved video","video_id":V1,"format":"mp4",
            "quality":0,"progress":100,"created":now,"ended":now,"batch_id":bid}
        module.jobs[queued_id]={"id":queued_id,"state":"queued",
            "video_id":V2,"format":"mp4","quality":0,"progress":0,
            "created":now,"batch_id":bid}
        module.batches[bid]={"id":bid,"state":"working","job_ids":[ready_id,queued_id],
            "format":"mp4","quality":0,"created":now}
        try:
            r=client.post("/api/batches/"+bid+"/stop")
            self.assertEqual(r.status_code,200,r.text)
            self.assertEqual(r.json()["state"],"stopping")
            self.assertEqual(r.json()["available"],1)
            self.assertEqual(r.json()["cancelled"],1)
            self.assertEqual(module.jobs[ready_id]["state"],"ready")
            self.assertEqual(module.jobs[queued_id]["state"],"cancelled")
            module.convert_batch(bid)
            final=client.get("/api/batches/"+bid).json()
            self.assertEqual(final["state"],"stopped")
            self.assertEqual(final["available"],1)
            self.assertEqual(client.post("/api/batches/"+bid+"/stop").status_code,200)
            zip_response=client.get(final["download_url"])
            self.assertEqual(zip_response.status_code,200)
            with zipfile.ZipFile(io.BytesIO(zip_response.content)) as archive:
                self.assertEqual(len([x for x in archive.namelist() if x.endswith(".mp4")]),1)
            self.assertEqual(module.jobs[ready_id]["state"],"downloaded")
        finally:
            module.batches.pop(bid,None)
            module.jobs.pop(ready_id,None)
            module.jobs.pop(queued_id,None)
            module.STORE.drop("batch",bid)
            module.STORE.drop("job",ready_id)
            module.STORE.drop("job",queued_id)
            shutil.rmtree(folder,ignore_errors=True)

    def test_stop_single_queued_job_is_idempotent(self):
        import uuid
        jid=uuid.uuid4().hex
        module.jobs[jid]={"id":jid,"state":"queued","video_id":V3,
            "format":"mp3","quality":0,"progress":0,"created":time.time()}
        try:
            r=client.post("/api/jobs/"+jid+"/stop")
            self.assertEqual(r.status_code,200,r.text)
            self.assertEqual(r.json()["state"],"cancelled")
            self.assertEqual(client.post("/api/jobs/"+jid+"/stop").json()["state"],"cancelled")
            self.assertFalse((module.MEDIA/jid).exists())
        finally:
            module.jobs.pop(jid,None)
            module.STORE.drop("job",jid)

    def test_low_storage_pauses_without_failed_videos_then_resumes(self):
        payload={"links":["https://youtu.be/"+V1,"https://youtu.be/"+V2],
                 "format":"mp4","quality":0,"rights_confirmed":True}
        with patch.object(module,"free_storage_mb",return_value=50):
            response=client.post("/api/batches",json=payload)
            self.assertEqual(response.status_code,202,response.text)
            bid=response.json()["id"]
            for _ in range(200):
                batch=client.get("/api/batches/"+bid).json()
                if batch["state"]=="paused":break
                time.sleep(.02)
            self.assertEqual(batch["state"],"paused",batch)
            self.assertEqual(batch["failed"],0,batch)
            self.assertEqual(batch["paused"],2,batch)
            low=client.post("/api/batches/"+bid+"/resume")
            self.assertEqual(low.status_code,409,low.text)
        with patch.object(module,"free_storage_mb",return_value=3000),patch.object(module,"convert",mock_conversion):
            resumed=client.post("/api/batches/"+bid+"/resume")
            self.assertEqual(resumed.status_code,200,resumed.text)
            complete=wait_batch(bid)
            self.assertEqual(complete["state"],"complete",complete)
            self.assertEqual(complete["succeeded"],2,complete)
            zipped=client.get(complete["download_url"]+"?max_total_mb=1500")
            self.assertEqual(zipped.status_code,200,zipped.text[:200])
            with zipfile.ZipFile(io.BytesIO(zipped.content)) as archive:
                self.assertIsNone(archive.testzip())
            self.assertEqual(client.get("/api/batches/"+bid).json()["available"],0)

    def test_partial_zip_download_frees_space_and_resumes_storage_failure(self):
        import uuid, shutil
        bid=uuid.uuid4().hex
        ready_id=uuid.uuid4().hex
        failed_id=uuid.uuid4().hex
        folder=module.MEDIA/ready_id
        folder.mkdir(parents=True,exist_ok=True)
        media=folder/"video.mp4"
        media.write_bytes(b"saved already"+b"x"*4000)
        now=time.time()
        module.jobs[ready_id]={"id":ready_id,"state":"ready","file":str(media),
            "title":"Previously converted","video_id":V1,"format":"mp4","quality":0,
            "created":now,"progress":100,"batch_id":bid}
        module.jobs[failed_id]={"id":failed_id,"state":"error",
            "title":"Storage interrupted","video_id":V2,"format":"mp4","quality":0,
            "created":now,"progress":0,"batch_id":bid,
            "error":"Not enough storage to finish the MP4 audio verification."}
        module.batches[bid]={"id":bid,"state":"partial",
            "job_ids":[ready_id,failed_id],"format":"mp4","quality":0,
            "created":now,"ended":now}
        try:
            with patch.object(module,"free_storage_mb",return_value=3000),patch.object(module,"convert",mock_conversion):
                response=client.get("/api/batches/"+bid+"/download?max_total_mb=1500")
                self.assertEqual(response.status_code,200,response.text[:100])
                with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                    self.assertIsNone(archive.testzip())
                    self.assertEqual(len([x for x in archive.namelist() if x.endswith(".mp4")]),1)
                finished=wait_batch(bid)
                self.assertEqual(finished["succeeded"],2,finished)
                self.assertEqual(finished["failed"],0,finished)
                self.assertEqual(module.jobs[ready_id]["state"],"downloaded")
                self.assertEqual(module.jobs[failed_id]["state"],"ready")
        finally:
            module.batches.pop(bid,None)
            module.jobs.pop(ready_id,None)
            module.jobs.pop(failed_id,None)
            module.STORE.drop("batch",bid)
            module.STORE.drop("job",ready_id)
            module.STORE.drop("job",failed_id)
            shutil.rmtree(folder,ignore_errors=True)
            shutil.rmtree(module.MEDIA/failed_id,ignore_errors=True)

    def test_downloading_old_batch_restarts_new_paused_batch(self):
        import uuid, shutil
        old_id=uuid.uuid4().hex
        new_id=uuid.uuid4().hex
        saved=uuid.uuid4().hex
        first=uuid.uuid4().hex
        second=uuid.uuid4().hex
        now=time.time()
        folder=module.MEDIA/saved
        folder.mkdir(parents=True,exist_ok=True)
        media=folder/"done.mp4"
        media.write_bytes(b"completed original"+b"x"*10000)
        module.jobs[saved]={"id":saved,"state":"ready","file":str(media),
            "title":"Already completed","video_id":V1,"format":"mp4","quality":0,
            "progress":100,"batch_id":old_id,"created":now}
        module.batches[old_id]={"id":old_id,"state":"partial","format":"mp4",
            "quality":0,"job_ids":[saved],"created":now}
        for jid,vid in ((first,V2),(second,V3)):
            module.jobs[jid]={"id":jid,"state":"paused","video_id":vid,
                "format":"mp4","quality":0,"created":now+1,
                "progress":0,"batch_id":new_id}
        module.batches[new_id]={"id":new_id,"state":"paused","format":"mp4",
            "quality":0,"job_ids":[first,second],"created":now+1}
        try:
            with patch.object(module,"free_storage_mb",return_value=3000),patch.object(module,"convert",mock_conversion):
                response=client.get("/api/batches/"+old_id+"/download?max_total_mb=1500")
                self.assertEqual(response.status_code,200,response.text[:100])
                with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                    self.assertIsNone(archive.testzip())
                resumed=wait_batch(new_id)
                self.assertEqual(resumed["state"],"complete",resumed)
                self.assertEqual(resumed["succeeded"],2,resumed)
                self.assertEqual(module.jobs[saved]["state"],"downloaded")
                self.assertFalse(media.exists())
        finally:
            for bid in (old_id,new_id):
                module.batches.pop(bid,None)
                module.STORE.drop("batch",bid)
            for jid in (saved,first,second):
                module.jobs.pop(jid,None)
                module.STORE.drop("job",jid)
                shutil.rmtree(module.MEDIA/jid,ignore_errors=True)

    def test_stop_a_paused_batch_without_erasing_finished_video(self):
        import uuid, shutil
        bid=uuid.uuid4().hex
        ready=uuid.uuid4().hex
        waiting=uuid.uuid4().hex
        directory=module.MEDIA/ready
        directory.mkdir(parents=True,exist_ok=True)
        media=directory/"ready.mp4"
        media.write_bytes(b"complete video"+b"x"*5000)
        now=time.time()
        module.jobs[ready]={"id":ready,"state":"ready","file":str(media),
            "video_id":V1,"format":"mp4","quality":0,"created":now,
            "progress":100,"batch_id":bid}
        module.jobs[waiting]={"id":waiting,"state":"paused","video_id":V2,
            "format":"mp4","quality":0,"created":now,"progress":0,"batch_id":bid}
        module.batches[bid]={"id":bid,"state":"paused","job_ids":[ready,waiting],
            "format":"mp4","quality":0,"created":now,"ended":now}
        try:
            response=client.post("/api/batches/"+bid+"/stop")
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()["state"],"stopped",response.json())
            self.assertEqual(response.json()["available"],1)
            self.assertEqual(module.jobs[ready]["state"],"ready")
            self.assertEqual(module.jobs[waiting]["state"],"cancelled")
            self.assertTrue(media.is_file())
        finally:
            module.batches.pop(bid,None)
            module.jobs.pop(ready,None)
            module.jobs.pop(waiting,None)
            module.STORE.drop("batch",bid)
            module.STORE.drop("job",ready)
            module.STORE.drop("job",waiting)
            shutil.rmtree(directory,ignore_errors=True)

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
        after=client.get("/api/batches/"+bid).json()
        self.assertEqual(after["succeeded"],2)
        self.assertEqual(after["available"],0)
        self.assertFalse(after["download_url"])
        self.assertTrue(all(item["state"]=="downloaded" for item in after["items"]))
        self.assertTrue(all(not (module.MEDIA/jid/"video.mp3").exists()
                            for jid in module.batches[bid]["job_ids"]))

    def test_single_folder_download_releases_media(self):
        with patch.object(module,"convert",mock_conversion):
            response=client.post("/api/jobs",json={
                "url":"https://youtu.be/"+V3,"format":"mp3",
                "rights_confirmed":True})
            self.assertEqual(response.status_code,202,response.text)
            jid=response.json()["id"]
            for _ in range(200):
                job=client.get("/api/jobs/"+jid).json()
                if job["state"] in ("ready","error"):break
                time.sleep(.02)
        self.assertEqual(job["state"],"ready")
        z=client.get(job["folder_url"])
        self.assertEqual(z.status_code,200)
        with zipfile.ZipFile(io.BytesIO(z.content)) as archive:
            self.assertIsNone(archive.testzip())
        self.assertEqual(client.get("/api/jobs/"+jid).json()["state"],"downloaded")
        self.assertFalse((module.MEDIA/jid).exists())

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
        self.assertEqual(client.get("/api/batches/"+bid).json()["available"],0)

    def test_new_batch_rejected_gracefully_when_storage_is_full(self):
        from types import SimpleNamespace
        before=len(module.jobs)
        with patch.object(module.shutil,"disk_usage",return_value=SimpleNamespace(free=0)):
            response=client.post("/api/batches",json={
                "links":["https://youtu.be/"+V1,"https://youtu.be/"+V2],
                "format":"mp4","rights_confirmed":True})
        self.assertEqual(response.status_code,503,response.text)
        self.assertIn("storage",response.text.lower())
        self.assertEqual(len(module.jobs),before)

    def test_in_progress_batch_stays_readable_and_downloadable_with_full_disk(self):
        # A full media volume must not break status polling or the ready files.
        import uuid
        bid=uuid.uuid4().hex
        jid=uuid.uuid4().hex
        waiting=uuid.uuid4().hex
        folder=module.MEDIA/jid
        folder.mkdir(mode=0o700,parents=True,exist_ok=True)
        media=folder/"saved.mp4"
        media.write_bytes(b"already converted"+b"x"*400)
        expected_media=media.read_bytes()
        module.jobs[jid]={
            "id":jid,"state":"ready","file":str(media),"title":"Saved video",
            "format":"mp4","video_id":V1,"quality":0,"progress":100,
            "created":time.time(),"batch_id":bid}
        module.jobs[waiting]={
            "id":waiting,"state":"queued","title":"Queued video","video_id":V2,
            "format":"mp4","quality":0,"progress":0,"created":time.time(),"batch_id":bid}
        module.batches[bid]={
            "id":bid,"state":"working","format":"mp4","quality":0,
            "job_ids":[jid,waiting],"message":"Converting","created":time.time()}
        try:
            with patch.object(module.shutil,"disk_usage",side_effect=OSError("disk full")):
                progress=client.get("/api/batches/"+bid)
                archive=client.get("/api/batches/"+bid+"/download")
            self.assertEqual(progress.status_code,200,progress.text)
            self.assertEqual(progress.json()["succeeded"],1)
            self.assertEqual(progress.json()["state"],"working")
            self.assertEqual(archive.status_code,200)
            with zipfile.ZipFile(io.BytesIO(archive.content)) as z:
                self.assertEqual(len([n for n in z.namelist() if n.endswith(".mp4")]),1)
                self.assertEqual(z.read([n for n in z.namelist() if n.endswith(".mp4")][0]),expected_media)
        finally:
            module.batches.pop(bid,None)
            module.jobs.pop(jid,None)
            module.jobs.pop(waiting,None)
            import shutil
            shutil.rmtree(folder,ignore_errors=True)

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
