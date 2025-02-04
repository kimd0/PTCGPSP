import logging
import cv2
import numpy as np
import asyncio
from PIL import Image
from typing import Optional, Tuple
from utils.adb_interaction import ADBInteraction

logging.basicConfig(level=logging.INFO)

def image_to_array(image: Image) -> np.ndarray:
    """
    Convert a PIL Image to a NumPy array (grayscale).

    :param image: PIL Image object
    :return: NumPy array of the image
    """
    return np.array(image.convert("L"))  # Convert to grayscale

async def template_match(adb_interaction: ADBInteraction, device_id: str, template_path: str, threshold: float = 0.9) -> Optional[Tuple[int, int]]:
    """
    Capture a screenshot and perform template matching.

    :param adb_interaction: Instance of ADBInteraction to take screenshots.
    :param device_id: The ADB device ID.
    :param template_path: Path to the template image file.
    :param threshold: Matching confidence threshold (0 to 1).
    :return: (center_x, center_y) of the matched image, or None if not found.
    """
    # Capture a fresh screenshot (returns a PIL Image)
    screenshot = await adb_interaction.take_screenshot(device_id, return_bitmap=True)

    # Load the template image
    template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)

    if screenshot is None:
        logging.error("Error: Screenshot not available.")
        return None

    if template is None:
        logging.error("Error: Template not available.")
        return None

    screenshot_array = image_to_array(screenshot)
    template_h, template_w = template.shape[:2]  # Get template size

    # Perform template matching
    result = cv2.matchTemplate(screenshot_array, template, cv2.TM_CCOEFF_NORMED)
    loc = np.where(result >= threshold)

    matches = list(zip(*loc[::-1]))  # Convert to (x, y) positions

    if not matches:
        return None

    # Select the first match and compute the center point
    x, y = matches[0]
    center_x = x + (template_w // 2)
    center_y = y + (template_h // 2)

    return center_x, center_y

async def search_until_found(adb_interaction: ADBInteraction, device_id: str, template_path: str, max_attempts: int = 100, delay: float = 0.1) -> Optional[Tuple[int, int]]:
    """
    Repeatedly take screenshots and search for an image until it's found or max attempts reached.

    :param adb_interaction: Instance of ADBInteraction to take screenshots.
    :param device_id: The ADB device ID.
    :param template_path: Path to the template image file.
    :param max_attempts: Maximum number of attempts before giving up.
    :param delay: Delay (in seconds) between attempts.
    :return: (x, y) coordinates if found, otherwise None.
    """
    for attempt in range(max_attempts):
        logging.info(f"Attempt to find {template_path} ({attempt + 1}/{max_attempts})")

        match = await template_match(adb_interaction, device_id, template_path)

        if match is not None:
            x, y = match
            logging.info(f"Image found at ({x}, {y}) on attempt {attempt + 1}.")
            return x, y

        await asyncio.sleep(delay)  # Wait before next attempt

    logging.info("Image not found after max attempts.")
    return None

async def pixel_search(adb_interaction: ADBInteraction, device_id: str, target_color: Tuple[int, int, int], tolerance: int = 10) -> Optional[Tuple[int, int]]:
    """
    Capture a screenshot and search for a specific pixel color.

    :param adb_interaction: Instance of ADBInteraction to take screenshots.
    :param device_id: The ADB device ID.
    :param target_color: The RGB color to search for.
    :param tolerance: Allowed variation for color matching.
    :return: (x, y) coordinates if found, otherwise None.
    """
    screenshot = await adb_interaction.take_screenshot(device_id, return_bitmap=True)
    screenshot = screenshot.convert("RGB")

    if screenshot is None:
        logging.error("Error: Screenshot not available.")
        return None

    screenshot_array = np.array(screenshot)  # Convert PIL image to NumPy array (RGB)

    # Find all pixels that match the target color within the tolerance range
    match_mask = np.all(
        np.abs(screenshot_array - np.array(target_color)) <= tolerance,
        axis=-1
    )

    # Get indices of matching pixels
    matches = np.column_stack(np.where(match_mask))

    if matches.size == 0:
        return None

    # Return the first matching pixel position
    return tuple(matches[0][::-1])  # Convert (row, col) to (x, y)

async def search_until_found_pixel(adb_interaction: ADBInteraction, device_id: str, target_color: Tuple[int, int, int], tolerance: int = 10, max_attempts: int = 100, delay: float = 0.1) -> Optional[Tuple[int, int]]:
    """
    Repeatedly take screenshots and search for a specific pixel color until it's found or max attempts reached.

    :param adb_interaction: Instance of ADBInteraction to take screenshots.
    :param device_id: The ADB device ID.
    :param target_color: The RGB color to search for.
    :param tolerance: Allowed variation for color matching.
    :param max_attempts: Maximum number of attempts before giving up.
    :param delay: Delay (in seconds) between attempts.
    :return: (x, y) coordinates if found, otherwise None.
    """
    for attempt in range(max_attempts):
        logging.info(f"Attempt {attempt + 1}/{max_attempts}...")

        match = await pixel_search(adb_interaction, device_id, target_color, tolerance)

        if match is not None:
            x, y = match
            logging.info(f"Pixel found at ({x}, {y}) on attempt {attempt + 1}.")
            return x, y

        await asyncio.sleep(delay)  # Wait before next attempt

    logging.info("Pixel not found after max attempts.")
    return None
