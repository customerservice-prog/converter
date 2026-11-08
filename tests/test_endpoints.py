import unittest
from fastapi.testclient import TestClient
from app import app

client=TestClient(app)

class EndpointTests(unittest.TestCase):
    def test_homepage_and_pages(self):
        for path in ("/","/faq","/bookmarklet","/add-on","/thumbnail","/privacy","/terms","/copyright","/contact"):
            with self.subTest(path=path):
                r=client.get(path)
                self.assertEqual(r.status_code,200)
                self.assertIn("ClipConvert",r.text)

    def test_assets(self):
        self.assertEqual(client.get("/assets/main.js").status_code,200)
        self.assertEqual(client.get("/assets/style.css").status_code,200)

    def test_health(self):
        r=client.get("/api/health")
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()["status"],"ok")

    def test_rights_confirmation_is_required(self):
        r=client.post("/api/jobs",json={"url":"https://youtu.be/dQw4w9WgXcQ","format":"mp3","quality":192})
        self.assertEqual(r.status_code,400)
        self.assertIn("permission",r.text)

    def test_disallowed_hostname_does_not_start_job(self):
        r=client.post("/api/jobs",json={"url":"http://127.0.0.1/private","format":"mp3","quality":192,"rights_confirmed":True})
        self.assertEqual(r.status_code,400)

    def test_invalid_quality_rejected(self):
        r=client.post("/api/jobs",json={"url":"https://youtu.be/dQw4w9WgXcQ","format":"mp4","quality":320,"rights_confirmed":True})
        self.assertEqual(r.status_code,400)

    def test_nonexistent_download(self):
        self.assertEqual(client.get("/api/download/missing").status_code,404)

    def test_invalid_thumbnail(self):
        self.assertEqual(client.get("/api/thumbnail/not-an-id").status_code,400)

if __name__=="__main__":
    unittest.main()
