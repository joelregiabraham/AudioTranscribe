"""
Audio Transcriber — Entry Point

A local, offline audio transcription tool using faster-whisper
with a modern dark-themed CustomTkinter GUI.

Usage:
    python main.py
"""

import sys

import customtkinter as ctk

from utils.logger import get_logger


def main() -> None:
    """Initialize and run the application."""
    logger = get_logger("transcriber")
    logger.info("=" * 60)
    logger.info("Audio Transcriber starting up")
    logger.info("Python %s", sys.version)
    logger.info("=" * 60)

    # CustomTkinter global settings
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    # Import here to ensure logger is initialized first
    from ui.app import TranscriberApp

    app = TranscriberApp()
    app.mainloop()

    logger.info("Application shut down cleanly.")


if __name__ == "__main__":
    main()
