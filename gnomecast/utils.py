import os
import socket
import threading
from collections.abc import Callable, Iterable


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


def get_tempfile_prefix() -> str:
    pid = os.getpid()
    return f"gnomecast_{pid}_"


def start_thread(
    target: Callable,
    *,
    args: Iterable | None = None,
    kwargs: dict | None = None,
    delay: float | None = None,
    daemon: bool = False,
) -> None:
    args = args or ()
    kwargs = kwargs or {}
    if delay:
        if daemon:
            raise ValueError("Cannot use delay with daemon threads")
        thread = threading.Timer(delay, target, args=args, kwargs=kwargs)
    else:
        thread = threading.Thread(
            target=target, args=args, kwargs=kwargs, daemon=daemon
        )
    thread.start()


def humanize_seconds(seconds: float) -> str:
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds // 60) % 60
    seconds = seconds % 60
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"
