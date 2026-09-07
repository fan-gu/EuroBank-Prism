"""Smoke-test the deployed Streamlit entry point."""

from pathlib import Path
import unittest

from streamlit.testing.v1 import AppTest


class StreamlitAppTests(unittest.TestCase):
    def test_dashboard_renders_waterfall_homepage_without_exception(self):
        app_path = Path(__file__).resolve().parent.parent / "streamlit_app.py"
        app = AppTest.from_file(str(app_path), default_timeout=30).run()
        self.assertEqual(app.exception, [])
        headings = [item.value for item in app.header] + [item.value for item in app.subheader]
        for expected in (
            "Core signal map",
            "Investment Groups",
            "Opportunities and risk queue",
            "Relative ranking",
            "One-bank research snapshot",
            "Language drift and governance gate",
        ):
            self.assertIn(expected, headings)
        self.assertGreaterEqual(len(app.dataframe), 2)


if __name__ == "__main__":
    unittest.main()
