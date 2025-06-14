import os
import logging
from requests import post, get
from json import loads, dumps
from pathlib import Path
from typing import Optional
import subprocess
import sys

# --- Configuration ---
OUTPUT_IMAGE_DIR = Path("output_images")
OUTPUT_AUDIO_DIR = Path("output_audio")
OUTPUT_VIDEO_DIR = Path("output_video")
FFMPEG_RESOLUTION = (720, 1280)  # (width, height) for 9:16
FFMPEG_ASPECT = 9 / 16
FFMPEG_FPS = 15
FFMPEG_VF_FILTER = (
    f"scale='if(gt(a,{FFMPEG_ASPECT}),{FFMPEG_RESOLUTION[0]},-2)':'if(gt(a,{FFMPEG_ASPECT}),-2,{FFMPEG_RESOLUTION[1]})',"
    f"pad={FFMPEG_RESOLUTION[0]}:{FFMPEG_RESOLUTION[1]}:({FFMPEG_RESOLUTION[0]}-iw)/2:({FFMPEG_RESOLUTION[1]}-ih)/2:black,"
    f"crop={FFMPEG_RESOLUTION[0]}:{FFMPEG_RESOLUTION[1]}"
)

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def send_video(video_path: str, chat_id: str) -> None:
    """
    Send a video file to a specified WhatsApp chat using a local WhatsApp API server.

    Args:
        video_path (str): Path to the video file to send.
        chat_id (str): WhatsApp chat ID to send the video to.

    Returns:
        None
    """
    url = "http://127.0.0.1:3000/client/sendMessage/ABCD"
    try:
        with open(video_path, "rb") as video_file:
            resp = post(
                "https://tmpfiles.org/api/v1/upload", files={"file": video_file}
            )
    except Exception as e:
        logger.error(f"Error reading video file: {e}")
        return
    video_url = resp.json().get("data", {}).get("url", "").split("/")
    video_url.insert(3, "dl")
    video_url = "/".join(video_url)

    if not video_url:
        logger.error(f"Failed to upload video. Response: {resp.text}")
        return
    else:
        logger.info(f"Video uploaded successfully. URL: {video_url}")
    data = {
        "chatId": chat_id,
        "contentType": "MessageMediaFromURL",
        "content": video_url,
    }
    try:
        response = post(url, json=data)
        if response.status_code == 200:
            logger.info(f"Video sent successfully to chat {chat_id}")
        else:
            logger.error(
                f"Failed to send video. Status code: {response.status_code}, Response: {response.text}"
            )
    except Exception as e:
        logger.error(f"Error sending video: {e}")


def create_video_from_audio_and_images(
    audio_path: str,
    image_paths: list[str],
    animal_name: str,
    output_path: str = "output_video/{animal_name}.mp4",
    duration: int = None,
    keep_images: bool = False,
) -> str:
    import tempfile

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
    vf_filter = FFMPEG_VF_FILTER
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
    # Optionally clean up images (see below for CLI flag)
    if not keep_images:
        for img in image_paths:
            try:
                Path(img).unlink(missing_ok=True)
                logger.info(f"Removed image: {img}")
            except Exception as e:
                logger.warning(f"Error removing image {img}: {e}")
    return str(output_path)


