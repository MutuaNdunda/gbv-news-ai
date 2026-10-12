"""Run the browser handler unit tests as part of the full offline suite."""
from pathlib import Path
import shutil
import subprocess
import unittest


class BulkValidationJavaScriptTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is needed for JavaScript handler tests')
    def test_inline_keyboard_lazy_body_save_and_draft_lifecycle(self):
        result = subprocess.run([shutil.which('node'), '--test', str(
            Path(__file__).parent / 'js' / 'validation_bulk.test.cjs')],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
