"""Animal data management module."""

import os
import random
from json import loads
from pathlib import Path
from requests import post
from json import dumps
from config import logger


def get_animal_name(animal_list_path: Path = Path("animal_names.json")) -> str:
    """
    Return a random animal name from a JSON file containing a list of animal names.
    If the file does not exist or is empty, raise an error.

    Returns:
        str: A unique animal name, or an error message if the API fails.
    """
    animal_list_path = animal_list_path.resolve()
    if not animal_list_path.exists():
        raise FileNotFoundError(
            f"Animal names file not found: {animal_list_path}. Please ensure the file exists."
        )

    animal_list = animal_list_path.read_text(encoding="utf-8")
    animal_list: list[str] = loads(animal_list)
    
    if not animal_list:
        raise ValueError(
            "Animal names list is empty. Please check the animal_names.json file."
        )
    
    for prev in read_previous_animal_names():
        try:
            animal_list.remove(prev)
        except ValueError:
            continue

    animal_name = random.choice(animal_list).strip()
    if not animal_name:
        raise ValueError(
            "Generated animal name is empty. Please check the animal_names.json file."
        )
    logger.info(f"Generated animal name: {animal_name}")

    return animal_name


def read_previous_animal_names() -> list:
    """
    Read previously generated animal names from a file.

    Returns:
        list: A list of previously generated animal names.
    """
    try:
        with open("previous_animal_names.txt", "r") as file:
            return [line.strip() for line in file.readlines()]
    except FileNotFoundError:
        return []


def save_animal_name(animal_name: str) -> None:
    """
    Save the given animal name to a file.

    Args:
        animal_name (str): The name of the animal to save.

    Returns:
        None
    """
    with open("previous_animal_names.txt", "a") as file:
        file.write(animal_name + "\n")


def generate_animal_info(animal_name: str) -> str:
    """
    Generate a string containing information about the given animal.
    Uses caching to avoid repeated API calls for the same animal.

    Args:
        animal_name (str): The name of the animal.

    Returns:
        str: A string containing the animal's name and a brief description.
    """
    from cache import cached_animal_info, cache_animal_info
    
    # Check cache first
    cached_info = cached_animal_info(animal_name)
    if cached_info:
        logger.info(f"Using cached info for {animal_name}")
        return cached_info
    
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError(
            "API key not found. Please set the OPENROUTER_API_KEY environment variable."
        )
    
    try:
        response = post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            data=dumps(
                {
                    "model": "google/gemma-3n-e4b-it:free",
                    "messages": [
                        {
                            "role": "user",
                            "content": f"Give me a brief description of the animal named {animal_name}. Use information from wikipedia and other reliable sources. Include its habitat, diet, size, scientific name and any interesting facts. The response should be concise and informative, suitable for a general audience. The response will be read out loud by a text-to-speech system, so it should be clear and easy to understand. Return the information in a single paragraph without any additional text or formatting.",
                        }
                    ],
                }
            ),
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        animal_info = data["choices"][0]["message"]["content"].strip()
        
        # Cache the result
        cache_animal_info(animal_name, animal_info)
        return animal_info
        
    except Exception as e:
        error_msg = f"Error generating animal info: {e}"
        logger.error(error_msg)
        return f"Error: {error_msg}"
