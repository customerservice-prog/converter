import unittest
from app import video_id, source_url, QUALITIES

V="dQw4w9WgXcQ"
class ValidationTests(unittest.TestCase):
    def test_supported(self):
        for s in ("https://www.youtube.com/watch?v="+V,"https://youtu.be/"+V,
                  "https://youtube.com/shorts/"+V,"https://youtube.com/live/"+V,
                  "https://youtube.com/embed/"+V,V):
            with self.subTest(s=s): self.assertEqual(video_id(s),V)
    def test_rejected(self):
        for s in ("https://youtube.com.evil.com/watch?v="+V,"http://127.0.0.1/",
                  "file:///etc/passwd","https://youtube.com/watch?v=xyz",
                  "https://youtube.com/playlist?list=abc"):
            with self.subTest(s=s):
                with self.assertRaises(ValueError): video_id(s)
    def test_facebook_public_urls(self):
        url="https://www.facebook.com/watch/?v=1632760975048127"
        for link in ("https://www.facebook.com/reel/1632760975048127",
                     "https://m.facebook.com/videos/1632760975048127",
                     url, "https://facebook.com/watch?v=1632760975048127",
                     "https://www.facebook.com/video.php?v=1632760975048127"):
            with self.subTest(link=link): self.assertEqual(source_url(link),url)

    def test_facebook_share_reel_url(self):
        self.assertEqual(source_url("https://www.facebook.com/share/r/1F9Qrxnahp/"),
                         "https://www.facebook.com/share/r/1F9Qrxnahp/")

    def test_facebook_rejects_unsafe_urls(self):
        for link in ("https://facebook.com.evil.test/reel/1234",
                     "http://127.0.0.1/",
                     "https://www.facebook.com/groups/123",
                     "https://www.facebook.com/login",
                     "https://user:pass@www.facebook.com/reel/123",
                     "https://www.facebook.com:8080/reel/123",
                     "file:///etc/passwd"):
            with self.subTest(link=link):
                with self.assertRaises(ValueError): source_url(link)

    def test_formats(self):
        self.assertIn(192,QUALITIES["mp3"])
        self.assertIn(720,QUALITIES["mp4"])
        self.assertNotIn(320,QUALITIES["mp4"])
if __name__=="__main__": unittest.main()
