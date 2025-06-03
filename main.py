import os
from requests import post, get
from json import loads, dumps


def send_video(video_path: str, chat_id: str) -> None:
    """
    Send a video file to a specified WhatsApp chat using a local WhatsApp API server.

    Args:
        video_path (str): Path to the video file to send.
        chat_id (str): WhatsApp chat ID to send the video to.

    Returns:
        None
    """
    from base64 import b64encode

    url = "http://127.0.0.1:3000/client/sendMessage/ABCD"
    try:
        with open(video_path, "rb") as video_file:
            encoded_data = b64encode(video_file.read()).decode()
    except Exception as e:
        print(f"Error reading video file: {e}")
        return
    data = {
        "chatId": chat_id,
        "contentType": "MessageMedia",
        "content": {
            "mimetype": "video/mp4",
            "filename": os.path.basename(video_path),
            "data": encoded_data,
        },
    }
    try:
        response = post(url, json=data)
        if response.status_code == 200:
            print(f"Video sent successfully to chat {chat_id}")
        else:
            print(
                f"Failed to send video. Status code: {response.status_code}, Response: {response.text}"
            )
    except Exception as e:
        print(f"Error sending video: {e}")


def create_video_from_audio_and_images(
    audio_path: str,
    image_paths: list[str],
    animal_name: str,
    output_path: str = "output_video/{animal_name}.mp4",
    duration: int = None,
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

    Returns:
        str: Path to the generated video file.
    """
    from subprocess import run
    from pathlib import Path

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    if not image_paths:
        raise ValueError("No image paths provided.")

    if duration is None:
        import wave
        import contextlib

        if audio_path.endswith(".mp3"):
            result = run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "json",
                    audio_path,
                ],
                capture_output=True,
                text=True,
            )
            duration = float(loads(result.stdout)["format"]["duration"])
        else:
            with contextlib.closing(wave.open(audio_path, "r")) as f:
                frames = f.getnframes()
                rate = f.getframerate()
                duration = frames / float(rate)
    list_file = "ffmpeg_images.txt"
    with open(list_file, "w") as f:
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
    output_path = output_path.format(animal_name=animal_name)
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
        audio_path,
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-r",
        "15",
        "-shortest",
        output_path,
    ]
    try:
        result = run(cmd, capture_output=True, text=True)
    except Exception as e:
        print(f"Error running ffmpeg: {e}")
        return ""
    try:
        os.remove(list_file)
    except Exception as e:
        print(f"Error removing ffmpeg list file: {e}")
    for img in image_paths:
        try:
            if os.path.exists(img):
                os.remove(img)
        except Exception as e:
            print(f"Error removing image {img}: {e}")
    if result.returncode != 0:
        print(f"ffmpeg failed: {result.stderr}")
        return ""
    return output_path


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
    os.makedirs(output_dir, exist_ok=True)
    output_paths = []
    for image_url in image_urls:
        try:
            filename = (
                f"{animal_name}.{image_url.split('photo-')[1].split('?')[0]}.jpeg"
            )
            output_path = os.path.join(output_dir, filename)
            try:
                response = get(image_url, stream=True)
            except Exception as e:
                print(f"Error requesting {image_url}: {e}")
                continue
            if response.status_code == 200:
                try:
                    with open(output_path, "wb") as f:
                        for chunk in response.iter_content(1024):
                            f.write(chunk)
                    output_paths.append(output_path)
                except Exception as e:
                    print(f"Error saving image {output_path}: {e}")
            else:
                print(
                    f"Failed to download {image_url}: Status code {response.status_code}"
                )
        except Exception as e:
            print(f"Error processing image URL {image_url}: {e}")
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


def get_animal_name() -> str:
    """
    Generate a random animal name that has not been used in previous requests.

    Returns:
        str: A unique animal name, or an error message if the API fails.
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
                        "content": f"Give me the name of an animal that I can use to generate information about it. The animal can be any species, including mammals, birds, reptiles, amphibians, fish, or insects. Return only the name of the animal without any additional text. Do not repeat the same animal name that has been used in previous requests. Here are some previously generated animal names: {', '.join(read_previous_animal_names())}.",
                    }
                ],
            }
        ),
    )
    if response.status_code == 200:
        data: str = response.json()["choices"][0]["message"]["content"]
        data = data.strip()
        save_animal_name(data)
        return data
    else:
        return f"Error: {response.status_code} - {response.text}"


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
        file.write(animal_name)


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
    import ffmpeg.audio as ffmpeg

    os.makedirs("output_audio", exist_ok=True)

    animal_info = animal_info.replace("*", "")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    if speaker_wav and os.path.exists(speaker_wav):
        print(f"Using speaker WAV file: {speaker_wav}")
        model = "tts_models/multilingual/multi-dataset/xtts_v2"
    else:
        model = "tts_models/en/ljspeech/vits"
    tts = TTS(model_name=model, progress_bar=True).to(device)
    tts.tts_to_file(
        text=animal_info,
        file_path=f"output_audio/{animal_name}.wav",
        speaker_wav=speaker_wav,
        language="en" if model.startswith("tts_models/multilingual") else None,
    )
    if ffmpeg.a_speed(
        f"output_audio/{animal_name}.wav", 1.0, f"output_audio/{animal_name}.mp3"
    ):
        os.remove(f"output_audio/{animal_name}.wav")
        return f"output_audio/{animal_name}.mp3"
    else:
        print(f"Error converting audio to MP3 format for {animal_name}.wav")
        return f"output_audio/{animal_name}.wav"


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
    args, _ = parser.parse_known_args()

    try:
        if args.animal_name:
            animal_name = args.animal_name.strip()
        else:
            animal_name = get_animal_name().strip()
        if animal_name.startswith("Error:"):
            print(f"Failed to generate animal name: {animal_name}")
            return
        print(f"Animal Name: {animal_name}")
        animal_info = generate_animal_info(animal_name)
        if animal_info.startswith("Error:"):
            print(f"Failed to generate animal info: {animal_info}")
            return
        print(f"Animal Info: {animal_info}")
        audio_file_path = generate_audio(
            animal_name, animal_info, speaker_wav=args.speaker_wav
        )
        print(f"Audio file generated at: {audio_file_path}")
        image_urls = get_animal_photo_urls_unsplash(animal_name)
        print(f"Image URLs: {image_urls}")
        image_paths = download_images(image_urls, animal_name)
        print(f"Images downloaded at: {image_paths}")
        video_file_path = create_video_from_audio_and_images(
            audio_file_path, image_paths, animal_name
        )
        print(f"Video file created at: {video_file_path}")

        chat_id = os.environ.get("WHATSAPP_CHAT_ID")
        if not chat_id:
            print(
                "WhatsApp chat ID not set. Please set the WHATSAPP_CHAT_ID environment variable."
            )
        else:
            send_video(video_file_path, chat_id)

        print("Cleanup: Removing temporary files...")

        for img in image_paths:
            try:
                if os.path.exists(img):
                    os.remove(img)
                    print(f"Removed image: {img}")
            except Exception as e:
                print(f"Error removing image {img}: {e}")
        try:
            if os.path.exists(audio_file_path):
                os.remove(audio_file_path)
                print(f"Removed audio file: {audio_file_path}")
        except Exception as e:
            print(f"Error removing audio file: {e}")
    except Exception as e:
        print(f"Unexpected error in main: {e}")


if __name__ == "__main__":
    main()
