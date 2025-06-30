import bottle
from paste import httpserver
from paste.translogger import TransLogger

from gnomecast.utils import get_webserver_ip_address, get_webserver_port


class GnomecastWebServer:
    def __init__(self, get_subtitles, get_transcoder):
        self.ip = get_webserver_ip_address()
        self.port = get_webserver_port()
        self.get_subtitles = get_subtitles
        self.get_transcoder = get_transcoder
        self.app = bottle.Bottle()
        self._setup_routes()

    def get_subtitles_url(self) -> str:
        return f"http://{self.ip}:{self.port}/subtitles.vtt"

    def get_media_base_url(self) -> str:
        return f"http://{self.ip}:{self.port}/media/"

    def _setup_routes(self) -> None:
        app = self.app

        @app.route("/subtitles.vtt")
        def subtitles():
            response = bottle.response
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, HEAD"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers["Content-Type"] = "text/vtt"
            return self.get_subtitles()

        @app.get("/media/<id>.<ext>")
        def video(id, ext):
            print(list(bottle.request.headers.items()))
            ranges = list(
                bottle.parse_range_header(
                    bottle.request.environ["HTTP_RANGE"], 1000000000000
                )
            )
            print("ranges", ranges)
            offset, end = ranges[0]
            transcoder = self.get_transcoder()
            transcoder.wait_for_byte(offset)
            response = bottle.static_file(transcoder.fn, root="/")
            response.headers.pop("Last-Modified", None)
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, HEAD"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            return response

    def start(self) -> None:
        handler = TransLogger(self.app, setup_console_handler=True)
        httpserver.serve(
            handler, host=self.ip, port=str(self.port), daemon_threads=True
        )
