import os
import subprocess
import tempfile
from pathlib import Path

from gnomecast.utils import get_tempfile_prefix


def parse_ffmpeg_time(time_s: str) -> float:
    hours, minutes, seconds = (float(s) for s in time_s.split(":"))
    return hours * 60 * 60 + minutes * 60 + seconds


def check_ffmpeg_installed() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], check=True, stdout=subprocess.DEVNULL)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def extract_thumbnail(file_path: Path, offset: int = 30) -> Path:
    _, output_path = tempfile.mkstemp(
        prefix=f"{get_tempfile_prefix()}_thumbnail_", suffix=".jpg"
    )
    cmd = [
        "ffmpeg",
        "-y",
        *("-v", "0"),  # Set log level to quiet
        *("-i", file_path),
        *("-f", "mjpeg"),
        *("-vframes", "1"),
        *("-ss", str(offset)),
        *("-vf", "scale=600:-1"),
        output_path,
    ]
    subprocess.run(cmd, check=True)
    return Path(output_path)


def get_media_duration(file_path: Path) -> float:
    cmd = [
        "ffprobe",
        *("-v", "error"),
        *("-show_entries", "format=duration"),
        *("-of", "default=noprint_wrappers=1:nokey=1"),
        str(file_path),
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return float(result.stdout.strip())
