"""Reject inherited host identities without extracting or logging key contents."""
from pathlib import Path, PurePosixPath
import lzma
import re
import subprocess
import tarfile


HOST_KEY = re.compile(r'(?:etc/ssh/ssh_host_[^/]+_key(?:\.pub|-cert\.pub)?|etc/dropbear/dropbear_[^/]+_host_key)')


def inspect_members(archive):
    count = 0
    for member in archive:
        name = PurePosixPath(member.name)
        if name.is_absolute() or '..' in name.parts:
            raise ValueError('Template contains an unsafe archive path')
        if HOST_KEY.fullmatch(str(name)):
            raise ValueError('Template contains an inherited SSH host identity')
        count += 1
    if not count:
        raise ValueError('Template archive is empty')


def _verify_template_identity(filename):
    path = Path(filename)
    if path.name.endswith('.tar.xz'):
        with tarfile.open(path, 'r|xz') as archive:
            inspect_members(archive)
    elif path.name.endswith('.tar.zst'):
        process = subprocess.Popen(['zstd', '--quiet', '--decompress', '--stdout', '--', str(path)],
                                   stdout=subprocess.PIPE)
        try:
            with tarfile.open(fileobj=process.stdout, mode='r|') as archive:
                inspect_members(archive)
            # Check the full compressed frame, including bytes after tar EOF.
            while process.stdout.read(1024 * 1024):
                pass
            if process.wait(timeout=60):
                raise ValueError('Template decompression failed')
        finally:
            process.stdout.close()
            if process.poll() is None:
                process.kill()
                process.wait()
    else:
        raise ValueError('Unsupported template archive format')


def verify_template_identity(filename):
    try:
        _verify_template_identity(filename)
    except (tarfile.TarError, lzma.LZMAError, EOFError) as error:
        raise ValueError('Template archive is unreadable') from error

