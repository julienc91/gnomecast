import subprocess


def parse_ffmpeg_time(time_s: str) -> float:
    hours, minutes, seconds = (float(s) for s in time_s.split(":"))
    return hours * 60 * 60 + minutes * 60 + seconds


def check_ffmpeg_installed() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], check=True, stdout=subprocess.DEVNULL)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
