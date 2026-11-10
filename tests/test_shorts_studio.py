import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from shorts_studio import render_short

class ShortsStudioTests(unittest.TestCase):
    def test_rejects_missing_source(self):
        with self.assertRaises(ValueError):
            render_short("/missing/source.mp4", "/tmp/out.mp4")
    def test_rejects_invalid_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/"in.mp4"
            src.write_bytes(b"example")
            with self.assertRaises(ValueError):
                render_short(str(src),str(Path(tmp)/"out.mp4"),mode="invalid")
    def test_rejects_overwriting_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/"in.mp4"
            src.write_bytes(b"example")
            with self.assertRaises(ValueError):
                render_short(str(src),str(src))
    def test_rejects_unsafe_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/"in.mp4"
            src.write_bytes(b"example")
            with self.assertRaises(ValueError):
                render_short(str(src),str(Path(tmp)/"out.mp4"),title="hi\\nbye")
if __name__=="__main__":
    unittest.main()
