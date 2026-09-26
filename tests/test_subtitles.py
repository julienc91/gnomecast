import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from gnomecast.subtitles import (
    find_sidecar_subtitles,
    get_preferred_language,
    language_from_locale,
)


class TestFindSidecarSubtitles(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.video = self.dir / "Movie.mkv"
        self.video.touch()

    def tearDown(self):
        self._tmp.cleanup()

    def touch(self, *names):
        for name in names:
            (self.dir / name).touch()

    def names(self, lang):
        return [p.name for p in find_sidecar_subtitles(self.video, lang)]

    def test_sidecar_exact_name(self):
        self.touch("Movie.srt")
        self.assertEqual(self.names(None), ["Movie.srt"])

    def test_sidecar_vtt_before_srt(self):
        self.touch("Movie.srt", "Movie.vtt")
        self.assertEqual(self.names(None), ["Movie.vtt", "Movie.srt"])

    def test_sidecar_lang_tagged_files_found(self):
        self.touch("Movie.fr.srt", "Movie.en.srt")
        self.assertEqual(self.names(None), ["Movie.en.srt", "Movie.fr.srt"])

    def test_sidecar_untagged_before_other_langs(self):
        self.touch("Movie.en.srt", "Movie.srt")
        self.assertEqual(self.names(None), ["Movie.srt", "Movie.en.srt"])

    def test_sidecar_preferred_lang_first(self):
        self.touch("Movie.en.srt", "Movie.srt", "Movie.fr.srt")
        self.assertEqual(
            self.names("fr"), ["Movie.fr.srt", "Movie.srt", "Movie.en.srt"]
        )

    def test_sidecar_preferred_lang_region_and_three_letter_codes(self):
        self.touch("Movie.pt-BR.srt", "Movie.en.srt")
        self.assertEqual(self.names("pt")[0], "Movie.pt-BR.srt")
        self.touch("Movie.fre.srt")
        self.assertEqual(self.names("fr")[0], "Movie.fre.srt")

    def test_sidecar_extension_case_insensitive(self):
        self.touch("Movie.EN.SRT")
        self.assertEqual(self.names("en"), ["Movie.EN.SRT"])

    def test_sidecar_ignores_unrelated_files(self):
        self.touch("Movie.nfo", "Movie2.srt", "Other.srt", "Movie.en.forced.srt")
        self.assertEqual(self.names(None), [])


class TestLanguageFromLocale(unittest.TestCase):
    def test_sidecar_locale_parsing(self):
        self.assertEqual(language_from_locale("fr_FR.UTF-8"), "fr")
        self.assertEqual(language_from_locale("en_US"), "en")
        self.assertIsNone(language_from_locale("C"))
        self.assertIsNone(language_from_locale("POSIX"))
        self.assertIsNone(language_from_locale(None))

    def test_sidecar_preferred_language_from_env(self):
        env = {"LANGUAGE": "", "LC_ALL": "", "LANG": "de_DE.UTF-8"}
        with mock.patch.dict("os.environ", env, clear=True):
            self.assertEqual(get_preferred_language(), "de")
        env = {"LANGUAGE": "fr_FR:en", "LANG": "de_DE.UTF-8"}
        with mock.patch.dict("os.environ", env, clear=True):
            self.assertEqual(get_preferred_language(), "fr")


if __name__ == "__main__":
    unittest.main()
