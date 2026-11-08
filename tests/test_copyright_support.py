"""Rights reporting, private triage and deferred email delivery tests."""
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


class CopyrightSupportTests(unittest.TestCase):
    def setUp(self):
        self.client=TestClient(module.app)
        self.unique="test-"+uuid.uuid4().hex
        self.identity=patch.object(module,"client_key",return_value=self.unique)
        self.identity.start()
        self.addCleanup(self.identity.stop)

    @staticmethod
    def valid_notice():
        return {
            "name":"Example Rights Holder","email":"rights@example.org",
            "work":"Original composition distributed by the author",
            "material_url":"https://youtube.com/watch?v=NY6acnscmwo",
            "details":"This specific material appears to contain a recording without authorization.",
            "signature":"Example Rights Holder",
            "good_faith":True,"accuracy":True
        }

    def test_requires_affirmations(self):
        notice=self.valid_notice()
        notice["good_faith"]=False
        with patch.object(module,"mail_configured",return_value=False):
            result=self.client.post("/api/copyright/report",json=notice)
        self.assertEqual(result.status_code,400)
        self.assertIn("good-faith",result.text.lower())

    def test_rejects_non_web_material_url(self):
        notice=self.valid_notice()
        notice["material_url"]="file:///etc/passwd"
        with patch.object(module,"mail_configured",return_value=False):
            result=self.client.post("/api/copyright/report",json=notice)
        self.assertEqual(result.status_code,400)

    def test_copyright_submission_is_privately_queued(self):
        notice=self.valid_notice()
        with patch.object(module,"mail_configured",return_value=False):
            result=self.client.post("/api/copyright/report",json=notice)
        self.assertEqual(result.status_code,200,result.text)
        ref=result.json()["reference"]
        self.assertEqual(len(ref),8)
        stored=[x for x in module.STORE.messages()
                if x["id"].startswith(ref)]
        self.assertEqual(len(stored),1)
        self.assertEqual(stored[0]["category"],"copyright")
        self.assertEqual(stored[0]["status"],"new")
        self.assertFalse(stored[0]["emailed"])
        self.assertIn("Electronic signature:",stored[0]["message"])

    def test_admin_can_triage_a_contact_but_public_cannot(self):
        key="private-unit-test-operator-key"
        msg_id=uuid.uuid4().hex
        payload={"name":"Example","email":"example@example.org","message":"Request for review",
                 "category":"support","status":"new","created":time.time(),"emailed":False}
        module.STORE.put("contact",msg_id,payload)
        try:
            self.assertEqual(self.client.patch("/api/admin/contacts/"+msg_id,
                json={"status":"reviewed"}).status_code,503 if not os.getenv("ADMIN_TOKEN") else 401)
            with patch.dict(os.environ,{"ADMIN_TOKEN":key}):
                result=self.client.patch("/api/admin/contacts/"+msg_id,json={"status":"reviewed"},
                    headers={"X-Admin-Token":key})
                self.assertEqual(result.status_code,200,result.text)
                self.assertEqual(module.STORE.load("contact")[msg_id]["status"],"reviewed")
                self.assertEqual(self.client.patch("/api/admin/contacts/"+msg_id,
                    json={"status":"nonsense"},headers={"X-Admin-Token":key}).status_code,422)
        finally:
            module.STORE.drop("contact",msg_id)

    def test_mail_requirements_do_not_claim_ready_without_smtp_key(self):
        with patch.dict(os.environ,{"CONTACT_EMAIL":"support@example.org",
                "SMTP_HOST":"smtp.resend.com","SMTP_FROM":"notifications@example.org",
                "SMTP_USER":"resend","SMTP_PASSWORD":""}):
            self.assertFalse(module.mail_configured())
        with patch.dict(os.environ,{"CONTACT_EMAIL":"support@example.org",
                "SMTP_HOST":"smtp.resend.com","SMTP_FROM":"notifications@example.org",
                "SMTP_USER":"resend","SMTP_PASSWORD":"unit-test-secret"}):
            self.assertTrue(module.mail_configured())

    def test_unsent_contact_is_retried_without_sending_twice(self):
        with tempfile.TemporaryDirectory() as root:
            fake=StateStore(Path(root)/"state.sqlite3")
            msg_id=uuid.uuid4().hex
            fake.put("contact",msg_id,{
                "name":"Example","email":"example@example.org","message":"Test support request",
                "category":"support","status":"new","created":time.time(),"emailed":False})
            with patch.object(module,"STORE",fake), \
                 patch.object(module,"mail_configured",return_value=True), \
                 patch.object(module,"deliver_message",return_value=True) as patch_send:
                module.flush_contact_notifications()
                self.assertTrue(fake.load("contact")[msg_id]["emailed"])
                self.assertEqual(patch_send.call_count,1)
                module.flush_contact_notifications()
                self.assertEqual(patch_send.call_count,1)

    def test_copyright_ui_and_realistic_disclosures(self):
        js=self.client.get("/assets/main.js")
        self.assertEqual(js.status_code,200)
        for fragment in ("copyrightForm","rightsGoodFaith","rightsAccuracy",
                         "/api/copyright/report","up to 90 days",
                         "not</strong> a representation","privacy"):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment,js.text)


if __name__=="__main__":
    unittest.main()
