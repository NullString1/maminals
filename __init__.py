"""Maminals package for generating animal videos with TTS."""

__version__ = "1.1.0"
__author__ = "Maminals Project"
__description__ = "Generate educational animal videos with text-to-speech narration"

from . import config
from . import animal_data
from . import image_handler
from . import audio_generator
from . import video_creator
from . import whatsapp_sender
from . import utils
from . import cache
from . import performance

__all__ = [
    "config",
    "animal_data",
    "image_handler",
    "audio_generator",
    "video_creator",
    "whatsapp_sender",
    "utils",
    "cache",
    "performance",
]
