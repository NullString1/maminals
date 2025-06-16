"""WhatsApp integration module for sending videos."""

import time
from pathlib import Path
from requests import post
from config import logger


def send_video(video_path: str, chat_id: str, max_retries: int = 3) -> bool:
    """
    Send a video file to a specified WhatsApp chat using a local WhatsApp API server.

    Args:
        video_path (str): Path to the video file to send.
        chat_id (str): WhatsApp chat ID to send the video to.
        max_retries (int): Maximum number of retry attempts. Defaults to 3.

    Returns:
        bool: True if video was sent successfully, False otherwise.
    """
    if not Path(video_path).exists():
        logger.error(f"Video file not found: {video_path}")
        return False

    url = "http://127.0.0.1:3000/client/sendMessage/ABCD"

    for attempt in range(max_retries):
        try:
            # Upload video to temporary file service
            with open(video_path, "rb") as video_file:
                upload_resp = post(
                    "https://tmpfiles.org/api/v1/upload",
                    files={"file": video_file},
                    timeout=60,  # 60 second timeout for upload
                )
                upload_resp.raise_for_status()
        except Exception as e:
            logger.error(f"Error uploading video file (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2**attempt)  # Exponential backoff
                continue
            return False
        # Parse upload response and create download URL
        try:
            video_url_parts = (
                upload_resp.json().get("data", {}).get("url", "").split("/")
            )
            if not video_url_parts or len(video_url_parts) < 4:
                logger.error(f"Invalid upload response: {upload_resp.text}")
                if attempt < max_retries - 1:
                    time.sleep(2**attempt)
                    continue
                return False

            video_url_parts.insert(3, "dl")
            video_url = "/".join(video_url_parts)
            logger.info(f"Video uploaded successfully. URL: {video_url}")
        except Exception as e:
            logger.error(f"Error parsing upload response: {e}")
            if attempt < max_retries - 1:
                time.sleep(2**attempt)
                continue
            return False

        # Send video via WhatsApp
        data = {
            "chatId": chat_id,
            "contentType": "MessageMediaFromURL",
            "content": video_url,
        }

        try:
            response = post(url, json=data, timeout=30)
            response.raise_for_status()
            logger.info(f"Video sent successfully to chat {chat_id}")
            return True
        except Exception as e:
            logger.error(f"Error sending video (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2**attempt)
                continue

    logger.error(f"Failed to send video after {max_retries} attempts")
    return False
