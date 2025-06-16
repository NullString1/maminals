"""Configuration settings for the maminals project."""

import logging
from pathlib import Path

# --- Directory Configuration ---
OUTPUT_IMAGE_DIR = Path("output_images")
OUTPUT_AUDIO_DIR = Path("output_audio")
OUTPUT_VIDEO_DIR = Path("output_video")

# --- FFmpeg Configuration ---
FFMPEG_RESOLUTION = (720, 1280)  # (width, height) for 9:16
FFMPEG_ASPECT = 9 / 16
FFMPEG_FPS = 15


def get_ffmpeg_filter(resolution=None, aspect=None):
    """Generate FFmpeg video filter string."""
    res = resolution or FFMPEG_RESOLUTION
    asp = aspect or FFMPEG_ASPECT

    return (
        f"scale='if(gt(a,{asp}),{res[0]},-2)':'if(gt(a,{asp}),-2,{res[1]})',"
        f"pad={res[0]}:{res[1]}:({res[0]}-iw)/2:({res[1]}-ih)/2:black,"
        f"crop={res[0]}:{res[1]}"
    )


FFMPEG_VF_FILTER = get_ffmpeg_filter()


# --- Logging Setup ---
def setup_logging():
    """Configure logging for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    return logging.getLogger(__name__)


# Create logger instance
logger = setup_logging()
