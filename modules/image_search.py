import cv2
import numpy as np
import time
from PIL import Image

def image_to_array(image):
    """
    Convert a PIL Image to a NumPy array (grayscale).

    :param image: PIL Image object
    :return: NumPy array of the image
    """
    return np.array(image.convert("L"))  # Convert to grayscale

def template_match(adb_interaction, device_id, template_path, threshold=0.8):
    """
    Capture a screenshot and perform template matching.

    :param adb_interaction: Instance of ADBInteraction to take screenshots.
    :param device_id: The ADB device ID.
    :param template_path: Path to the template image file.
    :param threshold: Matching confidence threshold (0 to 1).
    :return: (center_x, center_y) of the matched image, or None if not found.
    """
    # Capture a fresh screenshot (returns a PIL Image)
    screenshot = adb_interaction.take_screenshot(device_id, return_bitmap=True)

    # Load the template image
    template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)

    if screenshot is None or template is None:
        print("Error: Screenshot or template not available.")
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

def search_until_found(adb_interaction, device_id, template_path, max_attempts=20, delay=0.1):
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
        print(f"Attempt {attempt + 1}/{max_attempts}...")

        match = template_match(adb_interaction, device_id, template_path)

        if match is not None:  # ✅ `None`이 아닐 때만 처리
            x, y = match
            print(f"✅ Image found at ({x}, {y}) on attempt {attempt + 1}.")
            return x, y

        time.sleep(delay)  # Wait before next attempt

    print("Image not found after max attempts.")
    return None
