"""Video creation module using MoviePy with subtitles."""

import os
import re
import time
from pathlib import Path
from typing import List, Tuple, Dict
from moviepy import Clip
from moviepy.video.VideoClip import ImageClip, TextClip, ColorClip, VideoClip
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from config import OUTPUT_VIDEO_DIR, FFMPEG_FPS, FFMPEG_RESOLUTION, logger


def estimate_word_timings(text: str, audio_duration: float) -> List[Tuple[str, float, float]]:
    """
    Estimate word timings based on audio duration.
    Returns a list of (word, start_time, end_time) tuples.
    
    Args:
        text (str): The text to create timings for
        audio_duration (float): Total duration of the audio in seconds
        
    Returns:
        List[Tuple[str, float, float]]: List of (word, start_time, end_time)
    """
    # Clean and split text into words
    words = re.findall(r'\b\w+\b', text.lower())
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


def create_subtitle_clips(word_timings: List[Tuple[str, float, float]], 
                         video_width: int, video_height: int) -> List[TextClip]:
    """
    Create subtitle text clips with word-level highlighting.
    
    Args:
        word_timings: List of (word, start_time, end_time) tuples
        video_width: Width of the video
        video_height: Height of the video
        
    Returns:
        List[TextClip]: List of subtitle clips
    """
    subtitle_clips = []
    
    # Group words into sentences or phrases for better display
    current_text = []
    current_start = 0
    
    for i, (word, start_time, end_time) in enumerate(word_timings):
        if not current_text:
            current_start = start_time
            
        current_text.append(word)
        
        # End phrase on punctuation or every 8-10 words
        should_end_phrase = (
            word.endswith(('.', '!', '?')) or 
            len(current_text) >= 8 or 
            i == len(word_timings) - 1
        )
        
        if should_end_phrase:
            phrase = ' '.join(current_text)
            phrase_duration = end_time - current_start
            
            # Create text clip for the phrase
            txt_clip = TextClip(
                text=phrase,
                font_size=32,
                color='black',
                size=(video_width // 2 - 40, None),  # Right half of screen minus padding
                method='caption',
                duration=phrase_duration
            ).with_start(current_start)
            
            # Position on the right side of the screen
            txt_clip = txt_clip.with_position((video_width // 2 + 20, 'center'))
            
            subtitle_clips.append(txt_clip)
            current_text = []
    
    return subtitle_clips


def create_video_from_audio_and_images(
    audio_path: str,
    image_paths: list[str],
    animal_name: str,
    output_path: str = "output_video/{animal_name}.mp4",
    duration: int = None,
    keep_images: bool = False,
    vf_filter: str = None,
    text: str = None,
) -> str:
    """
    Create a video slideshow with images on the left and subtitles on the right using MoviePy.
    
    Args:
        audio_path (str): Path to the audio file.
        image_paths (list[str]): List of image file paths.
        animal_name (str): Name of the animal (used in output filename).
        output_path (str, optional): Output video path template. Defaults to "output_video/{animal_name}.mp4".
        duration (int, optional): Duration of the video in seconds. Defaults to None.
        keep_images (bool, optional): Whether to keep images after video creation. Defaults to False.
        vf_filter (str, optional): Custom video filter (ignored, kept for compatibility).
        text (str, optional): Text for subtitles. If None, will attempt to extract from animal data.
        
    Returns:
        str: Path to the generated video file.
    """
    try:
        OUTPUT_VIDEO_DIR.mkdir(parents=True, exist_ok=True)
        if not image_paths:
            raise ValueError("No image paths provided.")

        # Load audio file
        audio = AudioFileClip(audio_path)
        if duration is None:
            duration = audio.duration
        
        # Get text for subtitles - try to get from animal data if not provided
        if text is None:
            try:
                from animal_data import generate_animal_info
                text = generate_animal_info(animal_name)
                if text.startswith("Error:"):
                    text = f"This is a {animal_name}. A fascinating animal with many interesting characteristics."
            except Exception as e:
                logger.warning(f"Could not get animal info for subtitles: {e}")
                text = f"This is a {animal_name}. A fascinating animal with many interesting characteristics."
        
        # Set up video dimensions
        video_width, video_height = FFMPEG_RESOLUTION
        
        # Create white background
        background = ColorClip(size=(video_width, video_height), color=(255, 255, 255), duration=duration)
        
        # Create image slideshow for the left half of the screen
        image_clips = []
        image_duration = duration / len(image_paths) if len(image_paths) > 1 else duration
        
        for i, image_path in enumerate(image_paths):
            try:
                # Load and resize image to fit left half of screen
                img_clip = ImageClip(image_path, duration=image_duration)
                
                # Resize image to fit in left half while maintaining aspect ratio
                img_clip = img_clip.resized(height=video_height * 0.8)
                if img_clip.w > video_width // 2:
                    img_clip = img_clip.resized(width=video_width // 2 - 20)
                
                # Position image on the left side, centered
                img_clip = img_clip.with_position(((video_width // 2 - img_clip.w) // 2, 'center'))
                img_clip = img_clip.with_start(i * image_duration)
                
                image_clips.append(img_clip)
                
            except Exception as e:
                logger.warning(f"Error processing image {image_path}: {e}")
                continue
        
        # If no images were successfully processed, create a placeholder
        if not image_clips:
            placeholder = TextClip(
                text=animal_name,
                font_size=48,
                color='black',
                size=(video_width // 2 - 40, None),
                duration=duration
            ).with_position((20, 'center'))
            image_clips = [placeholder]
        
        # Generate word timings for subtitles - try to load from file first
        audio_timing_file = audio_path.replace('.wav', '_timings.json').replace('.mp3', '_timings.json')
        word_timings = []
        
        if os.path.exists(audio_timing_file):
            try:
                import json
                with open(audio_timing_file, 'r') as f:
                    timings_data = json.load(f)
                word_timings = [(item["word"], item["start"], item["end"]) for item in timings_data]
                logger.info(f"Loaded {len(word_timings)} word timings from file")
            except Exception as e:
                logger.warning(f"Error loading word timings from file: {e}")
        
        # Fall back to estimation if no timings file found
        if not word_timings:
            logger.info("No timing file found, using estimation")
            word_timings = estimate_word_timings(text, duration)
        
        # Create subtitle clips
        subtitle_clips = create_subtitle_clips(word_timings, video_width, video_height)
        
        # Combine all clips
        all_clips = [background] + image_clips + subtitle_clips
        
        # Create final composite video
        final_video: VideoClip = CompositeVideoClip(all_clips, size=(video_width, video_height))
        final_video = final_video.with_audio(audio)
        final_video = final_video.with_duration(duration)

        # Set output path
        output_path = Path(str(output_path).format(animal_name=animal_name))
        
        # Export video
        logger.info(f"Creating video: {output_path}")
        final_video.write_videofile(
            str(output_path),
            fps=FFMPEG_FPS,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile='temp-audio.m4a',
            remove_temp=True,
            logger="bar",
            threads=os.cpu_count() or 1,
        )
        
        # Clean up clips to free memory
        final_video.close()
        audio.close()
        for clip in image_clips:
            clip.close()
        for clip in subtitle_clips:
            clip.close()
        
        # Optionally clean up images
        if not keep_images:
            for img in image_paths:
                try:
                    Path(img).unlink(missing_ok=True)
                    logger.info(f"Removed image: {img}")
                except Exception as e:
                    logger.warning(f"Error removing image {img}: {e}")
        
        logger.info(f"Video created successfully: {output_path}")
        return str(output_path)
        
    except Exception as e:
        logger.error(f"Error creating video: {e}")
        return ""
