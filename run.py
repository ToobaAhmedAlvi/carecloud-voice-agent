"""
CareCloud — Entry Point
Uses Waitress (multi-threaded) to avoid Flask single-thread timeout issues.
Run: python run.py
"""
import os
import sys

# Fix Windows console Unicode encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app.main import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    try:
        from waitress import serve
        print(f"CareCloud running on http://0.0.0.0:{port} with Waitress (8 threads)")
        serve(app, host="0.0.0.0", port=port, threads=8)
    except ImportError:
        print("Waitress not found, falling back to Flask dev server (threaded)")
        app.run(host="0.0.0.0", port=port, debug=False, threaded=True)