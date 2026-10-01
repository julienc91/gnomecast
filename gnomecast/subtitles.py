import logging
import os
import subprocess
import tempfile
from pathlib import Path

import pycaption

logger = logging.getLogger(__name__)

SIDECAR_EXTS = ["vtt", "srt"]

# ISO 639-1 -> ISO 639-2 (bibliographic and terminology) codes, for sidecar
# files tagged like "Movie.fre.srt"
THREE_LETTER_LANGS = {
    "ar": ["ara"],
    "cs": ["cze", "ces"],
    "da": ["dan"],
    "de": ["ger", "deu"],
    "el": ["gre", "ell"],
    "en": ["eng"],
    "es": ["spa"],
    "fi": ["fin"],
    "fr": ["fre", "fra"],
    "he": ["heb"],
    "hu": ["hun"],
    "it": ["ita"],
    "ja": ["jpn"],
    "ko": ["kor"],
    "nl": ["dut", "nld"],
    "no": ["nor"],
    "pl": ["pol"],
    "pt": ["por"],
    "ro": ["rum", "ron"],
    "ru": ["rus"],
    "sv": ["swe"],
    "tr": ["tur"],
    "uk": ["ukr"],
    "zh": ["chi", "zho"],
}


def language_from_locale(locale_name: str | None) -> str | None:
    """Return the 2-letter language code of a locale name like "fr_FR.UTF-8"."""
    if not locale_name or locale_name in ("C", "POSIX"):
        return None
    lang = locale_name.split("_")[0].split(".")[0].lower()
    return lang if len(lang) == 2 else None


def get_preferred_language() -> str | None:
    """Return the user's 2-letter language code, following gettext's lookup order."""
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var, "").split(":")[0]
        if value:
            return language_from_locale(value)
    return None


def _lang_matches(tag: str, lang: str) -> bool:
    tag = tag.lower().replace("_", "-")
    return (
        tag == lang
        or tag.startswith(lang + "-")
        or tag in THREE_LETTER_LANGS.get(lang, [])
    )


def find_sidecar_subtitles(video_path: Path, lang: str | None) -> list[Path]:
    """
    Find subtitle files next to a video, named "<stem>.<ext>" or
    "<stem>.<tag>.<ext>", best candidate first: files tagged with `lang`,
    then the untagged file, then other tags alphabetically.
    """
    stem = video_path.stem
    candidates = []
    for path in video_path.parent.iterdir():
        if not path.name.startswith(stem + ".") or not path.is_file():
            continue
        parts = path.name[len(stem) + 1 :].split(".")
        ext = parts[-1].lower()
        if ext not in SIDECAR_EXTS or len(parts) > 2:
            continue
        tag = parts[0] if len(parts) == 2 else ""
        if lang and tag and _lang_matches(tag, lang):
            group = 0
        elif not tag:
            group = 1
        else:
            group = 2
        candidates.append(((group, tag.lower(), SIDECAR_EXTS.index(ext)), path))
    return [path for _, path in sorted(candidates)]


def convert_subtitles_to_webvtt(subtitles_path: Path) -> str:
    subtitles_bytes = Path(subtitles_path).read_bytes()
    try:
        subtitles = subtitles_bytes.decode("utf-8")
    except UnicodeDecodeError:
        subtitles = subtitles_bytes.decode("latin-1")

    subtitles = subtitles.removeprefix("\ufeff")  # Remove BOM if present

    converter = pycaption.CaptionConverter()
    converter.read(subtitles, pycaption.detect_format(subtitles)())
    return str(converter.write(pycaption.WebVTTWriter()))


def extract_single_subtitle(input_path: str, index: str) -> str | None:
    with tempfile.TemporaryDirectory() as temp_dir:
        output_file = Path(temp_dir) / "subtitle.vtt"
        cmd = [
            "ffmpeg",
            "-y",
            *("-v", "0"),
            *("-i", input_path),
            *("-vn", "-an"),
            "-map",
            index,
            "-f",
            "webvtt",
            "-scodec",
            "webvtt",
            output_file,
        ]
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            logger.warning("Could not extract subtitle stream %s: %s", index, e)
            return None
        return output_file.read_text()


def extract_subtitles_from_file(
    input_path: str, indexes: list[str]
) -> list[str] | None:
    if not indexes:
        return []

    cmd = [
        "ffmpeg",
        "-y",  # Overwrite output files without asking
        *("-v", "0"),  # Set log level to quiet
        *("-i", input_path),
        *("-vn", "-an"),  # No video, no audio
    ]
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)
        output_files = []
        for i, index in enumerate(indexes):
            output_file = temp_dir / f"subtitle_{i:03d}.vtt"
            cmd += [
                "-map",
                index,
                "-f",
                "webvtt",
                "-scodec",
                "webvtt",
                str(output_file),
            ]
            output_files.append(output_file)

        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            logger.warning("Could not extract subtitles from %s: %s", input_path, e)
            return None

        result = []
        for output_file in output_files:
            result.append(output_file.read_text())
    return result
