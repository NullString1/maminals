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
                    logger.debug(f"Skipping non-image URL: {image_url}")
                    return None
                filename = image_url.split("/")[-1]
            
            filename = sanitize_filename(filename)
            output_path = OUTPUT_IMAGE_DIR / filename
            
            # Skip if file already exists
            if output_path.exists():
                logger.debug(f"Image already exists: {output_path}")
                return str(output_path)
            
            try:
                response = get(
                    image_url,
                    stream=True,
                    timeout=(5, 30),  # 5s connect, 30s read timeout
                    headers={
                        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
                    },
                )
                response.raise_for_status()  # Raise exception for bad status codes
            except Exception as e:
                logger.warning(f"Error requesting {image_url}: {e}")
                return None
            
            try:
                with open(output_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):  # Larger chunks
                        if chunk:
                            f.write(chunk)
                return str(output_path)
            except Exception as e:
                logger.warning(f"Error saving image {output_path}: {e}")
                # Clean up partial file
                output_path.unlink(missing_ok=True)
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
    Uses caching to avoid repeated API calls.

    Args:
        animal_name (str): Name of the animal to search for.

    Returns:
        list[str] | str: List of image URLs or error message.
    """
    from cache import cached_image_urls, cache_image_urls
    
    # Check cache first
    cached_urls = cached_image_urls(animal_name, "unsplash")
    if cached_urls:
        logger.info(f"Using cached Unsplash URLs for {animal_name}")
        return cached_urls
    
    access_key = os.getenv("UNSPLASH_ACCESS_KEY")
    if not access_key:
        raise ValueError(
            "Unsplash API access key not found. Please set the UNSPLASH_ACCESS_KEY environment variable."
        )
    
    url = "https://api.unsplash.com/search/photos"
    params = {"query": animal_name, "per_page": 25, "client_id": access_key}
    
    try:
        response = get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])
        
        if results:
            image_urls = [
                result["urls"]["regular"]
                for result in results
                if "urls" in result and "regular" in result["urls"]
            ]
            # Cache the result
            cache_image_urls(animal_name, "unsplash", image_urls)
            return image_urls
        else:
            return "No images found."
    except Exception as e:
        error_msg = f"Error: {e}"
        logger.error(f"Unsplash API error for {animal_name}: {e}")
        return error_msg


def get_animal_photo_urls_wikimedia(animal_name: str) -> list[str] | str:
    """
    Retrieve URLs of animal images from Wikimedia Commons.
    Uses caching to avoid repeated API calls.

    Args:
        animal_name (str): Name of the animal to search for.

    Returns:
        list[str] | str: List of image URLs or error message.
    """
    from cache import cached_image_urls, cache_image_urls
    
    # Check cache first
    cached_urls = cached_image_urls(animal_name, "wikimedia")
    if cached_urls:
        logger.info(f"Using cached Wikimedia URLs for {animal_name}")
        return cached_urls
    
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
        response.raise_for_status()
        data = response.json()
        pages = data.get("query", {}).get("pages", {})
        image_urls = []
        
        for page in pages.values():
            imageinfo = page.get("imageinfo", [])
            if imageinfo:
                image_url = imageinfo[0].get("thumburl") or imageinfo[0].get("url")
                if image_url:
                    image_urls.append(image_url)
        
        if image_urls:
            # Cache the result
            cache_image_urls(animal_name, "wikimedia", image_urls)
            return image_urls
        else:
            return "No images found."
    except Exception as e:
        error_msg = f"Error: {e}"
        logger.error(f"Wikimedia API error for {animal_name}: {e}")
        return error_msg
