import json
import os

TRANSCODE_CACHE_DIR = "/var/tmp" if os.path.isdir("/var/tmp") else "/tmp"
TRANSCODE_CACHE_MP4 = os.path.join(TRANSCODE_CACHE_DIR, "gnomecast_transcode_cache.mp4")
TRANSCODE_CACHE_JSON = os.path.join(TRANSCODE_CACHE_DIR, "gnomecast_transcode_cache.json")


def read_transcode_cache():
    try:
        with open(TRANSCODE_CACHE_JSON) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def write_transcode_cache(source_path, mtime, size, ffmpeg_cmd):
    with open(TRANSCODE_CACHE_JSON, "w") as f:
        json.dump(
            {
                "source_path": source_path,
                "mtime": mtime,
                "size": size,
                "ffmpeg_cmd": ffmpeg_cmd,
            },
            f,
        )


def check_transcode_cache(source_path, ffmpeg_cmd):
    cache = read_transcode_cache()
    if not cache:
        return False
    if not os.path.isfile(TRANSCODE_CACHE_MP4):
        return False
    try:
        stat = os.stat(source_path)
    except OSError:
        return False
    return (
        cache.get("source_path") == source_path
        and cache.get("mtime") == stat.st_mtime
        and cache.get("size") == stat.st_size
        and cache.get("ffmpeg_cmd") == ffmpeg_cmd
    )


def delete_transcode_cache():
    for path in (TRANSCODE_CACHE_MP4, TRANSCODE_CACHE_JSON):
        try:
            os.remove(path)
        except OSError:
            pass
