"""Host-side timers enqueue work or publish completed artifacts; Python 3.6 compatible."""
import argparse
import os
from pathlib import Path
import subprocess


def main():
    import fcntl
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['inventory', 'scan', 'discover', 'publish', 'status'])
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    data = root / 'data/collector-results'
    if data.is_symlink() or not data.is_dir() or data.stat().st_uid != 0 or data.stat().st_gid != 10001 or data.stat().st_mode & 0o7777 != 0o2770:
        raise RuntimeError('collector-results must be root:10001 with mode 02770 before scheduling')
    with (root / 'data/crawler/.refresh.lock').open('a') as lock:
        try:
            # Enqueue must wait: skipping a busy publisher would lose a scan.
            flags = fcntl.LOCK_EX | (fcntl.LOCK_NB if args.action == 'publish' else 0)
            fcntl.flock(lock.fileno(), flags)
        except BlockingIOError:
            print('another publication/schedule is running; deferred')
            return
        command = ['docker', 'run', '--rm', '--user', '10001:10001', '--cpus', '1.0', '--memory', '600m',
                   '--network', 'ai-price-radar_default', '--env-file', str(root / '.env'),
                   '-e', 'COLLECTOR_RELEASE=' + (root / 'VERSION').read_text().strip(),
                   '-e', 'PUBLIC_DATA_DIR=/workspace/apps/web/public/data',
                   '-e', 'COLLECTOR_RESULTS_DIR=/data/collector-results',
                   '-e', 'INTAKE_API_URL=http://api:8000',
                   '-v', str(root / 'pipeline') + ':/workspace/pipeline:ro',
                   '-v', str(data) + ':/data/collector-results',
                   '-v', str(root / 'apps/web/public/data') + ':/workspace/apps/web/public/data',
                   '-w', '/workspace/pipeline']
        command += ['ai-price-radar-importer', 'python', 'collector_jobs.py']
        if args.action in ('publish', 'status'):
            command += [args.action]
        else:
            command += ['enqueue', '--kind', args.action]
        subprocess.run(command, cwd=str(root), check=True)


if __name__ == '__main__':
    main()
