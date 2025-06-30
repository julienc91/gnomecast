import bottle
from paste import httpserver
from paste.translogger import TransLogger


class GnomecastWebServer:
    def __init__(self, ip, port, get_subtitles, get_transcoder, get_subtitles_fn=None):
        self.ip = ip
        self.port = port
        self.get_subtitles = get_subtitles
        self.get_transcoder = get_transcoder
        self.get_subtitles_fn = get_subtitles_fn
        self.app = bottle.Bottle()
        self._setup_routes()

    def _setup_routes(self):
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
            if "Last-Modified" in response.headers:
                del response.headers["Last-Modified"]
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, HEAD"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            return response

    def start(self):
        handler = TransLogger(self.app, setup_console_handler=True)
        httpserver.serve(
            handler, host=self.ip, port=str(self.port), daemon_threads=True
        )
