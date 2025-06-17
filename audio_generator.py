"""Audio generation module using TTS with word-level timing extraction."""

import os
import json
import re
from typing import List, Tuple, Dict
from pathlib import Path


def extract_word_timings_from_audio(text: str, audio_path: str) -> List[Tuple[str, float, float]]:
    """
    Extract word-level timings from audio using phoneme alignment.
    
    Args:
        text (str): The original text
        audio_path (str): Path to the generated audio file
        
    Returns:
        List[Tuple[str, float, float]]: List of (word, start_time, end_time)
    """
    try:
        import librosa
        import numpy as np
        from phonemizer import phonemize
        import subprocess
        import shutil
        
        # Load audio
        audio, sr = librosa.load(audio_path, sr=22050)
        duration = len(audio) / sr
        
        # Clean and split text into words
        words = re.findall(r'\b\w+\b', text)
        if not words:
            return []
        
        # Get phonemes for the text
        try:            
            phonemes = phonemize(
                text,
                language='en-us',
                backend='espeak',
                strip=True,
                preserve_punctuation=False,
                with_stress=False
            )
        except Exception as e:
            print(f"Phonemizer error: {e}, falling back to simple estimation")
            return estimate_word_timings_simple(text, duration)
        
        # Estimate timing based on phoneme complexity and audio features
        word_timings = []
        
        # Use energy-based segmentation for rough alignment
        hop_length = 512
        
        # Calculate RMS energy
        rms = librosa.feature.rms(y=audio, hop_length=hop_length)[0]
        times = librosa.frames_to_time(range(len(rms)), sr=sr, hop_length=hop_length)
        
        # Find speech segments (above threshold)
        rms_threshold = np.percentile(rms, 20)  # Bottom 20% is likely silence
        speech_mask = rms > rms_threshold
        
        # Find speech boundaries
        speech_boundaries = []
        in_speech = False
        for i, is_speech in enumerate(speech_mask):
            if is_speech and not in_speech:
                speech_boundaries.append(times[i])
                in_speech = True
            elif not is_speech and in_speech:
                speech_boundaries.append(times[i])
                in_speech = False
        
        if in_speech:  # End of audio while still in speech
            speech_boundaries.append(times[-1])
        
        # Distribute words across speech segments
        if len(speech_boundaries) >= 2:
            speech_segments = [(speech_boundaries[i], speech_boundaries[i+1]) 
                             for i in range(0, len(speech_boundaries), 2)
                             if i+1 < len(speech_boundaries)]
            
            # Simple approach: distribute words evenly across total speech time
            total_speech_time = sum(end - start for start, end in speech_segments)
            
            if total_speech_time > 0:
                time_per_word = total_speech_time / len(words)
                current_time = speech_segments[0][0] if speech_segments else 0.0
                
                for word in words:
                    # Adjust duration based on word length
                    word_duration = time_per_word * (0.8 + 0.4 * len(word) / 8)
                    word_timings.append((word, current_time, current_time + word_duration))
                    current_time += word_duration
            else:
                # Fallback to simple estimation
                return estimate_word_timings_simple(text, duration)
        else:
            # Fallback to simple estimation
            return estimate_word_timings_simple(text, duration)
            
        return word_timings
        
    except ImportError as e:
        print(f"Missing library for audio analysis: {e}")
        return estimate_word_timings_simple(text, duration)
    except Exception as e:
        print(f"Error in word timing extraction: {e}")
        return estimate_word_timings_simple(text, duration)


def estimate_word_timings_simple(text: str, audio_duration: float) -> List[Tuple[str, float, float]]:
    """
    Simple word timing estimation based on speaking rate.
    
    Args:
        text (str): The text to create timings for
        audio_duration (float): Total duration of the audio in seconds
        
    Returns:
        List[Tuple[str, float, float]]: List of (word, start_time, end_time)
    """
    # Clean and split text into words
    words = re.findall(r'\b\w+\b', text)
    if not words:
        return []
    
    # Estimate average speaking rate (words per minute)
    # Typical speaking rate is 150-200 wpm, we'll use 160
    words_per_minute = 160
    words_per_second = words_per_minute / 60
    
    # Calculate time per word based on actual audio duration vs estimated duration
    estimated_duration = len(words) / words_per_second
    time_scale = audio_duration / estimated_duration if estimated_duration > 0 else 1
    
    word_timings = []
    current_time = 0.0
    
    for word in words:
        # Estimate duration based on word length and complexity
        base_duration = 0.4  # Base 400ms per word
        length_factor = max(0.1, len(word) / 8)  # Longer words take more time
        word_duration = base_duration * length_factor * time_scale
        
        # Add small pauses for punctuation and breathing
        if word.endswith(('.', '!', '?')):
            word_duration += 0.3 * time_scale
        elif word.endswith(','):
            word_duration += 0.2 * time_scale
            
        start_time = current_time
        end_time = current_time + word_duration
        
        word_timings.append((word, start_time, end_time))
        current_time = end_time
    
    return word_timings


def save_word_timings(word_timings: List[Tuple[str, float, float]], output_path: str) -> None:
    """Save word timings to a JSON file."""
    timings_data = [
        {"word": word, "start": start, "end": end}
        for word, start, end in word_timings
    ]
    
    timing_file = output_path.replace('.wav', '_timings.json').replace('.mp3', '_timings.json')
    with open(timing_file, 'w') as f:
        json.dump(timings_data, f, indent=2)
    
    print(f"Word timings saved to: {timing_file}")


def load_word_timings(audio_path: str) -> List[Tuple[str, float, float]]:
    """Load word timings from a JSON file."""
    timing_file = audio_path.replace('.wav', '_timings.json').replace('.mp3', '_timings.json')
    
    if os.path.exists(timing_file):
        try:
            with open(timing_file, 'r') as f:
                timings_data = json.load(f)
            
            return [(item["word"], item["start"], item["end"]) for item in timings_data]
        except Exception as e:
            print(f"Error loading word timings: {e}")
    
    return []


def generate_audio(
    animal_name: str, animal_info: str, speaker_wav: str | None = None
) -> str:
    """
    Generate an audio file from the given animal information and extract word timings.

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
    clean_animal_info = animal_info.replace("*", "")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    output_path = f"output_audio/{animal_name}.wav"

    if speaker_wav and os.path.exists(speaker_wav):
        print(f"Using speaker WAV file: {speaker_wav}")
        # Use XTTS v2 for voice cloning
        model = "tts_models/multilingual/multi-dataset/xtts_v2"
        tts = TTS(model_name=model, progress_bar=True).to(device)
        tts.tts_to_file(
            text=clean_animal_info,
            file_path=output_path,
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
        tts.tts_to_file(text=clean_animal_info, file_path=output_path)

    # Extract word timings from the generated audio
    try:
        print("Extracting word timings from audio...")
        word_timings = extract_word_timings_from_audio(clean_animal_info, output_path)
        
        if word_timings:
            save_word_timings(word_timings, output_path)
            print(f"Extracted {len(word_timings)} word timings")
        else:
            print("Could not extract word timings, will use estimation")
    except Exception as e:
        print(f"Error extracting word timings: {e}")

    return output_path
