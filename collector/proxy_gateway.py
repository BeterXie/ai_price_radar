"""Authenticated 16688-only CONNECT and fixed-group rotation in Mihomo's network namespace."""
from __future__ import annotations

import base64
import hmac
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import os
from pathlib import Path
import select
import tempfile
import threading
import time
import sys

from price_radar_http import PinnedHTTPSClient
from price_radar_http.deadline import socket_deadline
from price_radar_http.egress import HOSTS

GROUP = '16688-egress'
BUILTINS=frozenset({'DIRECT','REJECT','REJECT-DROP','PASS','GLOBAL','COMPATIBLE',GROUP})
MAX_STATE_BYTES=128*1024


class QuarantinedNodeError(OSError):
    pass


def selectable_nodes(group):
    nodes=group.get('all')
    if not isinstance(nodes,list):return []
    return [node for node in nodes if isinstance(node,str) and 0<len(node)<=256 and
            node not in BUILTINS and not any(ord(character)<32 for character in node)]


class Gateway:
    def __init__(self, secret, state_path):
        self.authorization = 'Basic ' + base64.b64encode(('collector:' + secret['proxy_password']).encode()).decode()
        self.controller_token = secret['controller_token']
        self.state_path = state_path
        self.lock = threading.Lock()
        self.addresses = {}

    def control(self, method, payload=None):
        connection = http.client.HTTPConnection('127.0.0.1', 9090, timeout=3)
        try:
            connection.connect()
            raw_socket=connection.sock
            with socket_deadline(lambda: raw_socket, time.monotonic()+4):
                connection.request(method, '/proxies/'+GROUP,
                    body=json.dumps(payload) if payload is not None else None,
                    headers={'Authorization':'Bearer '+self.controller_token,'Content-Type':'application/json'})
                response=connection.getresponse();data=response.read(1024*1024+1)
                if response.status not in (200,204) or len(data)>1024*1024:
                    raise OSError('proxy selector unavailable')
                result=json.loads(data) if data else {}
                if not isinstance(result,dict):raise ValueError('invalid selector response')
                return result
        finally:
            connection.close()

    def state(self):
        if not self.state_path.exists():return {}
        with self.state_path.open('rb') as stream:raw=stream.read(MAX_STATE_BYTES+1)
        if len(raw)>MAX_STATE_BYTES:raise ValueError('invalid quarantine state')
        state=json.loads(raw)
        if not isinstance(state,dict):raise ValueError('invalid quarantine state')
        now=time.time()
        return {name:until for name,until in state.items() if isinstance(name,str) and
                type(until) in (int,float) and now<until<now+3600}

    def save_state(self,state):
        encoded=json.dumps(state,ensure_ascii=False).encode()
        if len(encoded)>MAX_STATE_BYTES:raise ValueError('quarantine capacity reached; wait for existing entries to expire')
        descriptor,name=tempfile.mkstemp(dir=self.state_path.parent,prefix='quarantine-',suffix='.tmp')
        try:
            with os.fdopen(descriptor,'wb') as stream:
                stream.write(encoded);stream.flush();os.fsync(stream.fileno())
            Path(name).replace(self.state_path)
        finally:
            Path(name).unlink(missing_ok=True)

    def rotate(self,allow_switch):
        with self.lock:
            state=self.state();group=self.control('GET')
            current,nodes=group.get('now'),selectable_nodes(group)
            if not nodes or current not in nodes:
                raise ValueError('invalid selector response')
            state.setdefault(current,time.time()+1800)
            candidates=[node for node in nodes if node not in state]
            # Persist the failure even if changing the selector fails.
            self.save_state(state)
            if allow_switch and candidates:
                self.control('PUT',{'name':candidates[0]})
                return True
            return False

    def validate_target(self,host,address,port):
        parsed_address=ipaddress.ip_address(address)
        if host not in HOSTS or port!=443 or parsed_address.version!=4 or not parsed_address.is_global:
            raise ValueError('target is not an official public source')
        with self.lock:
            group=self.control('GET');current=group.get('now')
            if current not in selectable_nodes(group):raise OSError('no subscription node is selected')
            if current in self.state():raise QuarantinedNodeError('current proxy node is quarantined')
            cached=self.addresses.get(host)
            if cached is None or cached[0]<=time.monotonic() or address not in cached[1]:
                client=PinnedHTTPSClient(max_task_seconds=6,request_timeout=3)
                cached=(time.monotonic()+60,set(client._public_addresses(host)))
                self.addresses[host]=cached
            if address not in cached[1]:
                raise ValueError('target address does not belong to the official source')


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*_):
        pass

    def handle(self):
        self.connection.settimeout(10)
        try:
            with socket_deadline(lambda:self.connection,time.monotonic()+45):
                super().handle()
        except (OSError,ValueError,http.client.HTTPException):
            pass

    def authenticated(self):
        supplied=self.headers.get('Proxy-Authorization','')
        if not hmac.compare_digest(supplied,self.server.gateway.authorization):
            self.send_error(407,'Proxy authentication required');return False
        return True

    def do_GET(self):
        if not self.authenticated():return
        if self.path!='/health':self.send_error(404);return
        try:
            group=self.server.gateway.control('GET')
            if group.get('now') not in selectable_nodes(group):raise ValueError()
        except (OSError,ValueError,http.client.HTTPException):
            self.send_error(503);return
        self.send_response(200);self.send_header('Content-Length','2');self.end_headers();self.wfile.write(b'{}')

    def do_POST(self):
        if not self.authenticated():return
        if self.path!='/rotate':self.send_error(404);return
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=64:raise ValueError()
            payload=json.loads(self.rfile.read(size))
            if not isinstance(payload,dict) or set(payload)!={'switch'} or type(payload['switch']) is not bool:
                raise ValueError()
            changed=self.server.gateway.rotate(payload['switch'])
        except (OSError,ValueError,http.client.HTTPException):
            self.send_error(503,'Proxy selection unavailable');return
        body=json.dumps({'changed':changed}).encode()
        self.send_response(200);self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)

    def do_CONNECT(self):
        if not self.authenticated():return
        tunnel=None
        try:
            address,port=self.path.rsplit(':',1)
            address=str(ipaddress.ip_address(address.strip('[]')))
            host=self.headers.get('X-PriceMemo-Source','')
            self.server.gateway.validate_target(host,address,int(port))
        except QuarantinedNodeError:
            self.send_error(409,'Selected node is quarantined');return
        except ValueError:
            self.send_error(403,'Destination is not allowed');return
        except (OSError,http.client.HTTPException):
            self.send_error(503,'Local destination validation unavailable');return
        try:
            tunnel=http.client.HTTPConnection('127.0.0.1',7890,timeout=10)
            # Establish the socket separately so the watchdog can interrupt the
            # entire CONNECT response even if headers arrive a byte at a time.
            import socket
            tunnel.sock=socket.create_connection(('127.0.0.1',7890),timeout=3)
            raw_socket=tunnel.sock
            with socket_deadline(lambda:raw_socket,time.monotonic()+8):
                raw_socket.sendall((f'CONNECT {address}:443 HTTP/1.1\r\nHost: {address}:443\r\n'
                                   f'Proxy-Authorization: {self.server.gateway.authorization}\r\n\r\n').encode())
                response=http.client.HTTPResponse(raw_socket)
                try:
                    response.begin()
                    if response.status in (403,407):raise ValueError('Upstream policy rejected connection')
                    if response.status!=200:raise OSError('Proxy unavailable')
                finally:response.close()
        except ValueError:
            if tunnel:tunnel.close()
            self.send_error(403,'Destination is not allowed');return
        except (OSError,http.client.HTTPException):
            if tunnel:tunnel.close()
            self.send_error(502,'Proxy connection unavailable');return
        self.send_response(200,'Connection Established');self.end_headers()
        upstream=tunnel.sock
        try:
            with socket_deadline(lambda:upstream,time.monotonic()+30):
                deadline=time.monotonic()+30
                while time.monotonic()<deadline:
                    readable,_,_=select.select([self.connection,upstream],[],[],1)
                    for source in readable:
                        content=source.recv(64*1024)
                        if not content:return
                        target=upstream if source is self.connection else self.connection
                        target.sendall(content)
        finally:
            tunnel.close()


class Server(ThreadingHTTPServer):
    daemon_threads=True
    request_queue_size=8

    def __init__(self,address,gateway):
        self.gateway=gateway;self.capacity=threading.BoundedSemaphore(8)
        super().__init__(address,Handler)

    def process_request(self,request,client_address):
        if not self.capacity.acquire(blocking=False):
            request.close();return
        try:super().process_request(request,client_address)
        except BaseException:
            self.capacity.release();raise

    def process_request_thread(self,request,client_address):
        try:super().process_request_thread(request,client_address)
        finally:self.capacity.release()

    def handle_error(self,request,client_address):
        print('16688 egress request failed',flush=True)


if __name__=='__main__':
    secret=json.loads(Path('/secrets/gateway.key').read_text())
    gateway=Gateway(secret,Path('/state/quarantine.json'))
    if sys.argv[1:]==['--healthcheck']:
        connection=http.client.HTTPConnection('172.30.93.10',7891,timeout=4)
        try:
            connection.request('GET','/health',headers={'Proxy-Authorization':gateway.authorization})
            sys.exit(0 if connection.getresponse().status==200 else 1)
        finally:connection.close()
    Server(('172.30.93.10',7891),gateway).serve_forever()
