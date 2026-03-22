import os
import sys
from dotenv import load_dotenv

# Load .env FIRST before anything else
load_dotenv()

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
    base_url = os.getenv("BASE_URL", "NOT SET")
    print(f"BASE_URL = {base_url}")
    try:
        from waitress import serve
        print(f"CareCloud running on http://0.0.0.0:{port} with Waitress (8 threads)")
        serve(app, host="0.0.0.0", port=port, threads=8)
    except ImportError:
        app.run(host="0.0.0.0", port=port, debug=False, threaded=True)