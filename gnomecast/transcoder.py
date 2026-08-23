import os
import re
import subprocess
import tempfile
import time

from .cache import (
    TRANSCODE_CACHE_MP4,
    check_transcode_cache,
    delete_transcode_cache,
    write_transcode_cache,
)
from .devices import get_device, Device
from .ffmpeg import parse_ffmpeg_time
from .utils import start_thread

AUDIO_EXTS = ("aac", "mp3", "wav")


class Transcoder:
    def __init__(
        self,
        cast,
        fmd,
        video_stream,
        audio_stream,
        done_callback,
        error_callback,
        prev_transcoder=None,
    ):
        self.fmd = fmd
        self.video_stream = video_stream
        self.audio_stream = audio_stream
        fn = fmd.fn
        self.cast = cast
        self.source_fn = fn
        self.p = None
        self.using_cache = False

        if prev_transcoder:
            prev_transcoder.destroy()

        print("Transcoder", fn)
        transcode_container = fmd.container not in ("mp4", "aac", "mp3", "wav")
        self.transcode_video = not self.can_play_video_codec(video_stream.codec)
        self.transcode_audio = (
            fmd.container not in AUDIO_EXTS
            or not self.can_play_audio_stream(self.audio_stream)
        )
        self.transcode = (
            transcode_container or self.transcode_video or self.transcode_audio
        )
        self.trans_fn = None

        self.progress_bytes = 0
        self.progress_seconds = 0
        self.done_callback = done_callback
        self.error_callback = error_callback
        print(
            "transcode, transcode_video, transcode_audio",
            self.transcode,
            self.transcode_video,
            self.transcode_audio,
        )
        if self.transcode:
            self.done = False

            transcode_audio_to = (
                "ac3"
                if self.device.ac3 and audio_stream and audio_stream.channels > 2
                else "mp3"
            )

            # Build the ffmpeg command (without output path) for cache comparison
            self.transcode_cmd = [
                "ffmpeg",
                "-i",
                self.source_fn,
                "-map",
                self.video_stream.index,
            ]
            if self.audio_stream:
                self.transcode_cmd += [
                    "-map",
                    self.audio_stream.index,
                    "-c:a",
                    transcode_audio_to if self.transcode_audio else "copy",
                ] + (["-b:a", "256k"] if self.transcode_audio else [])
            self.transcode_cmd += [
                "-c:v",
                "h264" if self.transcode_video else "copy",
            ]  # '-movflags', 'faststart'

            # Check transcode cache before starting ffmpeg
            if check_transcode_cache(self.source_fn, self.transcode_cmd):
                print("Using cached transcode:", TRANSCODE_CACHE_MP4)
                self.trans_fn = TRANSCODE_CACHE_MP4
                self.using_cache = True
                self.done = True
                self.done_callback()
                return

            dir = "/var/tmp" if os.path.isdir("/var/tmp") else None
            self.trans_fn = tempfile.mkstemp(
                suffix=".mp4",
                prefix="gnomecast_pid%i_transcode_" % os.getpid(),
                dir=dir,
            )[1]
            os.remove(self.trans_fn)

            self.transcode_cmd += [self.trans_fn]
            print(" ".join(["'%s'" % s if " " in s else s for s in self.transcode_cmd]))
            print("---------------------")
            print(" starting ffmpeg at:")
            print("---------------------")
            self.p = subprocess.Popen(
                self.transcode_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
            )
            start_thread(self.monitor, daemon=True)
        else:
            self.done = True
            self.done_callback()

    @property
    def device(self) -> Device:
        return get_device(
            self.cast.cast_info.manufacturer, self.cast.cast_info.model_name
        )

    @property
    def fn(self):
        return self.trans_fn if self.transcode else self.source_fn

    def can_play_video_codec(self, video_codec):
        h265 = False if self.cast.cast_info.cast_type == "audio" else self.device.h265
        if h265:
            return video_codec in ("h264", "h265", "hevc")
        else:
            return video_codec in ("h264",)

    def can_play_audio_stream(self, stream):
        if not stream:
            return True
        if self.device.ac3:
            return stream.codec in ("aac", "mp3", "ac3")
        else:
            return stream.codec in ("aac", "mp3")

    def wait_for_byte(self, offset, buffer=128 * 1024 * 1024):
        if self.done:
            return
        if self.source_fn.lower().split(".")[-1] == "mp4":
            while offset > self.progress_bytes + buffer:
                print("waiting for", offset, "at", self.progress_bytes + buffer)
                time.sleep(2)
        else:
            while not self.done:
                print("waiting for transcode to finish")
                time.sleep(2)
        print("done waiting")

    def monitor(self):
        line = b""
        r = re.compile(r"=\s+")
        total_output = b""
        while self.p:
            assert self.p.stdout is not None
            byte = self.p.stdout.read(1)
            total_output += byte
            if byte == b"" and self.p.poll() is not None:
                break
            if byte != b"":
                line += byte
                if byte == b"\r":
                    # frame=92578 fps=3937 q=-1.0 size= 1142542kB time=01:04:21.14 bitrate=2424.1kbits/s speed= 164x
                    line = line.decode()
                    line = r.sub("=", line)
                    items = [s.split("=") for s in line.split()]
                    d = dict([x for x in items if len(x) == 2])
                    print(d)
                    self.progress_bytes = (
                        int(d.get("size", "0kb").lower().rstrip("kib")) * 1024
                    )
                    progress = parse_ffmpeg_time(d.get("time", "00:00:00"))
                    if progress is not None:
                        self.progress_seconds = progress
                    line = b""
        if self.p:
            assert self.p.stdout is not None
            self.p.stdout.close()
            if self.p.returncode:
                print("--== transcode error ==--")
                print(total_output)
                self.error_callback(total_output.decode())
                return
        self.done = True
        # Save to transcode cache
        if self.trans_fn and os.path.isfile(self.trans_fn):
            delete_transcode_cache()
            try:
                os.rename(self.trans_fn, TRANSCODE_CACHE_MP4)
                self.trans_fn = TRANSCODE_CACHE_MP4
                self.using_cache = True
                # Save cache metadata (command without output path)
                cache_cmd = self.transcode_cmd[:-1]
                stat = os.stat(self.source_fn)
                write_transcode_cache(
                    self.source_fn, stat.st_mtime, stat.st_size, cache_cmd
                )
                print("Transcode cached:", TRANSCODE_CACHE_MP4)
            except OSError as e:
                print("Failed to cache transcode:", e)
        if self.done_callback:
            self.done_callback(did_transcode=True)

    def destroy(self):
        if self.p and self.p.poll() is None:
            self.p.terminate()
        if self.trans_fn and os.path.isfile(self.trans_fn) and not self.using_cache:
            os.remove(self.trans_fn)

    def __del__(self):
        self.destroy()
