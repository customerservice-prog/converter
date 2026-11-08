import unittest
from app import video_id, QUALITIES

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
    def test_formats(self):
        self.assertIn(192,QUALITIES["mp3"])
        self.assertIn(720,QUALITIES["mp4"])
        self.assertNotIn(320,QUALITIES["mp4"])
if __name__=="__main__": unittest.main()
