import io
import math
import struct
import time
import unittest
import wave
from fastapi.testclient import TestClient
from app import app, ConvertRequest, QUALITIES, youtube_output_options

client=TestClient(app)


def tone():
    buf=io.BytesIO()
    with wave.open(buf,"wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(44100)
        samples=b"".join(struct.pack("<h",int(5000*math.sin(2*math.pi*440*i/44100))) for i in range(44100))
        f.writeframes(samples)
    return buf.getvalue()


def complete_job(jid):
    for _ in range(150):
        state=client.get("/api/jobs/"+jid).json()
        if state["state"] in ("ready","error"):
            return state
        time.sleep(.1)
    raise AssertionError("Job never completed")


class QualityTests(unittest.TestCase):
    def test_api_defaults_to_auto(self):
        self.assertEqual(ConvertRequest(url="https://youtu.be/NY6acnscmwo").quality,0)
        self.assertIn(0,QUALITIES["mp3"])
        self.assertIn(0,QUALITIES["mp4"])

    def test_auto_youtube_is_not_resolution_capped(self):
        options=youtube_output_options("mp4",0)
        self.assertEqual(options["format"],"bestvideo+bestaudio/best")
        self.assertNotIn("height<=",options["format"])
        self.assertEqual(options["merge_output_format"],"mp4")
        self.assertIn("res",options["format_sort"])

    def test_auto_mp3_uses_best_source_and_320_kbps_output(self):
        options=youtube_output_options("mp3",0)
        self.assertEqual(options["format"],"bestaudio/best")
        self.assertEqual(options["postprocessors"][0]["preferredquality"],"320")

    def test_manual_cap_still_available(self):
        manual=youtube_output_options("mp4",720)
        self.assertIn("height<=720",manual["format"])
        self.assertNotIn("height<=1080",manual["format"])
        self.assertEqual(youtube_output_options("mp3",128)["postprocessors"][0]["preferredquality"],"128")

    def test_actual_quality_reported_for_auto_mp3_upload(self):
        response=client.post(
            "/api/upload",data={"format":"mp3","rights_confirmed":"true"},
            files={"file":("tone.wav",tone(),"audio/wav")})
        self.assertEqual(response.status_code,202,response.text)
        state=complete_job(response.json()["id"])
        self.assertEqual(state["state"],"ready",state)
        self.assertEqual(state["quality"],0)
        self.assertIn("kbps",state["actual_quality"])
        self.assertGreaterEqual(int(state["actual_quality"].split()[0]),300)
        download=client.get(state["download_url"])
        self.assertEqual(download.status_code,200)
        self.assertGreater(len(download.content),10000)


if __name__=="__main__":
    unittest.main()
