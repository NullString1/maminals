"""WhatsApp integration module for sending videos."""

from requests import post
from config import logger


def send_video(video_path: str, chat_id: str) -> None:
    """
    Send a video file to a specified WhatsApp chat using a local WhatsApp API server.

    Args:
        video_path (str): Path to the video file to send.
        chat_id (str): WhatsApp chat ID to send the video to.

    Returns:
        None
    """
    url = "http://127.0.0.1:3000/client/sendMessage/ABCD"
    try:
        with open(video_path, "rb") as video_file:
            resp = post(
                "https://tmpfiles.org/api/v1/upload", files={"file": video_file}
            )
    except Exception as e:
        logger.error(f"Error reading video file: {e}")
        return

    video_url = resp.json().get("data", {}).get("url", "").split("/")
    video_url.insert(3, "dl")
    video_url = "/".join(video_url)

    if not video_url:
        logger.error(f"Failed to upload video. Response: {resp.text}")
        return
    else:
        logger.info(f"Video uploaded successfully. URL: {video_url}")

    data = {
        "chatId": chat_id,
        "contentType": "MessageMediaFromURL",
        "content": video_url,
    }
    try:
        response = post(url, json=data)
        if response.status_code == 200:
            logger.info(f"Video sent successfully to chat {chat_id}")
        else:
            logger.error(
                f"Failed to send video. Status code: {response.status_code}, Response: {response.text}"
            )
    except Exception as e:
        logger.error(f"Error sending video: {e}")
