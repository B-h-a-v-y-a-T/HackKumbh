"""
CopyCop - Unified Application Launcher
Starts both the FastAPI Backend and the React (Vite) Frontend.
Handles environment setup, dependency checks, and graceful multi-process termination.
"""

import os
import sys
import time
import shutil
import signal
import subprocess
import webbrowser
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT_DIR / "frontend"
VENV_DIR = ROOT_DIR / ".venv"

# Detect Python interpreter to use
if (VENV_DIR / "Scripts" / "python.exe").exists():
    PYTHON_EXE = str(VENV_DIR / "Scripts" / "python.exe")
elif (VENV_DIR / "bin" / "python").exists():
    PYTHON_EXE = str(VENV_DIR / "bin" / "python")
else:
    PYTHON_EXE = sys.executable

NPM_CMD = "npm.cmd" if sys.platform == "win32" else "npm"


def log(prefix: str, msg: str):
    print(f"[{prefix}] {msg}", flush=True)


def ensure_env_file():
    env_file = ROOT_DIR / ".env"
    env_example = ROOT_DIR / ".env.example"
    if not env_file.exists() and env_example.exists():
        log("SETUP", "Creating .env from .env.example...")
        shutil.copy(env_example, env_file)


def ensure_mock_data():
    mock_frame = ROOT_DIR / "data" / "mock" / "exam_frame.jpg"
    mock_script = ROOT_DIR / "scripts" / "generate_mock_data.py"
    if not mock_frame.exists() and mock_script.exists():
        log("SETUP", "Generating mock dataset...")
        try:
            subprocess.run([PYTHON_EXE, str(mock_script)], cwd=str(ROOT_DIR), check=True)
        except Exception as e:
            log("WARN", f"Mock data generation skipped: {e}")


def ensure_frontend_deps():
    node_modules = FRONTEND_DIR / "node_modules"
    if not node_modules.exists():
        log("SETUP", "Installing frontend dependencies (npm install)...")
        subprocess.run([NPM_CMD, "install"], cwd=str(FRONTEND_DIR), check=True)


def terminate_process(proc, name="Process"):
    if proc is None or proc.poll() is not None:
        return
    log("SHUTDOWN", f"Stopping {name} (PID {proc.pid})...")
    if sys.platform == "win32":
        try:
            # Terminate process tree on Windows
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass
    else:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            proc.kill()


def main():
    print("=" * 65)
    print("                COPYCOP SYSTEM RUNNER")
    print("=" * 65)

    ensure_env_file()
    ensure_mock_data()
    ensure_frontend_deps()

    backend_proc = None
    frontend_proc = None

    def handle_exit(signum=None, frame=None):
        print("\n" + "=" * 65)
        log("SHUTDOWN", "Shutting down CopyCop services...")
        print("=" * 65)
        terminate_process(frontend_proc, "Frontend (Vite)")
        terminate_process(backend_proc, "Backend (FastAPI)")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    log("BACKEND", "Starting FastAPI backend server on http://127.0.0.1:8000...")
    backend_cmd = [
        PYTHON_EXE,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
    ]
    backend_proc = subprocess.Popen(
        backend_cmd,
        cwd=str(ROOT_DIR),
    )

    # Give backend a moment to initialize
    time.sleep(2)

    log("FRONTEND", "Starting Vite React UI on http://127.0.0.1:5173...")
    frontend_cmd = [NPM_CMD, "run", "dev"]
    frontend_proc = subprocess.Popen(
        frontend_cmd,
        cwd=str(FRONTEND_DIR),
    )

    print("\n" + "=" * 65)
    print("   SERVICES ARE LIVE:")
    print("   -> Frontend UI:     http://localhost:5173")
    print("   -> Backend API:     http://localhost:8000")
    print("   -> API Docs:        http://localhost:8000/docs")
    print("   -> Health Check:    http://localhost:8000/health")
    print("=" * 65)
    print("   Press Ctrl+C at any time to stop all services.\n")

    # Optionally auto-open browser if not in headless/CI
    if "--no-browser" not in sys.argv:
        try:
            time.sleep(1.5)
            webbrowser.open("http://localhost:5173")
        except Exception:
            pass

    try:
        while True:
            time.sleep(0.5)
            # Check if any process terminated unexpectedly
            b_poll = backend_proc.poll()
            f_poll = frontend_proc.poll()
            if b_poll is not None:
                log("BACKEND", f"Backend exited with code {b_poll}")
                break
            if f_poll is not None:
                log("FRONTEND", f"Frontend exited with code {f_poll}")
                break
    except KeyboardInterrupt:
        pass
    finally:
        handle_exit()


if __name__ == "__main__":
    main()
