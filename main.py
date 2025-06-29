"""Main orchestration module for the maminals project."""

import os
import sys
import argparse

# Import only lightweight config at startup
from config import FFMPEG_RESOLUTION, get_ffmpeg_filter, logger


def main():
    """Main application entry point."""
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
    custom_filter = None
    if args.output_resolution:
        try:
            width, height = map(int, args.output_resolution.lower().split("x"))
            aspect = width / height
            custom_filter = get_ffmpeg_filter((width, height), aspect)
        except Exception as e:
            logger.warning(
                f"Invalid --output-resolution: {args.output_resolution}, using default. Error: {e}"
            )

    try:
        # Lazy imports for better startup performance
        from animal_data import get_animal_name, generate_animal_info, save_animal_name
        from image_handler import (
            download_images,
            get_animal_photo_urls_unsplash,
            get_animal_photo_urls_wikimedia,
        )
        from audio_generator import generate_audio
        from video_creator import create_video_from_audio_and_images
        from whatsapp_sender import send_video
        from utils import check_file_duration, cleanup_file

        # Get or generate animal name
        if args.animal_name:
            animal_name = args.animal_name.strip()
        else:
            animal_name = get_animal_name().strip()

        if animal_name.startswith("Error:"):
            logger.error(f"Failed to generate animal name: {animal_name}")
            sys.exit(1)
        logger.info(f"Animal Name: {animal_name}")

        # Generate animal information
        animal_info = generate_animal_info(animal_name)
        if animal_info.startswith("Error:"):
            logger.error(f"Failed to generate animal info: {animal_info}")
            sys.exit(1)
        logger.info(f"Animal Info: {animal_info}")

        # Get image URLs
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

        # Start image downloading and audio generation simultaneously
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from performance import PerformanceMonitor

        with PerformanceMonitor("Parallel image download and audio generation"):
            with ThreadPoolExecutor(max_workers=2) as executor:
                # Submit both tasks concurrently
                image_future = executor.submit(download_images, image_urls, animal_name)
                audio_future = executor.submit(
                    generate_audio, animal_name, animal_info, args.speaker_wav
                )

                # Wait for both to complete and get results
                image_paths = None
                audio_file_path = None

                for future in as_completed([image_future, audio_future]):
                    try:
                        if future == image_future:
                            image_paths = future.result()
                            if image_paths is None or len(image_paths) == 0:
                                logger.error("No images were downloaded. Exiting.")
                                audio_future.cancel()
                                sys.exit(1)
                            logger.info(
                                f"Image download completed. Downloaded {len(image_paths)} images."
                            )
                        elif future == audio_future:
                            audio_file_path = future.result()
                            if audio_file_path is None:
                                logger.error("Audio generation failed. Exiting.")
                                image_future.cancel()
                                sys.exit(1)
                            logger.info(
                                f"Audio generation completed: {audio_file_path}"
                            )
                    except Exception as e:
                        logger.error(f"Error in parallel execution: {e}")
                        sys.exit(1)

        logger.debug(f"Images downloaded at: {image_paths}")
        logger.debug(f"Audio file generated at: {audio_file_path}")

        # Check audio duration requirement (minimum 30 seconds)
        if not check_file_duration(audio_file_path, 30.0):
            logger.error(
                f"Generated audio file {audio_file_path} is shorter than 30 seconds. Exiting."
            )
            sys.exit(1)

        logger.info("Starting video creation...")

        # Create video
        video_file_path = create_video_from_audio_and_images(
            audio_file_path,
            image_paths,
            animal_name,
            keep_images=args.keep_images,
            vf_filter=custom_filter,
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

        # Send video via WhatsApp
        chat_id = os.environ.get("WHATSAPP_CHAT_ID")
        if not chat_id:
            logger.warning(
                "WhatsApp chat ID not set. Please set the WHATSAPP_CHAT_ID environment variable."
            )
        else:
            success = send_video(video_file_path, chat_id)
            if not success:
                logger.warning("Failed to send video via WhatsApp, but continuing...")

        # Clean up audio file
        cleanup_file(audio_file_path)

        # Save animal name to prevent duplicates
        save_animal_name(animal_name)

    except Exception as e:
        logger.error(f"Unexpected error in main: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
