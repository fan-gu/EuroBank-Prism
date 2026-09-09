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
        self.assertIn("Signal map", headings)
        for section_name in (
            "Investment groups",
            "Research triage",
            "Semantic research",
            "Relative ranking",
            "Research readiness",
            "Bank research",
            "Sources & evidence",
            "Methodology",
        ):
            self.assertTrue(any(heading.endswith(section_name) for heading in headings))
        self.assertEqual(len(app.tabs), 0)
        self.assertGreaterEqual(len(app.dataframe), 2)


if __name__ == "__main__":
    unittest.main()
