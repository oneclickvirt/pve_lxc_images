"""A retained old PVE release must never count as a newly validated build."""
from contextlib import redirect_stderr
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import refresh_pve_template as refresh


class TemplateRefreshTests(unittest.TestCase):
    def test_failed_candidates_are_isolated_but_zero_accepted_cannot_publish(self):
        candidates = [{'name': 'broken'}, {'name': 'complete'}]
        def process(asset):
            if asset['name'] == 'broken':
                raise RuntimeError('guest did not boot')
            return Path('complete.tar.zst')
        with redirect_stderr(io.StringIO()):
            outputs = refresh.process_candidates(candidates, process)
        self.assertEqual(outputs, ['complete.tar.zst'])
        with mock.patch.object(refresh.subprocess, 'run') as publish:
            refresh.publish_outputs(outputs)
            publish.assert_called_once()
        with redirect_stderr(io.StringIO()):
            outputs = refresh.process_candidates(candidates[:1], process)
        with mock.patch.object(refresh.subprocess, 'run') as publish:
            with self.assertRaisesRegex(RuntimeError, 'No maintained PVE templates passed'):
                refresh.publish_outputs(outputs)
            publish.assert_not_called()

    def test_publisher_failure_remains_a_failed_refresh(self):
        with mock.patch.object(refresh.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, ['publisher'])):
            with self.assertRaises(subprocess.CalledProcessError):
                refresh.publish_outputs(['complete.tar.zst'])


if __name__ == '__main__':
    unittest.main()