def download_images(
    image_urls: list[str], animal_name: str, output_dir: str = "output_images"
) -> list[str]:
    """
    Download all images from the given URLs and save them to the output_images/ directory with the animal name as the filename.

    Args:
        image_urls (list[str]): List of image URLs to download.
        animal_name (str): Name of the animal (used in filenames).
        output_dir (str, optional): Directory to save images. Defaults to "output_images".

    Returns:
        list[str]: List of paths to the saved images.
    """
    OUTPUT_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from tqdm import tqdm
    import re

    def sanitize_filename(filename: str) -> str:
        # Remove or replace problematic characters for all filesystems
        return re.sub(r"[^\w\-.]", "_", filename)

    def download_one(image_url: str) -> Optional[str]:
        try:
            # Only allow image URLs with valid image extensions
            if image_url.startswith("https://unsplash.com/photos/"):
                filename = (
                    f"{animal_name}.{image_url.split('photo-')[1].split('?')[0]}.jpeg"
                )
            else:
                valid_exts = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")
                url_lower = image_url.lower()
                if not any(url_lower.endswith(ext) for ext in valid_exts):
                    logger.info(f"Skipping non-image URL: {image_url}")
                    return None
                filename = image_url.split("/")[-1]
            filename = sanitize_filename(filename)
            output_path = OUTPUT_IMAGE_DIR / filename
            try:
                response = get(
                    image_url,
                    stream=True,
                    headers={
                        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
                    },
                )
            except Exception as e:
                logger.warning(f"Error requesting {image_url}: {e}")
                return None
            if response.status_code == 200:
                try:
                    with open(output_path, "wb") as f:
                        for chunk in response.iter_content(1024):
                            f.write(chunk)
                    return str(output_path)
                except Exception as e:
                    logger.warning(f"Error saving image {output_path}: {e}")
                    return None
            else:
                logger.warning(
                    f"Failed to download {image_url}: Status code {response.status_code}"
                )
                return None
        except Exception as e:
            logger.warning(f"Error processing image URL {image_url}: {e}")
            return None

    output_paths = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(download_one, url) for url in image_urls]
        for future in tqdm(
            as_completed(futures), total=len(futures), desc="Downloading images"
        ):
            result = future.result()
            if result:
                output_paths.append(result)
    return output_paths


def get_animal_photo_urls_unsplash(animal_name: str) -> list[str] | str:
    """
    Retrieve the URLs of the first 25 images of the animal from Unsplash.

    Args:
        animal_name (str): Name of the animal to search for.

    Returns:
        list[str] | str: List of image URLs or error message.
    """
    access_key = os.getenv("UNSPLASH_ACCESS_KEY")
    if not access_key:
        raise ValueError(
            "Unsplash API access key not found. Please set the UNSPLASH_ACCESS_KEY environment variable."
        )
    url = "https://api.unsplash.com/search/photos"
    params = {"query": animal_name, "per_page": 25, "client_id": access_key}
    response = get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        results = data.get("results", [])
        if results:
            return [
                result["urls"]["regular"]
                for result in results
                if "urls" in result and "regular" in result["urls"]
            ]
        else:
            return "No images found."
    else:
        return f"Error: {response.status_code} - {response.text}"


def get_animal_photo_urls_wikimedia(animal_name: str) -> list[str] | str:
    """
    Retrieve URLs of animal images from Wikimedia Commons

    Args:
        animal_name (str): Name of the animal to search for.

    Returns:
        list[str] | str: List of image URLs or error message.
    """
    url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "generator": "images",
        "titles": animal_name,
        "prop": "imageinfo",
        "redirects": 1,
        "gimlimit": "200",
        "iiprop": "url",
    }
    try:
        response = get(url, params=params, timeout=10)
        print(response.text)
        if response.status_code == 200:
            data = response.json()
            pages = data.get("query", {}).get("pages", {})
            image_urls = []
            for page in pages.values():
                imageinfo = page.get("imageinfo", [])
                if imageinfo:
                    image_urls.append(
                        imageinfo[0].get("thumburl") or imageinfo[0].get("url")
                    )
            if image_urls:
                return image_urls
            else:
                return "No images found."
        else:
            return f"Error: {response.status_code} - {response.text}"
    except Exception as e:
        return f"Error: {e}"


