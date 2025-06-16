"""Image handling module for downloading and managing animal images."""

import os
import re
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests import get
from config import OUTPUT_IMAGE_DIR, logger


def download_images(
    image_urls: list[str], animal_name: str, output_dir: str = "output_images"
) -> list[str]:
    """
    Download all images from the given URLs and save them to the output_images/ directory with the animal name as the filename.

    Args:
        image_urls (list[str]): List of image URLs to download.
        animal_name (str): Name of the animal (used in filenames).
        output_dir (str, optional): Directory to save images. Defaults to "output_images".

    Returns:
        list[str]: List of paths to the saved images.
    """
    from tqdm import tqdm  # Import only when needed

    OUTPUT_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    def sanitize_filename(filename: str) -> str:
        # Remove or replace problematic characters for all filesystems
        return re.sub(r"[^\w\-.]", "_", filename)

    def download_one(image_url: str) -> Optional[str]:
        try:
            # Only allow image URLs with valid image extensions
            if image_url.startswith("https://images.unsplash.com/photo-"):
                filename = (
                    f"{animal_name}.{image_url.split('photo-')[1].split('?')[0]}.jpeg"
                )
            else:
                valid_exts = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")
                url_lower = image_url.lower()
                if not any(url_lower.endswith(ext) for ext in valid_exts):
                    logger.info(f"Skipping non-image URL: {image_url}")
                    return None
                filename = image_url.split("/")[-1]
            filename = sanitize_filename(filename)
            output_path = OUTPUT_IMAGE_DIR / filename
            try:
                response = get(
                    image_url,
                    stream=True,
                    headers={
                        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
                    },
                )
            except Exception as e:
                logger.warning(f"Error requesting {image_url}: {e}")
                return None
            if response.status_code == 200:
                try:
                    with open(output_path, "wb") as f:
                        for chunk in response.iter_content(1024):
                            f.write(chunk)
                    return str(output_path)
                except Exception as e:
                    logger.warning(f"Error saving image {output_path}: {e}")
                    return None
            else:
                logger.warning(
                    f"Failed to download {image_url}: Status code {response.status_code}"
                )
                return None
        except Exception as e:
            logger.warning(f"Error processing image URL {image_url}: {e}")
            return None

    output_paths = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(download_one, url) for url in image_urls]
        for future in tqdm(
            as_completed(futures), total=len(futures), desc="Downloading images"
        ):
            result = future.result()
            if result:
                output_paths.append(result)
    return output_paths


def get_animal_photo_urls_unsplash(animal_name: str) -> list[str] | str:
    """
    Retrieve the URLs of the first 25 images of the animal from Unsplash.

    Args:
        animal_name (str): Name of the animal to search for.

    Returns:
        list[str] | str: List of image URLs or error message.
    """
    access_key = os.getenv("UNSPLASH_ACCESS_KEY")
    if not access_key:
        raise ValueError(
            "Unsplash API access key not found. Please set the UNSPLASH_ACCESS_KEY environment variable."
        )
    url = "https://api.unsplash.com/search/photos"
    params = {"query": animal_name, "per_page": 25, "client_id": access_key}
    response = get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        results = data.get("results", [])
        if results:
            return [
                result["urls"]["regular"]
                for result in results
                if "urls" in result and "regular" in result["urls"]
            ]
        else:
            return "No images found."
    else:
        return f"Error: {response.status_code} - {response.text}"


def get_animal_photo_urls_wikimedia(animal_name: str) -> list[str] | str:
    """
    Retrieve URLs of animal images from Wikimedia Commons

    Args:
        animal_name (str): Name of the animal to search for.

    Returns:
        list[str] | str: List of image URLs or error message.
    """
    url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "generator": "images",
        "titles": animal_name,
        "prop": "imageinfo",
        "redirects": 1,
        "gimlimit": "200",
        "iiprop": "url",
    }
    try:
        response = get(url, params=params, timeout=10)
        print(response.text)
        if response.status_code == 200:
            data = response.json()
            pages = data.get("query", {}).get("pages", {})
            image_urls = []
            for page in pages.values():
                imageinfo = page.get("imageinfo", [])
                if imageinfo:
                    image_urls.append(
                        imageinfo[0].get("thumburl") or imageinfo[0].get("url")
                    )
            if image_urls:
                return image_urls
            else:
                return "No images found."
        else:
            return f"Error: {response.status_code} - {response.text}"
    except Exception as e:
        return f"Error: {e}"
