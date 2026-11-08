import os
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
import app as module
from durable import StateStore

client=TestClient(module.app)


class PersistentStorageTests(unittest.TestCase):
    def test_record_survives_store_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"state.sqlite3"
            one=StateStore(path)
            payload={"id":"123","state":"working","progress":42,"title":"Preserved work"}
            one.put("job","123",payload)
            one.put("batch","abc",{"job_ids":["123"],"state":"working"})
            two=StateStore(path)
            self.assertEqual(two.load("job")["123"],payload)
            self.assertEqual(two.load("batch")["abc"]["job_ids"],["123"])
            two.drop("job","123")
            self.assertNotIn("123",StateStore(path).load("job"))

    def test_contact_messages_are_persisted(self):
        response=client.post("/api/contact",json={
            "name":"Test Visitor","email":"visitor@example.org",
            "message":"The conversion returned an error while processing."})
        self.assertEqual(response.status_code,200,response.text)
        self.assertTrue(response.json()["received"])
        self.assertTrue(response.json()["reference"])
        messages=module.STORE.messages()
        self.assertTrue(any(x["email"]=="visitor@example.org" and
                           x["message"].startswith("The conversion returned")
                           for x in messages))
        self.assertTrue(any(not x["emailed"] for x in messages))

    def test_private_inbox_is_not_public(self):
        with patch.dict(os.environ,{"ADMIN_TOKEN":"a-very-private-test-token"}):
            denied=client.get("/api/admin/contacts")
            self.assertEqual(denied.status_code,401)
            also_denied=client.get("/api/admin/contacts",
                                   headers={"X-Admin-Token":"wrong"})
            self.assertEqual(also_denied.status_code,401)
            allowed=client.get("/api/admin/contacts",
                               headers={"X-Admin-Token":"a-very-private-test-token"})
            self.assertEqual(allowed.status_code,200)
            self.assertIn("messages",allowed.json())
            overview=client.get("/api/admin/overview",
                                headers={"X-Admin-Token":"a-very-private-test-token"})
            self.assertEqual(overview.status_code,200)
            self.assertTrue(overview.json()["durable"])

    def test_retry_requeues_failed_video_and_persists_it(self):
        jid=uuid.uuid4().hex
        job={"id":jid,"state":"error","video_id":"NY6acnscmwo",
             "title":"Mock","format":"mp3","quality":0,
             "created":time.time(),"error":"Test failure","retry_count":0}
        with module.mutex:
            module.jobs[jid]=job
            module.STORE.put("job",jid,job)
        try:
            # Keep this unit test offline: don't start the actual download thread.
            with patch.object(module.threading,"Thread") as thread:
                answer=client.post("/api/jobs/"+jid+"/retry")
                self.assertEqual(answer.status_code,202,answer.text)
                thread.return_value.start.assert_called_once()
            self.assertEqual(module.jobs[jid]["state"],"queued")
            self.assertEqual(module.jobs[jid]["retry_count"],1)
            self.assertEqual(StateStore(module.STORE.path).load("job")[jid]["state"],"queued")
        finally:
            with module.mutex:
                module.jobs.pop(jid,None)
                module.STORE.drop("job",jid)


class SearchAndSecurityTests(unittest.TestCase):
    def test_robots_and_sitemap(self):
        robots=client.get("/robots.txt")
        self.assertEqual(robots.status_code,200)
        self.assertIn("Disallow: /admin",robots.text)
        sitemap=client.get("/sitemap.xml")
        self.assertEqual(sitemap.status_code,200)
        self.assertIn("<urlset",sitemap.text)
        self.assertIn("/faq</loc>",sitemap.text)

    def test_per_page_metadata(self):
        home=client.get("/")
        faq=client.get("/faq")
        self.assertEqual(home.status_code,200)
        self.assertEqual(faq.status_code,200)
        self.assertIn("ClipConvert — YouTube to MP3 &amp; MP4",home.text)
        self.assertIn("Frequently asked questions — ClipConvert",faq.text)
        self.assertIn('rel="canonical" href="https://clipconvert-web-production.up.railway.app/faq"',faq.text)
        self.assertNotIn('rel="canonical" href="https://clipconvert-web-production.up.railway.app/"',faq.text)

    def test_admin_page_not_indexed(self):
        response=client.get("/admin")
        self.assertEqual(response.status_code,200)
        self.assertIn("Private operator dashboard",response.text)
        self.assertIn("noindex",response.headers.get("x-robots-tag",""))

    def test_web_security_headers(self):
        r=client.get("/api/health")
        self.assertIn("object-src 'none'",r.headers["content-security-policy"])
        self.assertEqual(r.headers["x-content-type-options"],"nosniff")
        self.assertIn("no-store",r.headers.get("cache-control",""))
        self.assertTrue(r.json()["storage_ready"])

    def test_history_and_retry_controls_stay_in_ui(self):
        r=client.get("/")
        self.assertEqual(r.status_code,200)
        for key in ("historySection","historyList","historyClear",
                    "retryVideoButton","batchRetry"):
            self.assertIn('id="'+key+'"',r.text)
        js=client.get("/assets/main.js").text
        self.assertIn("localStorage",js)
        self.assertIn('"/retry"',js)


if __name__=="__main__":
    unittest.main()
