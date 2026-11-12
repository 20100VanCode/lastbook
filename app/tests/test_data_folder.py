#!/usr/bin/env python3
"""Where the app looks for its library, and the first-open question. Temporary folders and a made-up home only: never the real Documents.

  python3 -B app/tests/test_data_folder.py [-v]

Never packaged."""
import json, os, shutil, stat, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent)]
import main  # noqa: E402


def library(folder):
    (folder / 'library-data').mkdir(parents=True)
    (folder / 'library-data' / 'catalog.json').write_text('{}', encoding='utf-8')
    return folder


class Lookup(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='lastbook-lookup-')).resolve()
        self.home = self.tmp / 'home'
        self.home.mkdir()
        env = {k: v for k, v in os.environ.items() if k not in ('LASTBOOK_DATA', 'APPDATA', 'LOCALAPPDATA', 'USERPROFILE')}
        env['HOME'] = env['USERPROFILE'] = str(self.home)   # Path.home(): HOME on a Mac, USERPROFILE on Windows
        patches = [mock.patch.dict(os.environ, env, clear=True), mock.patch.object(main, 'beside', lambda: self.tmp / 'app' / 'LastbookData'),
                   mock.patch.object(main.sys, 'platform', 'darwin')]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.assertEqual(Path.home(), self.home)

    def tearDown(self):
        for p in self.tmp.rglob('*'):
            if p.is_dir():
                p.chmod(0o755)
        shutil.rmtree(self.tmp)

    def settings(self):
        return self.home / 'Library' / 'Application Support' / 'Lastbook' / 'settings.json'

    def test_nothing_found(self):
        (self.home / 'Downloads' / 'Other').mkdir(parents=True)
        self.assertIsNone(main.data_folder(None))

    def test_order(self):
        app_data = library(self.home / 'Library' / 'Application Support' / 'Lastbook' / 'LastbookData')
        one_down_home = library(self.home / 'Lastbook-Small' / 'LastbookData')
        in_home = library(self.home / 'LastbookData')
        one_down = library(self.home / 'Downloads' / 'Lastbook-Small' / 'LastbookData')
        downloads = library(self.home / 'Downloads' / 'LastbookData')
        docs_down = library(self.home / 'Documents' / 'Lastbook-Medium' / 'LastbookData')
        documents = library(self.home / 'Documents' / 'LastbookData')
        by_app = library(self.tmp / 'app' / 'LastbookData')
        chosen = library(self.tmp / 'elsewhere' / 'Mine')
        main.remember(chosen)
        order = [chosen, by_app, downloads, one_down, documents, docs_down, in_home, one_down_home, app_data]
        for want in order:
            self.assertEqual(main.data_folder(None), want)
            shutil.rmtree(want)
        self.assertIsNone(main.data_folder(None))

    def test_extract_all_one_down(self):
        found = library(self.home / 'Downloads' / 'Lastbook-Small' / 'LastbookData')
        self.assertEqual(main.data_folder(None), found)

    def test_hidden_and_two_down_skipped(self):
        library(self.home / 'Downloads' / '.hidden' / 'LastbookData')
        library(self.home / 'Downloads' / 'a' / 'b' / 'LastbookData')
        self.assertIsNone(main.data_folder(None))

    def test_named_folder_wins(self):
        library(self.home / 'Downloads' / 'LastbookData')
        given = self.tmp / 'given'
        self.assertEqual(main.data_folder(str(given)), given)
        with mock.patch.dict(os.environ, {'LASTBOOK_DATA': str(given)}):
            self.assertEqual(main.data_folder(None), given)

    def test_not_writable_skipped(self):
        locked = library(self.home / 'Downloads' / 'LastbookData')
        locked.chmod(stat.S_IRUSR | stat.S_IXUSR)
        if os.access(locked, os.W_OK):
            self.skipTest('running as a user who can write anywhere')
        found = library(self.home / 'Documents' / 'LastbookData')
        self.assertEqual(main.data_folder(None), found)
        self.assertIn('cannot save', main.check(locked)[1])

    def test_check_takes_the_folder_or_its_parent(self):
        data = library(self.tmp / 'Lastbook-Small' / 'LastbookData')
        self.assertEqual(main.check(data), (data, None))
        self.assertEqual(main.check(data.parent), (data, None))
        found, why = main.check(self.tmp)
        self.assertIsNone(found)
        self.assertIn('is not a Lastbook library', why)
        self.assertNotIn(str(self.tmp.parent), why)   # the folder's name, not its whole path

    def test_remembered_gone_searches_again(self):
        gone = library(self.tmp / 'usb' / 'LastbookData')
        main.remember(gone)
        self.assertEqual(json.loads(self.settings().read_text())['library'], str(gone))
        shutil.rmtree(gone)
        found = library(self.home / 'Downloads' / 'LastbookData')
        self.assertEqual(main.data_folder(None), found)
        shutil.rmtree(found)
        self.assertIsNone(main.data_folder(None))

    def test_bad_settings_ignored(self):
        self.settings().parent.mkdir(parents=True)
        self.settings().write_text('not json')
        found = library(self.home / 'Downloads' / 'LastbookData')
        self.assertEqual(main.data_folder(None), found)

    def test_ask_until_good_then_remember(self):
        good = library(self.tmp / 'Lastbook-Small' / 'LastbookData')
        asked = []
        answers = iter([str(self.tmp / 'empty'), str(good.parent)])
        (self.tmp / 'empty').mkdir()
        with mock.patch.object(main, 'choose_folder', lambda m: asked.append(m) or next(answers)):
            self.assertEqual(main.ask_for_library(), good)
        self.assertEqual(asked[0], main.ASK)
        self.assertIn('is not a Lastbook library', asked[1])
        self.assertEqual(main.data_folder(None), good)   # remembered

    def test_cancel_drops_old_reason(self):
        good = library(self.tmp / 'Lastbook-Small' / 'LastbookData')
        (self.tmp / 'empty').mkdir()
        asked = []
        answers = iter([str(self.tmp / 'empty'), '', str(good)])   # wrong folder, then the picker is cancelled
        with mock.patch.object(main, 'choose_folder', lambda m: asked.append(m) or next(answers)):
            self.assertEqual(main.ask_for_library(), good)
        self.assertIn('is not a Lastbook library', asked[1])
        self.assertEqual(asked[2], main.ASK)

    def test_quit(self):
        with mock.patch.object(main, 'choose_folder', lambda m: None):
            self.assertIsNone(main.ask_for_library())
            with mock.patch.object(sys, 'argv', ['Lastbook', '--ask']):     # the old question, kept behind --ask
                self.assertEqual(main.main(), 0)
            with mock.patch.object(sys, 'argv', ['Lastbook']), mock.patch.object(main, 'run_setup', lambda: 7):
                self.assertEqual(main.main(), 7)       # no library: the window opens on setup (engine/setup/)
        self.assertFalse(self.settings().exists())

    def test_windows_places(self):
        with mock.patch.object(main.sys, 'platform', 'win32'), mock.patch.dict(os.environ, {'APPDATA': str(self.tmp / 'Roaming'), 'LOCALAPPDATA': str(self.tmp / 'Local')}):
            self.assertEqual(main.app_folders(), (self.tmp / 'Roaming' / 'Lastbook', self.tmp / 'Local' / 'Lastbook'))
            with mock.patch.object(main, 'home_places', lambda: [self.home / 'Downloads', self.home / 'Documents', self.home]):
                local = library(self.tmp / 'Local' / 'Lastbook' / 'LastbookData')
                self.assertEqual(main.data_folder(None), local)
                chosen = library(self.tmp / 'D' / 'LastbookData')
                main.remember(chosen)
                self.assertTrue((self.tmp / 'Roaming' / 'Lastbook' / 'settings.json').is_file())
                self.assertEqual(main.data_folder(None), chosen)


if __name__ == '__main__':
    unittest.main()
