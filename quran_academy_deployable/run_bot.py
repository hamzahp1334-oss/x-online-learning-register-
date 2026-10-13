"""Online Quran Academy — Telegram Bot Service Runner.

Run: python run_bot.py
"""
import os
import sys

# Ensure attendance/quran-academy is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from bot.runner import main

if __name__ == "__main__":
    main()
