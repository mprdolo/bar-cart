"""Silent launcher for Bar Cart — no console window."""
import os
import sys
import webbrowser
import threading

# Ensure working directory is the script's folder
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Suppress stdout/stderr (no console to write to with pythonw)
sys.stdout = open(os.devnull, "w")
sys.stderr = open(os.devnull, "w")

from app import app

PORT = 3346

def open_browser():
    webbrowser.open(f"http://localhost:{PORT}")

threading.Timer(1.0, open_browser).start()
app.run(port=PORT)
