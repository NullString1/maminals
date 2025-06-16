"""Video creation module using FFmpeg."""

import subprocess
import tempfile
from json import loads
from pathlib import Path
from config import OUTPUT_VIDEO_DIR, FFMPEG_FPS, FFMPEG_VF_FILTER, logger


def create_video_from_audio_and_images(
    audio_path: str,
    image_paths: list[str],
    animal_name: str,
    output_path: str = "output_video/{animal_name}.mp4",
    duration: int = None,
    keep_images: bool = False,
    vf_filter: str = None,
) -> str:
    """
    Create a video from the given audio file and a list of image files using ffmpeg.

    The images will be shown in sequence, each for an equal duration, or the first image will be looped if only one is provided.
    If duration is not provided, it will be set to the audio length.

    Args:
        audio_path (str): Path to the audio file.
        image_paths (list[str]): List of image file paths.
        animal_name (str): Name of the animal (used in output filename).
        output_path (str, optional): Output video path template. Defaults to "output_video/{animal_name}.mp4".
        duration (int, optional): Duration of the video in seconds. Defaults to None.
        keep_images (bool, optional): Whether to keep images after video creation. Defaults to False.
        vf_filter (str, optional): Custom video filter. Defaults to None (uses config default).

    Returns:
        str: Path to the generated video file.
    """
    OUTPUT_VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    if not image_paths:
        raise ValueError("No image paths provided.")

    if duration is None:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        duration = float(loads(result.stdout)["format"]["duration"])

    with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".txt") as f:
        list_file = f.name
        if len(image_paths) == 1:
            abs_path = Path(image_paths[0]).resolve()
            f.write(f"file '{abs_path}'\nduration {duration}\n")
            f.write(f"file '{abs_path}'\n")
        else:
            per_image = duration / len(image_paths)
            for img in image_paths:
                abs_path = Path(img).resolve()
                f.write(f"file '{abs_path}'\nduration {per_image}\n")
            f.write(f"file '{abs_path}'\n")

    output_path = Path(str(output_path).format(animal_name=animal_name))
    vf_filter = vf_filter or FFMPEG_VF_FILTER
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        list_file,
        "-i",
        str(audio_path),
        "-vf",
        vf_filter,
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-r",
        str(FFMPEG_FPS),
        "-shortest",
        str(output_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running ffmpeg: {e.stderr}")
        return ""
    finally:
        try:
            Path(list_file).unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"Error removing ffmpeg list file: {e}")

    # Optionally clean up images
    if not keep_images:
        for img in image_paths:
            try:
                Path(img).unlink(missing_ok=True)
                logger.info(f"Removed image: {img}")
            except Exception as e:
                logger.warning(f"Error removing image {img}: {e}")

    return str(output_path)
