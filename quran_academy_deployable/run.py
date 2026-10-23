"""Online Quran Academy — Shortcut runner for Render and CLI.

Delegates directly to start.py to run both Web Application and Telegram Bots concurrently.
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from start import main

if __name__ == "__main__":
    main()
