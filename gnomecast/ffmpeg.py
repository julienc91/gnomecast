def parse_ffmpeg_time(time_s: str) -> float:
    hours, minutes, seconds = (float(s) for s in time_s.split(":"))
    return hours * 60 * 60 + minutes * 60 + seconds
