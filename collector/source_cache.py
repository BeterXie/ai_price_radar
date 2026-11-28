"""Atomic, bounded six-hour 16688 source cache with original observation times."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
from urllib.parse import urlsplit
from price_radar_http.platform_16688 import HOSTS
from collector_protocol import MAX_LINE, MAX_EXPANDED, MAX_COMPRESSED, validate_collected_record

REFRESH_SECONDS=6*3600
MAX_CACHE_BYTES=64*1024*1024
MAX_TOTAL_BYTES=512*1024*1024
WORKSPACE_RESERVE=MAX_EXPANDED+MAX_COMPRESSED+64*1024*1024


def _path(root,spec):
    if spec.get('connector')!='16688':return None
    parsed=urlsplit(spec['source'])
    match=re.fullmatch(r'/(shop|goods)/([A-Za-z0-9._~-]{1,128})/?',parsed.path)
    if parsed.scheme!='https' or parsed.hostname not in HOSTS or not match:
        return None
    return root/'source-cache/16688'/(match[1]+'-'+match[2]+'.cache')


def load(root,spec):
    path=_path(root,spec)
    if path is None:return None
    try:
        if path.stat().st_size>MAX_CACHE_BYTES:return None
        with path.open('rb') as stream:
            header=stream.readline(4097)
            if len(header)>4096:return None
            meta=json.loads(header)
            if not isinstance(meta,dict) or meta.get('source')!=spec['source']:
                return None
            if not 0<=time.time()-meta['collected_at']<REFRESH_SECONDS:return None
            rows=[]
            while line:=stream.readline(MAX_LINE+1):
                if len(line)>MAX_LINE:return None
                row=json.loads(line);validate_collected_record(row,spec);rows.append(row)
            return rows if len(rows)==meta['count'] else None
    except (OSError,ValueError,TypeError,KeyError,RecursionError,OverflowError):
        return None


def cleanup(root):
    folder=root/'source-cache/16688'
    now=time.time();files=[]
    for path in folder.glob('cache-*.tmp'):
        if now-path.stat().st_mtime>3600:path.unlink()
    for path in folder.glob('*.cache'):
        stat=path.stat()
        if now-stat.st_mtime>=REFRESH_SECONDS:path.unlink()
        else:files.append((stat.st_mtime,stat.st_size,path))
    total=sum(size for _,size,_ in files)
    for _,size,path in sorted(files):
        if total<=MAX_TOTAL_BYTES:break
        path.unlink();total-=size


def store(root,spec,complete_records,count):
    path=_path(root,spec)
    if path is None or complete_records.stat().st_size+4096>MAX_CACHE_BYTES:return
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    if shutil.disk_usage(path.parent).free < WORKSPACE_RESERVE+complete_records.stat().st_size+4096:
        return
    descriptor,name=tempfile.mkstemp(dir=path.parent,prefix='cache-',suffix='.tmp')
    temporary=Path(name)
    try:
        with os.fdopen(descriptor,'wb') as out,complete_records.open('rb') as incoming:
            header={'source':spec['source'],'collected_at':time.time(),'count':count}
            out.write(json.dumps(header).encode()+b'\n');shutil.copyfileobj(incoming,out)
            out.flush();os.fsync(out.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    cleanup(root)
