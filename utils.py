"""Utility functions for file operations and validation."""

import subprocess
from json import loads
from pathlib import Path
from config import logger


def check_file_duration(file_path: str, min_duration: float = 30.0) -> bool:
    """
    Check if an audio or video file meets the minimum duration requirement.

    Args:
        file_path (str): Path to the audio or video file.
        min_duration (float): Minimum required duration in seconds. Defaults to 30.0.

    Returns:
        bool: True if duration meets requirement, False otherwise.
    """
    try:
        # More efficient duration check using csv output
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                str(file_path),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        duration = float(result.stdout.strip())
        logger.info(f"File {file_path} duration: {duration:.2f} seconds")
        return duration >= min_duration
    except (subprocess.CalledProcessError, ValueError, subprocess.TimeoutExpired) as e:
        logger.error(f"Error checking duration for {file_path}: {e}")
        return False


def cleanup_file(file_path: str) -> None:
    """
    Safely remove a file.

    Args:
        file_path (str): Path to the file to remove.
    """
    try:
        Path(file_path).unlink(missing_ok=True)
        logger.info(f"Removed file: {file_path}")
    except Exception as e:
        logger.warning(f"Error removing file {file_path}: {e}")


def ensure_directory_exists(directory: Path) -> None:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        directory (Path): Directory path to create.
    """
    directory.mkdir(parents=True, exist_ok=True)
