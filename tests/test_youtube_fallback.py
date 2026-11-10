import unittest
from unittest.mock import patch
import yt_dlp

from app import fetch_public_video_info, youtube_access_challenge


class FakeExtractor:
    calls=[]
    def __init__(self,options):
        self.options=options
    def __enter__(self):
        return self
    def __exit__(self,*args):
        return False
    def extract_info(self,url,download=False):
        self.calls.append((self.options.get("source_address"),
                           self.options.get("extractor_args")))
        if self.options.get("source_address")=="::":
            raise yt_dlp.utils.DownloadError("Sign in to confirm you're not a bot")
        return {"title":"Public test video","duration":50,"id":"NY6acnscmwo"}


class BrokenExtractor(FakeExtractor):
    def extract_info(self,url,download=False):
        raise yt_dlp.utils.DownloadError("This video is private")


class PublicClientFallbackTests(unittest.TestCase):
    def setUp(self):
        FakeExtractor.calls=[]

    def test_ip_family_fallback_after_public_access_challenge(self):
        with patch("app.yt_dlp.YoutubeDL",FakeExtractor), \
             patch("app.time.sleep",return_value=None):
            info,kwargs=fetch_public_video_info("https://www.youtube.com/watch?v=NY6acnscmwo",
                {"source_address":"::","no_warnings":True},"mp4",0)
        self.assertEqual(info["title"],"Public test video")
        self.assertEqual(kwargs["source_address"],"0.0.0.0")
        self.assertEqual(len(FakeExtractor.calls),3)
        self.assertEqual([x[0] for x in FakeExtractor.calls],["::","::","0.0.0.0"])
        self.assertTrue(FakeExtractor.calls[1][1])

    def test_no_retry_for_private_or_non_public_video(self):
        with patch("app.yt_dlp.YoutubeDL",BrokenExtractor):
            with self.assertRaises(yt_dlp.utils.DownloadError):
                fetch_public_video_info("https://www.youtube.com/watch?v=NY6acnscmwo",
                    {"source_address":"::"},"mp3",0)

    def test_access_reason_classification(self):
        self.assertTrue(youtube_access_challenge(Exception("Sign in to confirm you're not a bot")))
        self.assertFalse(youtube_access_challenge(Exception("This video is private")))
        self.assertFalse(youtube_access_challenge(Exception("File is too large")))


if __name__=="__main__":
    unittest.main()
