"""Exercise both compressed formats using real safe and inherited-key archives."""
import io
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from verify_template_identity import verify_template_identity


class TemplateIdentityTests(unittest.TestCase):
    def test_mislabelled_executable_is_rejected_before_publication(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'openeuler_arm64_default.tar.xz'
            for architecture,machine in [('amd64',62),('arm64',183)]:
                header=bytearray(64)
                header[:6]=b'\x7fELF\x02\x01'
                header[18:20]=machine.to_bytes(2,'little')
                with tarfile.open(path,'w:xz') as archive:
                    member=tarfile.TarInfo('./usr/bin/bash')
                    member.size=len(header)
                    archive.addfile(member,io.BytesIO(header))
                verify_template_identity(path,architecture=architecture)
                other='arm64' if architecture=='amd64' else 'amd64'
                with self.assertRaisesRegex(ValueError,'architecture does not match'):
                    verify_template_identity(path,architecture=other)

    def test_metadata_without_a_native_executable_cannot_prove_arm64(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=self.write_archive(Path(temporary),['etc/os-release'],'xz')
            with self.assertRaisesRegex(ValueError,'no executable'):
                verify_template_identity(path,architecture='arm64')

    def write_archive(self, folder, names, extension):
        tar = folder / 'rootfs.tar'
        with tarfile.open(tar, 'w') as archive:
            for name in names:
                member = tarfile.TarInfo(name)
                content = b'fixture-content-must-never-appear-in-errors'
                member.size = len(content)
                archive.addfile(member, io.BytesIO(content))
        output = folder / ('rootfs.tar.' + extension)
        if extension == 'xz':
            import lzma
            with tar.open('rb') as source, lzma.open(output, 'wb') as target:
                shutil.copyfileobj(source, target)
        else:
            subprocess.run(['zstd', '--quiet', '--force', str(tar), '-o', str(output)], check=True)
        return output

    def exercise_format(self, extension):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            path = self.write_archive(folder, ['etc/os-release', './usr/bin/ssh-keygen'], extension)
            verify_template_identity(path)
            for unsafe in ('./etc/ssh/ssh_host_ed25519_key', 'etc/ssh/ssh_host_rsa_key.pub',
                           'etc/dropbear/dropbear_ed25519_host_key', '../etc/ssh/ssh_host_rsa_key'):
                with self.subTest(path=unsafe):
                    path = self.write_archive(folder, ['etc/os-release', unsafe], extension)
                    with self.assertRaises(ValueError) as raised:
                        verify_template_identity(path)
                    self.assertNotIn('fixture-content', str(raised.exception))

    def test_xz_accepts_clean_and_rejects_inherited_identities(self):
        self.exercise_format('xz')

    @unittest.skipUnless(shutil.which('zstd'), 'zstd is installed by the template workflow')
    def test_zstd_accepts_clean_and_rejects_inherited_identities(self):
        self.exercise_format('zst')

    def test_empty_archive_cannot_be_published(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_archive(Path(temporary), [], 'xz')
            with self.assertRaisesRegex(ValueError, 'empty'):
                verify_template_identity(path)

    def test_unreadable_source_is_reported_as_a_deferred_candidate(self):
        from refresh_pve_template import process_candidates
        from contextlib import redirect_stderr
        with tempfile.TemporaryDirectory() as temporary, redirect_stderr(io.StringIO()):
            path = Path(temporary) / 'broken.tar.xz'
            path.write_bytes(b'not-an-archive')
            rows = [{'name': str(path)}, {'name': 'healthy'}]
            def process(asset):
                if asset['name'] == str(path):
                    verify_template_identity(path)
                return 'healthy.tar.zst'
            self.assertEqual(process_candidates(rows, process), ['healthy.tar.zst'])


if __name__ == '__main__':
    unittest.main()
