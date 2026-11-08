import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from app import ensure_mp4_audio, mp4_audio_info

FFMPEG=bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def run(args):
    return subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                          text=True,timeout=45,check=True)


def generate_clip(path:Path,codec:str="libopus",with_audio:bool=True):
    cmd=["ffmpeg","-nostdin","-hide_banner","-loglevel","error","-y",
         "-f","lavfi","-i","testsrc=size=160x90:rate=12"]
    if with_audio:
        cmd+=["-f","lavfi","-i","sine=frequency=660:sample_rate=48000"]
    cmd+=["-t","2","-c:v","libx264","-pix_fmt","yuv420p"]
    if with_audio:
        cmd+=["-c:a",codec,"-shortest"]
    else:
        cmd+=["-an"]
    cmd.append(str(path))
    run(cmd)


def video_hash(path:Path):
    result=subprocess.run(
        ["ffmpeg","-nostdin","-hide_banner","-loglevel","error",
         "-i",str(path),"-map","0:v:0","-c:v","copy","-f","md5","-"],
        capture_output=True,text=True,check=True,timeout=30)
    return result.stdout.strip()


@unittest.skipUnless(FFMPEG,"ffmpeg and ffprobe required")
class Mp4AudioTests(unittest.TestCase):
    def test_opus_audio_is_repaired_to_aac_without_changing_video(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"opus.mp4"
            generate_clip(path,"libopus")
            self.assertEqual(mp4_audio_info(path)["codec_name"],"opus")
            before_video=video_hash(path)
            result=ensure_mp4_audio(path)
            self.assertEqual(result["audio_codec"],"aac")
            self.assertEqual(result["audio_channels"],2)
            self.assertEqual(mp4_audio_info(path)["codec_name"],"aac")
            self.assertEqual(video_hash(path),before_video,"Video stream must be unchanged")
            # Ensure there is actual decoded non-zero audio, not just a metadata track.
            decoded=subprocess.run(
                ["ffmpeg","-nostdin","-hide_banner","-v","error","-i",str(path),
                 "-map","0:a:0","-t","1","-f","s16le","-ac","1","-ar","16000","-"],
                capture_output=True,check=True,timeout=30)
            self.assertGreater(len(decoded.stdout),16000)
            self.assertNotEqual(set(decoded.stdout),{0})

    def test_aac_audio_is_fast_path_and_does_not_recompress(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"aac.mp4"
            generate_clip(path,"aac")
            original=hashlib.sha256(path.read_bytes()).digest()
            result=ensure_mp4_audio(path)
            self.assertEqual(result["audio_codec"],"aac")
            self.assertIn(result["audio_channels"],(1,2))
            self.assertEqual(hashlib.sha256(path.read_bytes()).digest(),original)

    def test_missing_audio_track_is_rejected_instead_of_silent_download(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"silent.mp4"
            generate_clip(path,with_audio=False)
            with self.assertRaisesRegex(ValueError,"no audio track"):
                ensure_mp4_audio(path)


if __name__=="__main__":
    unittest.main()
