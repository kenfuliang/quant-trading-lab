#!/usr/bin/env python3
"""Prepare saved reports and start/stop loopback-only performance browsers."""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
STATE = ROOT / '.local/performance-service.json'
OUTPUT = ROOT / '.local/performance'
MLFLOW = ROOT / '.local/venvs/mlflow/bin'


def owned_pid():
    if not STATE.exists():
        return None
    pid = json.loads(STATE.read_text())['pid']
    check = subprocess.run(['ps', '-p', str(pid), '-o', 'command='], capture_output=True, text=True)
    return pid if str(Path(__file__).resolve()) in check.stdout and 'serve' in check.stdout else None


def serve():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for port in (5050, 8765):
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('127.0.0.1', port))
    children = []
    def stop(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    try:
        children.append(subprocess.Popen([str(MLFLOW / 'mlflow'), 'server', '--host', '127.0.0.1', '--port', '5050',
            '--backend-store-uri', 'sqlite:///' + str(ROOT / '.local/mlflow/tracking.db'),
            '--workers', '1', '--serve-artifacts', '--artifacts-destination', str(ROOT / '.local/mlflow/artifacts')], cwd=ROOT, start_new_session=True))
        children.append(subprocess.Popen([sys.executable, '-m', 'http.server', '8765', '--bind', '127.0.0.1', '--directory', str(OUTPUT)], cwd=ROOT, start_new_session=True))
        STATE.write_text(json.dumps({'pid': os.getpid(), 'ports': [5050, 8765]}))
        while all(p.poll() is None for p in children):
            time.sleep(.5)
        raise RuntimeError('A performance browser process stopped; see .local/performance-server.log.')
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
        for child in children:
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        if STATE.exists() and json.loads(STATE.read_text())['pid'] == os.getpid():
            STATE.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'serve', 'stop'])
    args = parser.parse_args()
    if args.action == 'serve':
        serve()
        return
    if args.action == 'stop':
        pid = owned_pid()
        if pid:
            os.kill(pid, signal.SIGTERM)
            for _ in range(100):
                if not STATE.exists():
                    print('Performance browsers stopped; saved results retained.')
                    return
                time.sleep(.2)
            raise RuntimeError('Shutdown still pending; inspect the local service log.')
        print('No project performance service running.')
        return
    from reporting.saved_runs import prepare, write_index
    bundle_path = prepare()
    (ROOT / '.local/mlflow').mkdir(parents=True, exist_ok=True)
    if not owned_pid():
        with (ROOT / '.local/performance-server.log').open('a') as log:
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'serve'], cwd=ROOT,
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        for _ in range(120):
            if process.poll() is not None:
                raise RuntimeError('Server startup failed; inspect .local/performance-server.log.')
            try:
                with urlopen('http://127.0.0.1:5050/health', timeout=1) as response:
                    if STATE.exists() and response.status == 200:
                        break
            except OSError:
                pass
            time.sleep(.5)
        else:
            raise RuntimeError('MLflow did not become healthy within startup timeout.')
    subprocess.run([str(MLFLOW / 'python'), str(ROOT / 'scripts/import_performance_mlflow.py'), str(bundle_path)], check=True)
    registry = json.loads((bundle_path.parent / 'mlflow-runs.json').read_text())
    write_index(bundle_path, registry)
    latest = OUTPUT / 'leverage-latest.json'
    if latest.exists():
        from reporting.leverage import render
        render(json.loads(latest.read_text())['source'])
    print('Reports: http://127.0.0.1:8765/\nMLflow: http://127.0.0.1:5050/')


if __name__ == '__main__':
    main()
