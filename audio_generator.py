"""Audio generation module using TTS."""

import os


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
