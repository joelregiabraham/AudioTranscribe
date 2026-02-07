"""
File handling module for audio input validation and transcript output.

Supports validation of common audio formats and clean text file output
with configurable encoding and line formatting.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from utils.logger import get_logger

logger = get_logger(__name__)

# Supported audio extensions (lowercase, with dot)
SUPPORTED_EXTENSIONS: Final[frozenset[str]] = frozenset({
    ".mp3", ".wav", ".flac", ".m4a", ".mp4",
    ".ogg", ".wma", ".aac", ".opus", ".webm",
})

# File type filter string for file dialogs
FILETYPES: Final[list[tuple[str, str]]] = [
    ("Audio Files", " ".join(f"*{ext}" for ext in sorted(SUPPORTED_EXTENSIONS))),
    ("MP3", "*.mp3"),
    ("WAV", "*.wav"),
    ("FLAC", "*.flac"),
    ("M4A / MP4", "*.m4a *.mp4"),
    ("OGG / Opus", "*.ogg *.opus"),
    ("All Files", "*.*"),
]


def validate_audio_file(file_path: str | Path) -> Path:
    """
    Validate that the given path points to a supported audio file.

    Args:
        file_path: Path to the audio file.

    Returns:
        Resolved Path object.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file extension is not supported.
        PermissionError: If the file is not readable.
    """
    path = Path(file_path).resolve()

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if not path.is_file():
        raise ValueError(f"Not a file: {path}")

    if not path.suffix.lower() in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported format '{path.suffix}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    # Check read permission
    try:
        with open(path, "rb") as f:
            f.read(1)
    except PermissionError:
        raise PermissionError(f"Cannot read file: {path}")

    file_size_mb = path.stat().st_size / (1024 * 1024)
    logger.info("Validated audio file: %s (%.1f MB)", path.name, file_size_mb)

    return path


def get_file_size_display(file_path: Path) -> str:
    """Return a human-readable file size string."""
    size_bytes = file_path.stat().st_size
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def save_transcript(
    text: str,
    output_path: str | Path,
    encoding: str = "utf-8",
) -> Path:
    """
    Save transcribed text to a .txt file.

    Args:
        text: The transcription text to save.
        output_path: Destination file path.
        encoding: Text encoding (default UTF-8).

    Returns:
        The resolved Path where the file was saved.

    Raises:
        ValueError: If text is empty.
        OSError: If the file cannot be written.
    """
    if not text or not text.strip():
        raise ValueError("Transcript text is empty — nothing to save.")

    path = Path(output_path).resolve()

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Ensure .txt extension
    if path.suffix.lower() != ".txt":
        path = path.with_suffix(".txt")

    # Clean up text: normalize line endings, strip trailing whitespace
    cleaned = "\n".join(line.rstrip() for line in text.splitlines())
    cleaned = cleaned.strip() + "\n"

    path.write_text(cleaned, encoding=encoding)

    logger.info("Transcript saved: %s (%d characters)", path, len(cleaned))
    return path


def generate_output_path(input_path: Path, suffix: str = "_transcript") -> Path:
    """
    Generate a default output path based on the input audio file.

    Places the transcript in the same directory as the audio file.

    Args:
        input_path: Path to the source audio file.
        suffix: Suffix to append before .txt extension.

    Returns:
        A Path for the output transcript file.
    """
    return input_path.parent / f"{input_path.stem}{suffix}.txt"
