import subprocess
from pathlib import Path
import tempfile
import pycaption


def convert_subtitles_to_webvtt(subtitles_path: Path) -> str:
    subtitles_bytes = Path(subtitles_path).read_bytes()
    try:
        subtitles = subtitles_bytes.decode("utf-8")
    except UnicodeDecodeError:
        subtitles = subtitles_bytes.decode("latin-1")

    subtitles.removeprefix("\ufeff")  # Remove BOM if present

    converter = pycaption.CaptionConverter()
    converter.read(subtitles, pycaption.detect_format(subtitles)())
    return converter.write(pycaption.WebVTTWriter())


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
            cmd += ["-map", index, "-f", "webvtt", "-scodec", "webvtt", output_file]
            output_files.append(output_file)

        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error extracting subtitles: {e.stderr.strip()}")
            return None

        result = []
        for output_file in output_files:
            result.append(output_file.read_text())
    return result
