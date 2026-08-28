import subprocess
import sys
import os
import time
import signal

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

def print_banner():
    print("""
======================================================================
  ____            _               _____ _                 
 |  _ \ _____   _(_) _____      _|  ___| | _____      __  
 | |_) / _ \ \ / / |/ _ \ \ /\ / / |_  | |/ _ \ \ /\ / /  
 |  _ <  __/\ V /| |  __/\ V  V /|  _| | | (_) \ V  V /   
 |_| \_\___| \_/ |_|\___| \_/\_/ |_|   |_|\___/ \_/\_/    
  Telegram Automation SaaS Platform for Forex Channel Owners
======================================================================
    """)

def free_ports():
    """Kills any process listening on ports 8000, 3000, 3001, etc."""
    try:
        import psutil
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                for conn in proc.connections(kind='inet'):
                    if conn.laddr.port in [8000, 3000, 3001, 3002, 3003, 3004]:
                        proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except Exception:
        pass

def main():
    print_banner()
    print("[*] Ensuring ports 8000 and 3000 are clean and free...", flush=True)
    free_ports()
    time.sleep(1.0)

    custom_env = dict(os.environ)
    custom_env["PYTHONPATH"] = os.getcwd()
    custom_env["PYTHONUNBUFFERED"] = "1"
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"

    # Process configurations: (name, command, cwd)
    service_defs = {
        "api": {
            "name": "[1/3] 🚀 FastAPI Backend API",
            "cmd": [sys.executable, "-u", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"],
            "cwd": os.getcwd()
        },
        "listener": {
            "name": "[2/3] 🛰️ Telegram Master Engine",
            "cmd": [sys.executable, "-u", "telegram_engine/listener.py"],
            "cwd": os.getcwd()
        },
        "frontend": {
            "name": "[3/3] 🌐 React Dashboard",
            "cmd": [npm_cmd, "run", "dev", "--", "--port", "3000", "--host"],
            "cwd": os.path.join(os.getcwd(), "frontend")
        }
    }

    running_procs = {}

    def start_service(key):
        cfg = service_defs[key]
        print(f"Starting {cfg['name']}...")
        p = subprocess.Popen(cfg["cmd"], cwd=cfg["cwd"], env=custom_env)
        running_procs[key] = p
        return p

    try:
        # Start all services
        for key in ["api", "listener", "frontend"]:
            start_service(key)
            time.sleep(1.5)

        print("\n" + "=" * 70)
        print("🎉 ALL REVIEWFLOW SAAS SERVICES ARE ONLINE & ACTIVE!")
        print("👉 Customer & Admin Dashboard: http://localhost:3000")
        print("👉 API Documentation (Swagger): http://localhost:8000/docs")
        print("=" * 70)
        print("\n[🛡️ Supervisor Active]: Auto-monitoring and self-healing enabled 24/7.\n")

        # Supervisor Watchdog Loop
        while True:
            time.sleep(2)
            for key, p in list(running_procs.items()):
                if p.poll() is not None:
                    print(f"\n[⚠️ Warning]: {service_defs[key]['name']} stopped unexpectedly! Auto-restarting...")
                    start_service(key)

    except KeyboardInterrupt:
        print("\n[🛑 Shutting down ReviewFlow services...]")
        for key, p in running_procs.items():
            try:
                p.terminate()
            except Exception:
                pass
        print("[✓] All services stopped cleanly.")

if __name__ == "__main__":
    main()
