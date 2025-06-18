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
from audio_generator import estimate_word_timings_simple


def create_subtitle_clips(word_timings: List[Tuple[str, float, float]], 
                         video_width: int, video_height: int) -> List[TextClip]:
    """
    Create subtitle text clips displaying complete sentences with multiple lines.
    
    Args:
        word_timings: List of (word, start_time, end_time) tuples
        video_width: Width of the video
        video_height: Height of the video
        
    Returns:
        List[TextClip]: List of subtitle clips
    """
    subtitle_clips = []
    
    # Group words into complete sentences
    current_sentence = []
    current_start = 0
    
    for i, (word, start_time, end_time) in enumerate(word_timings):
        if not current_sentence:
            current_start = start_time
            
        current_sentence.append(word)
        
        # End sentence on sentence-ending punctuation
        is_sentence_end = word.endswith(('.', '!', '?'))
        is_last_word = i == len(word_timings) - 1
        
        # Also break on very long sentences (more than 25 words) or commas after long phrases
        is_long_sentence = len(current_sentence) >= 25
        is_comma_break = word.endswith(',') and len(current_sentence) >= 15
        
        if is_sentence_end or is_last_word or is_long_sentence or is_comma_break:
            sentence_text = ' '.join(current_sentence)
            sentence_duration = end_time - current_start
            
            # Create multi-line text clip for the complete sentence
            txt_clip = TextClip(
                text=sentence_text,
                font_size=22,
                color='black',
                size=(video_width - 100, 22*10),  # Allow height to auto-adjust for multiple lines
                method='caption',
                duration=sentence_duration
            ).with_start(current_start)
            
            # Position in the bottom third of the screen with more space for multiple lines
            txt_clip = txt_clip.with_position(('center', video_height * 0.70))
            
            subtitle_clips.append(txt_clip)
            current_sentence = []
    
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
        
        # Create image slideshow centered on screen with minimum duration
        image_clips = []
        min_image_duration = 1.5
        
        max_images = int(duration // min_image_duration)
        if max_images < 1:
            max_images = 1
        image_paths = image_paths[:max_images]
        image_duration = duration / len(image_paths)
        total_min_duration = min_image_duration * len(image_paths)
        overlap_factor = 1.0  # No overlap needed since we fit exactly
        
        for i, image_path in enumerate(image_paths):
            try:
                # Load and resize image to fit in upper portion of screen
                img_clip = ImageClip(image_path, duration=image_duration)
                
                # Resize image to fit in upper 2/3 of screen while maintaining aspect ratio
                max_height = video_height * 0.8  # Use 80% of screen height for images
                max_width = video_width * 0.95   # Use 95% of screen width for images

                # Resize maintaining aspect ratio
                if img_clip.h > max_height:
                    img_clip = img_clip.resized(height=max_height)
                if img_clip.w > max_width:
                    img_clip = img_clip.resized(width=max_width)
                
                # Center the image horizontally and position in upper portion
                img_clip = img_clip.with_position(('center', video_height * 0.15))
                
                # Handle overlapping if needed
                if total_min_duration > duration:
                    start_time = i * (duration * overlap_factor / len(image_paths))
                else:
                    start_time = i * image_duration
                    
                img_clip = img_clip.with_start(start_time)
                
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
                size=(video_width - 40, None),
                duration=duration
            ).with_position(('center', video_height * 0.3))
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
            word_timings = estimate_word_timings_simple(text, duration)
        
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