def generate_animal_info(animal_name: str) -> str:
    """
    Generate a string containing information about the given animal.

    Args:
        animal_name (str): The name of the animal.

    Returns:
        str: A string containing the animal's name and a brief description.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError(
            "API key not found. Please set the OPENROUTER_API_KEY environment variable."
        )
    response = post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        data=dumps(
            {
                "model": "google/gemma-3n-e4b-it:free",
                "messages": [
                    {
                        "role": "user",
                        "content": f"Give me a brief description of the animal named {animal_name}. Use information from wikipedia and other reliable sources. Include its habitat, diet, size, scientific name and any interesting facts. The response should be concise and informative, suitable for a general audience. The response will be read out loud by a text-to-speech system, so it should be clear and easy to understand. Return the information in a single paragraph without any additional text or formatting.",
                    }
                ],
            }
        ),
    )
    if response.status_code == 200:
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    else:
        return f"Error: {response.status_code} - {response.text}"


def get_animal_name(animal_list_path: Path = Path("animal_names.json")) -> str:
    """
    Return a random animal name from a JSON file containing a list of animal names.
    If the file does not exist or is empty, raise an error.

    Returns:
        str: A unique animal name, or an error message if the API fails.
    """
    animal_list_path = animal_list_path.resolve()
    if not animal_list_path.exists():
        raise FileNotFoundError(
            f"Animal names file not found: {animal_list_path}. Please ensure the file exists."
        )

    animal_list = animal_list_path.read_text(encoding="utf-8")
    animal_list = loads(animal_list)

    if not animal_list:
        raise ValueError(
            "Animal names list is empty. Please check the animal_names.json file."
        )

    import random

    animal_name = random.choice(animal_list).strip()
    if not animal_name:
        raise ValueError(
            "Generated animal name is empty. Please check the animal_names.json file."
        )
    logger.info(f"Generated animal name: {animal_name}")

    previous_names = read_previous_animal_names()
    if animal_name in previous_names:
        logger.warning(
            f"Generated animal name '{animal_name}' has been used before. Generating a new name..."
        )
        return get_animal_name(animal_list_path)

    return animal_name


def read_previous_animal_names() -> list:
    """
    Read previously generated animal names from a file.

    Returns:
        list: A list of previously generated animal names.
    """
    try:
        with open("previous_animal_names.txt", "r") as file:
            return [line.strip() for line in file.readlines()]
    except FileNotFoundError:
        return []


def save_animal_name(animal_name: str) -> None:
    """
    Save the given animal name to a file.

    Args:
        animal_name (str): The name of the animal to save.

    Returns:
        None
    """
    with open("previous_animal_names.txt", "a") as file:
        file.write(animal_name + "\n")


def generate_audio(
    animal_name: str, animal_info: str, speaker_wav: str | None = None
) -> str:
    """
    Generate an audio file from the given animal information.

    Args:
        animal_name (str): The name of the animal.
        animal_info (str): The information about the animal to convert to audio.
        speaker_wav (str|None): The path to the speaker WAV file to use for voice cloning (optional).

    Returns:
        str: The path to the generated audio file.
    """
    from TTS.api import TTS
    import torch

    os.makedirs("output_audio", exist_ok=True)

    animal_name = animal_name.replace(" ", "_").replace("/", "_")
    animal_info = animal_info.replace("*", "")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    if speaker_wav and os.path.exists(speaker_wav):
        print(f"Using speaker WAV file: {speaker_wav}")
        # Use XTTS v2 for voice cloning
        model = "tts_models/multilingual/multi-dataset/xtts_v2"
        tts = TTS(model_name=model, progress_bar=True).to(device)
        tts.tts_to_file(
            text=animal_info,
            file_path=f"output_audio/{animal_name}.wav",
            speaker_wav=speaker_wav,
            language="en",
            # Add these parameters for better quality
            temperature=0.75,  # Controls randomness (0.1-1.0)
            length_penalty=1.0,  # Controls speech speed
            repetition_penalty=5.0,  # Reduces repetition
            top_k=50,  # Limits vocabulary for more consistent output
            top_p=0.85,  # Nucleus sampling for better quality
        )
    else:
        # Fallback to standard TTS
        model = "tts_models/en/ljspeech/vits"
        tts = TTS(model_name=model, progress_bar=True).to(device)
        tts.tts_to_file(text=animal_info, file_path=f"output_audio/{animal_name}.wav")

    return f"output_audio/{animal_name}.wav"


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
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(file_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        duration = float(loads(result.stdout)["format"]["duration"])
        logger.info(f"File {file_path} duration: {duration:.2f} seconds")
        return duration >= min_duration
    except (subprocess.CalledProcessError, KeyError, ValueError, TypeError) as e:
        logger.error(f"Error checking duration for {file_path}: {e}")
        return False


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate animal info and audio.")
    parser.add_argument(
        "animal_name",
        type=str,
        nargs="?",
        help="Name of the animal to use (optional, if not provided, will be generated)",
    )
    parser.add_argument(
        "--speaker_wav",
        type=str,
        help="Path to the speaker WAV file for voice cloning (optional)",
    )
    parser.add_argument(
        "--keep-images",
        action="store_true",
        help="Keep downloaded images after video creation (default: delete)",
    )
    parser.add_argument(
        "--output-resolution",
        type=str,
        default=f"{FFMPEG_RESOLUTION[0]}x{FFMPEG_RESOLUTION[1]}",
        help="Output video resolution as WIDTHxHEIGHT (default: 720x1280)",
    )
    args, _ = parser.parse_known_args()

    # Update ffmpeg filter if output resolution is overridden
    if args.output_resolution:
        try:
            width, height = map(int, args.output_resolution.lower().split("x"))
            globals()["FFMPEG_RESOLUTION"] = (width, height)
            aspect = width / height
            globals()["FFMPEG_VF_FILTER"] = (
                f"scale='if(gt(a,{aspect}),{width},-2)':'if(gt(a,{aspect}),-2,{height})',"
                f"pad={width}:{height}:({width}-iw)/2:({height}-ih)/2:black,"
                f"crop={width}:{height}"
            )
        except Exception as e:
            logger.warning(
                f"Invalid --output-resolution: {args.output_resolution}, using default. Error: {e}"
            )

    try:
        if args.animal_name:
            animal_name = args.animal_name.strip()
        else:
            animal_name = get_animal_name().strip()

        if animal_name.startswith("Error:"):
            logger.error(f"Failed to generate animal name: {animal_name}")
            sys.exit(1)
        logger.info(f"Animal Name: {animal_name}")

        animal_info = generate_animal_info(animal_name)
        if animal_info.startswith("Error:"):
            logger.error(f"Failed to generate animal info: {animal_info}")
            sys.exit(1)
        logger.info(f"Animal Info: {animal_info}")

        audio_file_path = generate_audio(
            animal_name, animal_info, speaker_wav=args.speaker_wav
        )
        logger.info(f"Audio file generated at: {audio_file_path}")

        # Check audio duration requirement (minimum 30 seconds)
        if not check_file_duration(audio_file_path, 30.0):
            logger.error(
                f"Generated audio file {audio_file_path} is shorter than 30 seconds. Exiting."
            )
            sys.exit(1)

        image_urls = get_animal_photo_urls_wikimedia(animal_name)
        if isinstance(image_urls, str):
            logger.warning(
                f"Failed to retrieve image URLs from wikimedia: {image_urls}"
            )
            logger.info("Trying to retrieve image URLs from Unsplash...")
            image_urls = get_animal_photo_urls_unsplash(animal_name)
            if isinstance(image_urls, str):
                logger.error(
                    f"Failed to retrieve image URLs from Unsplash: {image_urls}"
                )
                sys.exit(1)
        logger.debug(f"Image URLs: {image_urls}")

        image_paths = download_images(image_urls, animal_name)
        if len(image_paths) == 0:
            logger.error("No images were downloaded. Exiting.")
            sys.exit(1)
        logger.debug(f"Images downloaded at: {image_paths}")

        video_file_path = create_video_from_audio_and_images(
            audio_file_path, image_paths, animal_name, keep_images=args.keep_images
        )
        if video_file_path == "":
            logger.error("Failed to create video from audio and images.")
            sys.exit(1)
        logger.info(f"Video file created at: {video_file_path}")

        # Check video duration requirement (minimum 30 seconds)
        if not check_file_duration(video_file_path, 30.0):
            logger.error(
                f"Generated video file {video_file_path} is shorter than 30 seconds. Exiting."
            )
            sys.exit(1)

        chat_id = os.environ.get("WHATSAPP_CHAT_ID")
        if not chat_id:
            logger.warning(
                "WhatsApp chat ID not set. Please set the WHATSAPP_CHAT_ID environment variable."
            )
        else:
            send_video(video_file_path, chat_id)

        # Optionally clean up audio file
        try:
            Path(audio_file_path).unlink(missing_ok=True)
            logger.info(f"Removed audio file: {audio_file_path}")
        except Exception as e:
            logger.warning(f"Error removing audio file: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in main: {e}")


if __name__ == "__main__":
    main()
