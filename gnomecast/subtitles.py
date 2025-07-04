from pathlib import Path

import pycaption


def convert_subtitles_to_webvtt(subtitles_path: str) -> str:
    subtitles_bytes = Path(subtitles_path).read_bytes()
    try:
        subtitles = subtitles_bytes.decode("utf-8")
    except UnicodeDecodeError:
        subtitles = subtitles_bytes.decode("latin-1")

    subtitles.removeprefix("\ufeff")  # Remove BOM if present

    converter = pycaption.CaptionConverter()
    converter.read(subtitles, pycaption.detect_format(subtitles)())
    return converter.write(pycaption.WebVTTWriter())
