from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Stylesheets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "link" and attributes.get("rel") == "stylesheet":
            self.hrefs.append(attributes.get("href", ""))


class ScrollbarContractTests(unittest.TestCase):
    def test_all_page_shells_load_shared_scrollbar_styles(self):
        for name in ("base.html", "react_base.html", "login.html"):
            with self.subTest(template=name):
                parser = Stylesheets()
                parser.feed((ROOT / "app/templates" / name).read_text(encoding="utf-8"))
                self.assertTrue(any(href.startswith("/static/scrollbars.css?v=") for href in parser.hrefs))

    def test_shared_styles_keep_theme_tokens_and_accessibility_escape(self):
        css = (ROOT / "app/static/scrollbars.css").read_text(encoding="utf-8")
        for rule in ("color-scheme: dark", "var(--border,", "::-webkit-scrollbar-button", "forced-colors: active"):
            self.assertIn(rule, css)
        command = (ROOT / "frontend/src/components/ui/command.tsx").read_text(encoding="utf-8")
        self.assertNotIn("no-scrollbar", command)
