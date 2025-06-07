# Maminals

**Maminals** is an "Animal of the Day" generator that uses AI to fetch animal facts, generate TTS audio, download images (from Wikimedia Commons or Unsplash), create a video, and send it to a WhatsApp group.

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
