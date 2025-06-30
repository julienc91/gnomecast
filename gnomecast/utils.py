import os
import socket


def get_webserver_ip_address() -> str:
    hostname = socket.gethostname()
    _, _, ip_addresses = socket.gethostbyname_ex(hostname)
    for ip in ip_addresses:
        if not ip.startswith("127."):
            return ip

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("1.1.1.1", 53))
        ip, _ = s.getsockname()
    # TODO: handle OSError (network unreachable) and return explicit message
    return ip


def get_webserver_port() -> int:
    try:
        return int(os.environ["GNOMECAST_HTTP_PORT"])
    except (KeyError, ValueError, TypeError):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("0.0.0.0", 0))
            _, port = s.getsockname()
        return port
