import subprocess
import time
import os
import sys

def run():
    """
    Helper script to run both the FastAPI backend and Next.js frontend concurrently.
    """
    print("=" * 50)
    print("🚀 Starting CBSE Answer Sheet Evaluation System")
    print("=" * 50)
    
    # 1. Start FastAPI Backend
    print("\n[1/2] Launching FastAPI Backend (Port 8000)...")
    # Use 'uv run' to ensure the correct environment and tools are used.
    # We call uvicorn directly if installed via uv pip, but 'uv run uvicorn' or 'uv run python -m uvicorn' is safer.
    backend_cmd = ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
    
    backend_env = os.environ.copy()
    backend_env["PYTHONPATH"] = os.getcwd()
    
    backend_process = subprocess.Popen(
        backend_cmd,
        cwd=os.getcwd(),
        env=backend_env
    )
    
    # Wait a bit for backend to bind to port
    time.sleep(3)
    
    # 2. Start Next.js Frontend
    print("\n[2/2] Launching Next.js Frontend (Port 3000)...")
    # Note: On Windows, npm is sometimes npm.cmd
    npm_cmd = "npm.cmd" if os.name == 'nt' else "npm"
    frontend_process = subprocess.Popen(
        [npm_cmd, "run", "dev"],
        cwd=os.path.join(os.getcwd(), "frontend-next")
    )
    
    print("\n" + "=" * 50)
    print("✅ System successfully started!")
    print(f"👉 Frontend: http://localhost:3000")
    print(f"👉 API Docs: http://localhost:8000/docs")
    print("=" * 50)
    print("\n[Logs will appear below. Press Ctrl+C to terminate both services.]\n")
    
    try:
        # Keep the script alive and monitor processes
        while True:
            time.sleep(1)
            if backend_process.poll() is not None:
                print("\n❌ Backend process has stopped. Terminating frontend...")
                break
            if frontend_process.poll() is not None:
                print("\n❌ Frontend process has stopped. Terminating backend...")
                break
    except KeyboardInterrupt:
        print("\n\n👋 Gracefully shutting down...")
    finally:
        # Cleanup
        backend_process.terminate()
        frontend_process.terminate()
        print("Done.")

if __name__ == "__main__":
    run()
