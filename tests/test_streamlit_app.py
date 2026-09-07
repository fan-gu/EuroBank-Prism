"""Smoke-test the deployed Streamlit entry point."""

from pathlib import Path
import unittest

from streamlit.testing.v1 import AppTest


class StreamlitAppTests(unittest.TestCase):
    def test_dashboard_renders_investment_groups_without_exception(self):
        app_path = Path(__file__).resolve().parent.parent / "streamlit_app.py"
        app = AppTest.from_file(str(app_path), default_timeout=30).run()
        self.assertEqual(app.exception, [])
        self.assertIn("Investment Groups", [item.value for item in app.subheader])
        self.assertGreaterEqual(len(app.dataframe), 2)


if __name__ == "__main__":
    unittest.main()
