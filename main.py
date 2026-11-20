"""
Entry point to run the Lagos Updates Directory server.
Usage: python3 main.py
"""
import sys
import os

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.app import run_server
from server.config import PORT

if __name__ == '__main__':
    run_server(PORT)
