import sys
import os

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from server.app import DirectoryAppHandler
from server.db import init_db

# Initialize database on cold start
try:
    init_db()
except Exception as e:
    print(f"Error initializing DB: {e}")

class handler(DirectoryAppHandler):
    pass
