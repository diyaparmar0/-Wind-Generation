import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.app.main import app  # Vercel serves this ASGI app
