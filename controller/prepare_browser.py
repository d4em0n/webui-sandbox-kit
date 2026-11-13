"""Remove stale Chromium singleton links after a private VM restart."""
import fcntl
from pathlib import Path
import re


def prepare(root):
    for profile in root.glob('*'):
        if profile.is_symlink() or not profile.is_dir() or not re.fullmatch(r'[0-9a-f]{24}', profile.name):
            continue
        with (profile / '.open-terminal.lock').open('a+b') as lease:
            try:
                fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                continue
            for name in ('SingletonLock', 'SingletonSocket', 'SingletonCookie'):
                path = profile / name
                if path.is_symlink():
                    path.unlink()


if __name__ == '__main__':
    prepare(Path.home() / '.local/state/open-terminal/browser')
