# Maminals

**Maminals** is an "Animal of the Day" generator that uses AI to fetch animal facts, generate TTS audio, download images (from Wikimedia Commons or Unsplash), create a video, and send it to a WhatsApp group.

## Project Structure

The project has been modularized into the following components:

- **`config.py`** - Configuration settings and constants
- **`animal_data.py`** - Animal name generation and information retrieval
- **`image_handler.py`** - Image downloading from Wikimedia Commons and Unsplash
- **`audio_generator.py`** - Text-to-speech audio generation using Coqui TTS
- **`video_creator.py`** - Video creation using FFmpeg
- **`whatsapp_sender.py`** - WhatsApp integration for sending videos
- **`utils.py`** - Utility functions for file operations and validation
- **`main.py`** - Main orchestration and CLI interface
- **`__init__.py`** - Package initialization

## Features
- Fetches a random animal name using OpenRouter AI
- Generates a concise animal description using OpenRouter AI
- Downloads animal images from Wikimedia Commons (preferred) or Unsplash (fallback)
- Generates TTS audio (WAV) using Coqui TTS (with optional voice cloning)
- Creates a video slideshow from images and audio using ffmpeg
- Sends the video to a WhatsApp group using [whatsapp-api](https://github.com/chrishubert/whatsapp-api)

## Requirements
- Python 3.10+
- [Coqui TTS](https://github.com/coqui-ai/TTS)
- ffmpeg
- [whatsapp-api](https://github.com/chrishubert/whatsapp-api)
- gcc
- espeak-ng / espeak
- Unsplash API key
- OpenRouter API key
- You may need python3-dev or equivalent providing Python.h

## Installation
1. Clone the repository.
2. Install dependencies using [uv](https://github.com/astral-sh/uv): (example for debian based systems with apt)
   ```bash
   sudo apt update
   sudo apt install python3-dev espeak-ng gcc ffmpeg
   uv venv
   source .venv/bin/activate
   uv pip install .
   ```
3. Ensure ffmpeg is installed and available in your PATH.
4. Set environment variables:
   - `OPENROUTER_API_KEY` (for animal info and name)
   - `UNSPLASH_ACCESS_KEY` (for Unsplash fallback images)
   - `WHATSAPP_CHAT_ID` (for WhatsApp video delivery)

## Usage

### Command Line
```bash
python main.py [animal_name] [--speaker_wav path/to/voice.wav] [--keep-images] [--output-resolution WIDTHxHEIGHT]
```
- If `animal_name` is omitted, a random animal will be chosen.
- If `--speaker_wav` is provided, voice cloning will be used for TTS.
- If `--keep-images` is set, downloaded images will be kept after video creation (default: images are deleted).
- Use `--output-resolution` to set the video resolution (default: 720x1280, e.g. `--output-resolution 1080x1920`).

### Example
```bash
export OPENROUTER_API_KEY=sk-...  # your OpenRouter key
export UNSPLASH_ACCESS_KEY=...    # your Unsplash key (optional, fallback)
export WHATSAPP_CHAT_ID=...@g.us  # WhatsApp chat id (optional)
python main.py "Pangolin"
```

### Programmatic Usage

You can also import and use the individual modules in your own Python code:

```python
from animal_data import get_animal_name, generate_animal_info
from image_handler import download_images, get_animal_photo_urls_wikimedia
from audio_generator import generate_audio
from video_creator import create_video_from_audio_and_images
from whatsapp_sender import send_video

# Generate animal content
animal_name = get_animal_name()
animal_info = generate_animal_info(animal_name)

# Get images
image_urls = get_animal_photo_urls_wikimedia(animal_name)
image_paths = download_images(image_urls, animal_name)

# Generate audio and video
audio_path = generate_audio(animal_name, animal_info)
video_path = create_video_from_audio_and_images(audio_path, image_paths, animal_name)

# Send via WhatsApp (optional)
send_video(video_path, "your_chat_id@g.us")
```

## Output
- Audio (Temporary): `output_audio/{animal_name}.wav` (deleted after video creation)
- Images (Temporary): `output_images/{animal_name}-xxxxxxxx.jpeg` (deleted after video creation unless `--keep-images` is set)
- Video: `output_video/{animal_name}.mp4`

## WhatsApp Integration
- The script will send the generated video to the WhatsApp group/chat
- Requires the [whatsapp-api](https://github.com/chrishubert/whatsapp-api) server running and authenticated.

## Project Structure
- `main.py` - Main script
- `pyproject.toml` - Python dependencies
- `output_audio/`, `output_images/`, `output_video/` - Output folders

## License
MIT

## Credits
- [Coqui TTS](https://github.com/coqui-ai/TTS)
- [OpenRouter](https://openrouter.ai/)
- [Unsplash](https://unsplash.com/)
- [whatsapp-api](https://github.com/chrishubert/whatsapp-api)
