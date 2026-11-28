"""Dedicated 16688 CONNECT gateway. Workers never receive proxy administration keys."""
from __future__ import annotations

import base64
import http.client
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from .deadline import socket_deadline

from .platform_16688 import HOSTS
PROXY_ADDRESS = '172.30.93.10'
PROXY_PORT = 7891


class ProxyConnectionError(OSError):
    """Only failures to establish the dedicated proxy tunnel may select another node."""


class ProxyDestinationError(ValueError):
    """A local policy rejection is not evidence of a broken proxy node."""


@dataclass(frozen=True)
class ProxySettings:
    authorization: str = field(repr=False)


def settings_for(host: str) -> ProxySettings | None:
    path = os.getenv('COLLECTOR_16688_PROXY_KEY_FILE', '')
    if host not in HOSTS or not path:
        return None
    if not os.getenv('COLLECTOR_RATE_DIR', ''):
        raise ValueError('16688 proxy requires the shared collection rate directory')
    try:
        with Path(path).open('rb') as stream:
            raw = stream.read(4097)
        if len(raw) > 4096:
            raise ValueError()
        secret = json.loads(raw)
        password = secret['proxy_password']
        if not isinstance(password, str) or not 32 <= len(password) <= 128 or not password.isascii() or not password.isalnum():
            raise ValueError()
    except (OSError, ValueError, TypeError, KeyError):
        raise ValueError('16688 proxy credential is unavailable or invalid') from None
    return ProxySettings('Basic ' + base64.b64encode(('collector:' + password).encode()).decode())


def connect_tunnel(settings, connector, address, port, host, deadline, request_timeout):
    connection = http.client.HTTPConnection(PROXY_ADDRESS, PROXY_PORT,
                                            timeout=min(request_timeout, max(0.001, deadline-time.monotonic())))
    try:
        connection.sock = connector((PROXY_ADDRESS, PROXY_PORT), timeout=connection.timeout)
        raw_socket=connection.sock
        with socket_deadline(lambda: connection.sock, deadline):
            target=('['+address+']' if ':' in address else address)+':'+str(port)
            request=(f'CONNECT {target} HTTP/1.1\r\nHost: {target}\r\n'
                     f'Proxy-Authorization: {settings.authorization}\r\nX-PriceMemo-Source: {host}\r\n\r\n')
            raw_socket.sendall(request.encode('ascii'))
            response=http.client.HTTPResponse(raw_socket)
            try:
                response.begin()
                if response.status==403:raise ProxyDestinationError('16688 proxy rejected the pinned destination')
                if response.status in (407,503):raise ValueError('16688 proxy authentication or local validation unavailable')
                if response.status!=200:raise ProxyConnectionError('16688 proxy tunnel is unavailable')
            finally:response.close()
        sock, connection.sock = connection.sock, None
        return sock
    except ValueError:
        connection.close();raise
    except (OSError, http.client.HTTPException):
        connection.close()
        if time.monotonic()>=deadline:
            raise TimeoutError('source request exceeded total time limit') from None
        raise ProxyConnectionError('16688 proxy tunnel is unavailable') from None


def rotate(settings, deadline, *, allow_switch=True) -> bool:
    """Report a failed node to the limited gateway; never call the Mihomo controller."""
    remaining = deadline-time.monotonic()
    if remaining <= 0:
        return False
    connection = http.client.HTTPConnection(PROXY_ADDRESS, PROXY_PORT, timeout=min(5, remaining))
    try:
        connection.connect()
        raw_socket=connection.sock
        with socket_deadline(lambda: raw_socket, min(deadline, time.monotonic()+5)):
            connection.request('POST', '/rotate', body=json.dumps({'switch': bool(allow_switch)}),
                               headers={'Proxy-Authorization': settings.authorization,'Content-Type':'application/json'})
            response = connection.getresponse()
            body = response.read(4097)
            if response.status != 200 or len(body)>4096:
                return False
            result = json.loads(body)
            return isinstance(result, dict) and result.get('changed') is True
    except (OSError, ValueError, http.client.HTTPException):
        return False
    finally:
        connection.close()
