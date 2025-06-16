"""Caching module for improving performance by avoiding redundant operations."""

import json
import hashlib
from pathlib import Path
from typing import Any, Optional
from config import logger


class SimpleCache:
    """A simple file-based cache for storing temporary data."""

    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

    def _get_cache_path(self, key: str) -> Path:
        """Generate cache file path for a given key."""
        # Create a hash of the key to avoid filesystem issues
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.json"

    def get(self, key: str) -> Optional[Any]:
        """Retrieve a value from cache."""
        cache_path = self._get_cache_path(key)
        try:
            if cache_path.exists():
                with open(cache_path, "r") as f:
                    data = json.load(f)
                    logger.debug(f"Cache hit for key: {key}")
                    return data.get("value")
        except Exception as e:
            logger.debug(f"Cache read error for key {key}: {e}")
        return None

    def set(self, key: str, value: Any) -> None:
        """Store a value in cache."""
        cache_path = self._get_cache_path(key)
        try:
            with open(cache_path, "w") as f:
                json.dump({"value": value}, f)
                logger.debug(f"Cache set for key: {key}")
        except Exception as e:
            logger.debug(f"Cache write error for key {key}: {e}")

    def clear(self) -> None:
        """Clear all cache files."""
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
            logger.info("Cache cleared")
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")


# Global cache instance
cache = SimpleCache()


def cached_animal_info(animal_name: str) -> Optional[str]:
    """Get cached animal information if available."""
    return cache.get(f"animal_info_{animal_name}")


def cache_animal_info(animal_name: str, info: str) -> None:
    """Cache animal information for future use."""
    cache.set(f"animal_info_{animal_name}", info)


def cached_image_urls(animal_name: str, source: str) -> Optional[list]:
    """Get cached image URLs if available."""
    return cache.get(f"image_urls_{source}_{animal_name}")


def cache_image_urls(animal_name: str, source: str, urls: list) -> None:
    """Cache image URLs for future use."""
    cache.set(f"image_urls_{source}_{animal_name}", urls)
