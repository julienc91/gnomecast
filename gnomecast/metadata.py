import logging
import os
import re
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from typing_extensions import override

from .ffmpeg import extract_thumbnail
from .languages import language_name
from .utils import start_thread

logger = logging.getLogger(__name__)


class StreamMetadata:
    def __init__(
        self,
        index,
        codec,
        title: str | None = None,
        language: str | None = None,
        fallback: str = "",
    ):
        self.index = index
        self.codec = codec
        self.title: str | None = title
        self.language: str | None = language
        self.fallback = fallback
        self.hearing_impaired = False
        self.forced = False
        self._subtitles: str | None = None

    @property
    def label(self) -> str:
        """A human readable name, like "English (SDH)"."""
        name = language_name(self.language)
        if not name and self.language != "und":
            name = self.language
        if self.title:
            extras = (
                []
                if name and self.title.casefold() == name.casefold()
                else [self.title]
            )
        else:
            extras = []
            if self.hearing_impaired:
                extras.append("SDH")
            if self.forced:
                extras.append("Forced")
        if name:
            return f"{name} ({', '.join(extras)})" if extras else name
        return ", ".join(extras) or self.fallback

    @override
    def __repr__(self):
        fields = [
            f"{k}:{v}"
            for k, v in self.__dict__.items()
            if v is not None and not k.startswith("_")
        ]
        return "{}({})".format(self.__class__.__name__, ", ".join(fields))


class AudioMetadata(StreamMetadata):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.channels = 2

    def details(self):
        if self.channels == 1:
            channels = "mono"
        elif self.channels == 2:
            channels = "stereo"
        elif self.channels == 6:
            channels = "5.1"
        elif self.channels == 8:
            channels = "7.1"
        else:
            channels = str(self.channels)
        return f"{self.label} ({self.codec}/{channels})"


def split_language(id: str) -> tuple[str, str | None]:
    """Split an ffmpeg stream id like "0:1(eng)" into ("0:1", "eng")."""
    if "(" in id:
        return id[: id.index("(")], id[id.index("(") + 1 : id.index(")")]
    return id, None


class FileMetadata:
    def __init__(self, fn: str, callback: Callable[["FileMetadata"], None] | None):
        self.fn = fn
        self.ready = False
        self.thumbnail_fn: str = ""
        self._ffmpeg_output: str = ""
        self._important_ffmpeg: str = ""
        self.container: str = ""
        self.video_streams: list[StreamMetadata] = []
        self.audio_streams: list[AudioMetadata] = []
        self.subtitles: list[StreamMetadata] = []

        def parse():
            self.thumbnail_fn = str(extract_thumbnail(Path(fn)))
            self._ffmpeg_output = subprocess.check_output(
                ["ffmpeg", "-i", fn, "-f", "ffmetadata", "-"],
                stderr=subprocess.STDOUT,
            ).decode()
            _important_ffmpeg = []
            output = self._ffmpeg_output.split("\n")
            self.container = fn.lower().split(".")[-1]
            self.video_streams = []
            self.audio_streams = []
            self.subtitles = []
            stream = None
            for line in output:
                line = line.strip()
                if line.startswith("ffmpeg version"):
                    _important_ffmpeg.append(line)
                if line.startswith("Stream") and "Video" in line:
                    _important_ffmpeg.append(line)
                    id = re.sub(r"\[.*?\]", "", line.split()[1].strip("#").strip(":"))
                    id, language = split_language(id)
                    video_codec = line.split()[3]
                    stream = StreamMetadata(
                        id,
                        video_codec,
                        language=language,
                        fallback=f"Video #{len(self.video_streams) + 1}",
                    )
                    self.video_streams.append(stream)
                elif line.startswith("Stream") and "Audio" in line:
                    _important_ffmpeg.append(line)
                    id = re.sub(r"\[.*?\]", "", line.split()[1].strip("#").strip(":"))
                    id, language = split_language(id)
                    audio_codec = line.split()[3].strip(",")
                    stream = AudioMetadata(
                        id,
                        audio_codec,
                        language=language,
                        fallback=f"Audio #{len(self.audio_streams) + 1}",
                    )
                    stream.hearing_impaired = "(hearing impaired)" in line
                    if ", stereo, " in line:
                        stream.channels = 1
                    if ", stereo, " in line:
                        stream.channels = 2
                    if ", 5.1" in line:
                        stream.channels = 6
                    if ", 7.1" in line:
                        stream.channels = 8
                    self.audio_streams.append(stream)
                elif line.startswith("Stream") and "Subtitle" in line:
                    _important_ffmpeg.append(line)
                    id = re.sub(r"\[.*?\]", "", line.split()[1].strip("#").strip(":"))
                    id, language = split_language(id)
                    stream = StreamMetadata(
                        id,
                        None,
                        language=language,
                        fallback=f"Subtitle #{len(self.subtitles) + 1}",
                    )
                    stream.hearing_impaired = "(hearing impaired)" in line
                    stream.forced = "(forced)" in line
                    self.subtitles.append(stream)
                elif stream and line.startswith("title"):
                    _important_ffmpeg.append(line)
                    stream.title = line.split(":", 1)[1].strip()
                elif line.startswith("Output"):
                    break
            self._important_ffmpeg = "\n".join(_important_ffmpeg)
            self.load_subtitles()
            logger.debug(
                "Probed %s: %s container, %d video, %d audio, %d subtitle stream(s)",
                fn,
                self.container,
                len(self.video_streams),
                len(self.audio_streams),
                len(self.subtitles),
            )
            self.ready = True
            if callback:
                callback(self)

        start_thread(parse)

    def wait(self):
        while not self.ready:
            time.sleep(1)

    def load_subtitles(self):
        for stream in self.subtitles:
            stream._subtitles = None

    @override
    def __repr__(self):
        fields = [f"{k}:{v}" for k, v in self.__dict__.items() if not k.startswith("_")]
        return "FileMetadata({})".format(", ".join(fields))

    def details(self):
        fields = [
            f"File: {os.path.basename(self.fn)}",
            "Video: {}".format(
                ", ".join([f"{s.label} ({s.codec})" for s in self.video_streams])
            ),
            "Audio: {}".format(", ".join([s.details() for s in self.audio_streams])),
            "Subtitles: {}".format(", ".join([s.label for s in self.subtitles])),
        ]
        return "\n".join(fields)
