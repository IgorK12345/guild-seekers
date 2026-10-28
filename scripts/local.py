"""Start/stop the project-local PostgreSQL and web application on Windows."""
import os
import secrets
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
RUNTIME = ROOT / '.runtime'
PG = RUNTIME / 'pgsql' / 'bin'
DATA = RUNTIME / 'pgdata'
HIDDEN = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0

def command(args, **kwargs):
    if Path(str(args[0])).name == 'pg_ctl.exe' and 'start' in args:
        # A database child may inherit stdout handles: use a file, not a pipe.
        environment = os.environ.copy()
        environment['COMSPEC'] = str(RUNTIME / 'quiet-shell.exe')
        with (RUNTIME / 'pg-control.log').open('ab') as log:
            return subprocess.run([str(a) for a in args], check=True, stdout=log, stderr=log, creationflags=HIDDEN, env=environment, **kwargs)
    result = subprocess.run([str(a) for a in args], capture_output=True, creationflags=HIDDEN, **kwargs)
    output = (result.stdout + result.stderr).decode('utf-8', errors='replace')
    if output:
        print(output)
    result.check_returncode()
    return result

def database():
    RUNTIME.mkdir(exist_ok=True)
    env_file = ROOT / '.env'
    if not env_file.exists():
        password = secrets.token_urlsafe(24)
        env_file.write_text(f'DATABASE_URL=postgresql+psycopg://guild:{password}@127.0.0.1:54329/guild\n'
                            f'SECRET_KEY={secrets.token_urlsafe(48)}\nPUBLIC_ORIGIN=http://127.0.0.1:8000\nSECURE_COOKIE=false\n', encoding='utf-8')
    from dotenv import load_dotenv
    from sqlalchemy.engine import make_url
    load_dotenv(env_file)
    url = make_url(os.environ['DATABASE_URL'])
    if not (PG / 'pg_ctl.exe').exists():
        raise RuntimeError('Portable PostgreSQL missing: see README.md')
    if not (DATA / 'PG_VERSION').exists():
        password_file = RUNTIME / 'init-password.txt'
        password_file.write_text(url.password, encoding='utf-8')
        try:
            initialize([PG / 'initdb.exe', '-D', DATA, '-U', url.username, '--pwfile', password_file,
                        '--auth=scram-sha-256', '--encoding=UTF8', '--locale=C'])
        finally:
            password_file.unlink(missing_ok=True)
    status = subprocess.run([str(PG / 'pg_ctl.exe'), '-D', str(DATA), 'status'], capture_output=True, creationflags=HIDDEN)
    if status.returncode:
        command([PG / 'pg_ctl.exe', '-D', DATA, '-l', RUNTIME / 'postgres.log', '-o', '-h 127.0.0.1 -p 54329', '-w', 'start'])
    import psycopg
    from psycopg import sql
    with psycopg.connect(host=url.host, port=url.port, user=url.username, password=url.password, dbname='postgres', autocommit=True) as db:
        if not db.execute('SELECT 1 FROM pg_database WHERE datname=%s', (url.database,)).fetchone():
            db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(url.database)))

def initialize(args):
    # Use cmd /d only for initdb's version probe; leave Windows settings intact.
    shim = RUNTIME / 'quiet-shell.exe'
    if not shim.exists():
        compiler = Path(os.environ['WINDIR']) / 'Microsoft.NET' / 'Framework64' / 'v4.0.30319' / 'csc.exe'
        command([compiler, '/nologo', '/out:' + str(shim), ROOT / 'scripts' / 'QuietShell.cs'])
    environment = os.environ.copy()
    environment['COMSPEC'] = str(shim)
    command(args, env=environment)


def is_running():
    try:
        with urlopen('http://127.0.0.1:8000/health', timeout=2) as response:
            return response.status == 200 and b'postgresql' in response.read()
    except Exception:
        return False

def start():
    database()
    command([sys.executable, '-m', 'alembic', 'upgrade', 'head'])
    command([sys.executable, '-m', 'backend.app.seed'])
    if not is_running():
        with (RUNTIME / 'server.log').open('a', encoding='utf-8') as log:
            process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', '8000'],
                                       cwd=ROOT, stdout=log, stderr=log, creationflags=HIDDEN)
        (RUNTIME / 'server.pid').write_text(str(process.pid))
        for _ in range(30):
            if is_running():
                break
            if process.poll() is not None:
                raise RuntimeError('Server exited. See .runtime/server.log')
            time.sleep(.5)
        else:
            raise RuntimeError('Server startup timeout. See .runtime/server.log')
    print('Game ready: http://127.0.0.1:8000')
    if '--no-browser' not in sys.argv:
        webbrowser.open('http://127.0.0.1:8000')

def stop():
    import psutil
    pid_file = RUNTIME / 'server.pid'
    if pid_file.exists():
        try:
            process = psutil.Process(int(pid_file.read_text()))
            cmd = process.cmdline()
            if 'backend.app.main:app' in cmd and Path(process.cwd()).resolve() == ROOT:
                process.terminate()
                process.wait(timeout=10)
        except psutil.NoSuchProcess:
            pass
        pid_file.unlink(missing_ok=True)
    status = subprocess.run([str(PG / 'pg_ctl.exe'), '-D', str(DATA), 'status'], capture_output=True, creationflags=HIDDEN)
    if status.returncode == 0:
        command([PG / 'pg_ctl.exe', '-D', DATA, '-m', 'fast', '-w', 'stop'])
    print('Game stopped. Progress is saved.')

if __name__ == '__main__':
    try:
        if len(sys.argv) > 1 and sys.argv[1] == 'db':
            database()
        elif len(sys.argv) > 1 and sys.argv[1] == 'stop':
            stop()
        else:
            start()
    except Exception as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
