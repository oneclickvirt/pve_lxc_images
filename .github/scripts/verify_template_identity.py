"""Reject inherited host identities without extracting or logging key contents."""
from pathlib import Path, PurePosixPath
import lzma
import re
import subprocess
import tarfile


HOST_KEY = re.compile(r'(?:etc/ssh/ssh_host_[^/]+_key(?:\.pub|-cert\.pub)?|etc/dropbear/dropbear_[^/]+_host_key)')


def inspect_members(archive, architecture=None):
    count = 0
    expected = {'amd64': 62, 'arm64': 183}
    if architecture is not None and architecture not in expected:
        raise ValueError('Unsupported template architecture')
    executable_found = False
    for member in archive:
        name = PurePosixPath(member.name)
        if name.is_absolute() or '..' in name.parts:
            raise ValueError('Template contains an unsafe archive path')
        if HOST_KEY.fullmatch(str(name)):
            raise ValueError('Template contains an inherited SSH host identity')
        if architecture is not None and member.isfile() and str(name) in {
            'bin/bash', 'bin/sh', 'bin/dash', 'bin/busybox', 'usr/bin/bash',
            'usr/bin/dash', 'usr/bin/busybox', 'usr/lib/systemd/systemd', 'sbin/init',
        }:
            with archive.extractfile(member) as executable:
                header = executable.read(20)
            if header.startswith(b'\x7fELF'):
                if len(header) != 20 or header[4:6] != b'\x02\x01' or int.from_bytes(header[18:20], 'little') != expected[architecture]:
                    raise ValueError('Template executable architecture does not match '+architecture)
                executable_found = True
        count += 1
    if not count:
        raise ValueError('Template archive is empty')
    if architecture is not None and not executable_found:
        raise ValueError('Template has no executable to verify its architecture')


def _verify_template_identity(filename, architecture=None):
    path = Path(filename)
    if path.name.endswith('.tar.xz'):
        with tarfile.open(path, 'r|xz') as archive:
            inspect_members(archive, architecture)
    elif path.name.endswith('.tar.zst'):
        process = subprocess.Popen(['zstd', '--quiet', '--decompress', '--stdout', '--', str(path)],
                                   stdout=subprocess.PIPE)
        try:
            with tarfile.open(fileobj=process.stdout, mode='r|') as archive:
                inspect_members(archive, architecture)
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


def verify_template_identity(filename, architecture=None):
    try:
        _verify_template_identity(filename, architecture)
    except (tarfile.TarError, lzma.LZMAError, EOFError) as error:
        raise ValueError('Template archive is unreadable') from error

