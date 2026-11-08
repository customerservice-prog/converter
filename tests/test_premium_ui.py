"""Presentation regression checks for the premium ClipConvert redesign.

These assertions verify that a visual redesign does not remove API-bound controls.
"""
import unittest
from html.parser import HTMLParser
from pathlib import Path

from fastapi.testclient import TestClient
from app import app

ROOT = Path(__file__).resolve().parents[1]
client = TestClient(app)

REQUIRED_IDS = {
    "videoUrl", "pasteButton", "quality", "rightsCheck", "convertForm",
    "convertButton", "youtubeSourceButton", "batchSourceButton", "fileSourceButton",
    "batchUrls", "batchCount", "batchPasteButton", "batchPanel", "batchRows",
    "batchDownload", "batchReset", "uploadInput", "uploadFileName",
    "jobPanel", "jobTitle", "jobStatus", "jobDetail", "jobThumbnail",
    "progressTrack", "downloadButton", "folderDownload", "resetButton",
    "uploadFallbackButton", "mobileMenu", "copyrightYear",
}


class ElementCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.links = []
        self.buttons = []

    def handle_starttag(self, tag, attrs):
        props = dict(attrs)
        if "id" in props:
            self.ids.append(props["id"])
        if tag == "link":
            self.links.append(props)
        if tag == "button":
            self.buttons.append(props)


class PremiumSiteTests(unittest.TestCase):
    def test_new_theme_is_served_by_live_page_route(self):
        result = client.get("/")
        self.assertEqual(result.status_code, 200)
        self.assertIn('class="premium-ui"', result.text)
        self.assertIn("/assets/premium.css", result.text)
        self.assertIn("Your media. Your format.", result.text)
        self.assertIn("Made effortless.", result.text)
        self.assertIn("YOUR CONVERSION STUDIO", result.text)

    def test_all_core_converter_elements_still_exist(self):
        result = client.get("/")
        parser = ElementCollector()
        parser.feed(result.text)
        ids = set(parser.ids)
        self.assertFalse(set(REQUIRED_IDS) - ids, "Missing existing controls: " + str(REQUIRED_IDS - ids))
        self.assertEqual(len(parser.ids), len(ids), "Duplicate HTML ID found")
        self.assertTrue(any(x.get("rel") == "stylesheet" and
                            x.get("href") == "/assets/premium.css" for x in parser.links))

    def test_layout_styles_include_accessibility_and_mobile(self):
        result = client.get("/assets/premium.css")
        self.assertEqual(result.status_code, 200)
        content = result.text
        for selector in (".source-tab", ".converter-card", ".steps", ".feature-strip",
                         ".footer-inner", ".batch-result", ".secondary-page",
                         "@media (max-width:560px)", "prefers-reduced-motion",
                         ":focus-visible"):
            with self.subTest(selector=selector):
                self.assertIn(selector, content)

    def test_js_functions_and_source_modes_unchanged(self):
        script = (ROOT / "static/main.js").read_text()
        for value in ('fetch("/api/jobs"', 'fetch("/api/batches"', 'fetch("/api/upload"',
                      'updateBatchPanel', 'updateProgress(data)', 'setSource("batch")',
                      'setSource("file")'):
            with self.subTest(value=value):
                self.assertIn(value, script)

    def test_secondary_pages_keep_same_shell(self):
        for path in ("/faq", "/add-on", "/bookmarklet", "/contact",
                     "/thumbnail", "/terms", "/copyright", "/privacy"):
            with self.subTest(path=path):
                result = client.get(path)
                self.assertEqual(result.status_code, 200)
                self.assertIn("/assets/premium.css", result.text)
                self.assertIn('id="secondaryPage"', result.text)


if __name__ == "__main__":
    unittest.main()
