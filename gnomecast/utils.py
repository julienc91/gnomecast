import os
import socket
import threading
from collections.abc import Callable


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


def throttle(seconds: float) -> Callable[[Callable], Callable]:
    def decorator(f: Callable) -> Callable:
        timer = None
        latest_args, latest_kwargs = (), {}

        def run_f():
            nonlocal timer, latest_args, latest_kwargs
            f(*latest_args, **latest_kwargs)
            timer = None

        def wrapper(*args, **kwargs) -> None:
            nonlocal timer, latest_args, latest_kwargs
            latest_args, latest_kwargs = args, kwargs
            if timer is None:
                timer = threading.Timer(seconds, run_f)
                timer.start()

        return wrapper

    return decorator


def is_pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True
