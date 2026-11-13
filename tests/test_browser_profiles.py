import fcntl
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('prepare_browser', Path(__file__).parents[1] / 'controller/prepare_browser.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class BrowserProfileTests(unittest.TestCase):
    def test_stale_links_removed_without_touching_profile_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = root / ('a' * 24)
            profile.mkdir()
            for name in ['SingletonLock', 'SingletonSocket', 'SingletonCookie']:
                (profile / name).symlink_to('/old-guest/' + name)
            (profile / 'Cookies').write_text('retained data')
            module.prepare(root)
            self.assertFalse((profile / 'SingletonLock').is_symlink())
            self.assertEqual((profile / 'Cookies').read_text(), 'retained data')

    def test_live_profile_lease_preserves_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = root / ('b' * 24)
            profile.mkdir()
            (profile / 'SingletonLock').symlink_to('current-guest-123')
            with (profile / '.open-terminal.lock').open('a+b') as lease:
                fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
                module.prepare(root)
            self.assertTrue((profile / 'SingletonLock').is_symlink())

    def test_unmanaged_and_symlink_profiles_are_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = root / 'unmanaged'
            profile.mkdir()
            (profile / 'SingletonLock').symlink_to('keep-me')
            (root / ('c' * 24)).symlink_to(profile, target_is_directory=True)
            module.prepare(root)
            self.assertTrue((profile / 'SingletonLock').is_symlink())
