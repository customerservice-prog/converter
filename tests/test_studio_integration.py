import io, os, subprocess, tempfile, time, unittest
from pathlib import Path
from fastapi.testclient import TestClient
from app import app

class StudioIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client=TestClient(app)
        cls.tmp=tempfile.TemporaryDirectory()
        cls.video=Path(cls.tmp.name)/"test.mp4"
        subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",
                        "-f","lavfi","-i","color=c=blue:s=320x180:r=12",
                        "-f","lavfi","-i","sine=frequency=440:sample_rate=44100",
                        "-t","1","-c:v","libx264","-pix_fmt","yuv420p",
                        "-c:a","aac",str(cls.video)],check=True,timeout=30)
    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
    def test_permission_required(self):
        response=self.client.post("/api/studio/render",
            files={"video":("sample.mp4",self.video.read_bytes(),"video/mp4")})
        self.assertEqual(response.status_code,400)
    def test_private_render_and_download(self):
        response=self.client.post("/api/studio/render",
            files={"video":("sample.mp4",self.video.read_bytes(),"video/mp4")},
            data={"rights_confirmed":"true","mode":"fit","duration":"1"})
        self.assertEqual(response.status_code,202,response.text)
        job=response.json()
        self.assertEqual(self.client.get("/api/studio/jobs/"+job["id"]).status_code,422)
        for _ in range(90):
            status=self.client.get(job["status_url"])
            self.assertEqual(status.status_code,200)
            state=status.json()["state"]
            if state in ("ready","error"): break
            time.sleep(1)
        self.assertEqual(state,"ready",status.text)
        url=status.json()["download_url"]
        self.assertEqual(self.client.get(url.split("?")[0]+"?token=bad").status_code,404)
        result=self.client.get(url)
        self.assertEqual(result.status_code,200)
        self.assertTrue(result.content.startswith(b"\\x00\\x00"))
        self.assertGreater(len(result.content),1000)
if __name__=="__main__":unittest.main()
