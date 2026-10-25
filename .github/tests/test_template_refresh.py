"""A retained old PVE release must never count as a newly validated build."""
from contextlib import redirect_stderr
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import refresh_pve_template as refresh


class TemplateRefreshTests(unittest.TestCase):
    def test_arm_sources_cannot_select_amd64_or_cloud_templates(self):
        releases=[{'version':'24.03','release':'24.03'}]
        names=['openeuler_24.03_24.03_'+suffix+'.tar.xz' for suffix in
               ['amd64_default','x86_64_default','arm64_default','aarch64_default','arm64_cloud']]
        assets=[dict(name=name,state='uploaded',size=1024,updated_at='2026-10-25T07:00:00Z') for name in names]
        assets[2]['updated_at']='2026-10-25T08:00:00Z'
        self.assertEqual(refresh.source_configuration('arm64')[0], 'oneclickvirt/lxc_arm_images')
        chosen=refresh.select_candidates(assets,releases,'openeuler','default','arm64')
        self.assertEqual([a['name'] for a in chosen], ['openeuler_24.03_24.03_arm64_default.tar.xz'])
        chosen=refresh.select_candidates(assets,releases,'openeuler','default','amd64')
        self.assertEqual(len(chosen),1)
        self.assertIn(chosen[0]['name'],names[:2])

    def test_arm_request_rejects_amd64_worker_before_reading_sources(self):
        with mock.patch.object(sys,'argv',['refresh','openeuler','--arch','arm64']), \
             mock.patch.object(refresh.platform,'machine',return_value='x86_64'), \
             mock.patch.object(refresh,'Publisher') as source:
            with self.assertRaisesRegex(RuntimeError,'native arm64'):
                refresh.main()
            source.assert_not_called()

    def test_default_refresh_keeps_amd64_source(self):
        self.exercise_native_refresh('amd64','x86_64',[])

    def test_arm_refresh_selects_arm_catalog_release(self):
        self.exercise_native_refresh('arm64','aarch64',['--arch','arm64','--release','24.03'])

    def exercise_native_refresh(self,architecture,machine,options):
        import base64
        catalog={'distros':{'openeuler':{'architectures':['amd64','arm64'],
                 'releases':[{'version':'24.03','release':'24.03'}]}}}
        asset=dict(name=f'openeuler_24.03_24.03_{architecture}_default.tar.xz',state='uploaded',
                   size=100,updated_at='2026-10-25T08:00:00Z')
        source=mock.Mock()
        source.base='/repos/'+refresh.source_configuration(architecture)[0]
        source.request.side_effect=[{'id':1},{'content':base64.b64encode(json.dumps(catalog).encode()).decode()}]
        source.assets.return_value={asset['name']:asset}
        def accept_candidates(candidates,process):
            self.assertEqual([a['name'] for a in candidates],[asset['name']])
            return [f'openeuler_24.03_24.03_{architecture}_default_20261025_{architecture}.tar.zst']
        with mock.patch.object(sys,'argv',['refresh','openeuler',*options]), \
             mock.patch.object(refresh.platform,'machine',return_value=machine), \
             mock.patch.dict(refresh.os.environ,{'GH_TOKEN':'fixture'}), \
             mock.patch.object(refresh,'Publisher',return_value=source) as factory, \
             mock.patch.object(refresh,'process_candidates',side_effect=accept_candidates), \
             mock.patch.object(refresh,'publish_outputs') as publish:
            refresh.main()
            factory.assert_called_once_with(refresh.source_configuration(architecture)[0],'fixture')
            self.assertTrue(publish.call_args.args[0][0].endswith('_'+architecture+'.tar.zst'))

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
