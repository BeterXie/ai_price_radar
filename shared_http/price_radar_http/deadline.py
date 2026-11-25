"""Interrupt socket I/O at an absolute deadline, including fragmented headers."""
import socket
import threading
import time
from contextlib import contextmanager


@contextmanager
def socket_deadline(get_socket, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('request deadline exceeded')
    def interrupt():
        sock = get_socket()
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
    timer = threading.Timer(remaining, interrupt)
    timer.daemon = True
    timer.start()
    try:
        yield
        if time.monotonic() >= deadline:
            raise TimeoutError('request deadline exceeded')
    finally:
        timer.cancel()
