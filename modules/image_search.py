import logging
import os
import cv2
import numpy as np
import asyncio
from PIL import Image
from typing import Dict, Optional, Tuple
from utils.adb_interaction import ADBInteraction

logging.basicConfig(level=logging.INFO)

import asyncio
import cv2
import logging
import os
import numpy as np
from typing import Dict, Optional

class TemplateCache:
    """싱글톤 패턴으로 템플릿 이미지를 캐싱하는 클래스"""
    _instance = None
    _cache: Dict[str, np.ndarray] = {}
    _image_dir = os.path.abspath("./data/images")  # 절대 경로 변환

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TemplateCache, cls).__new__(cls)
        return cls._instance

    async def load_template(self, template_path: str) -> Optional[np.ndarray]:
        """단일 템플릿을 로드 및 캐싱 (경로 정규화 적용)"""
        template_path = os.path.abspath(template_path)  # 절대 경로로 변환

        if template_path in self._cache:
            return self._cache[template_path]

        loop = asyncio.get_running_loop()
        template = await loop.run_in_executor(None, cv2.imread, template_path, cv2.IMREAD_GRAYSCALE)

        if template is None:
            logging.error(f"Error: Template {template_path} not found.")
            return None

        self._cache[template_path] = template
        return template

    async def load_all_templates(self):
        """모든 템플릿을 미리 캐싱 (경로 정규화 적용)"""
        if not os.path.exists(self._image_dir):
            logging.error(f"Error: Template directory {self._image_dir} not found.")
            return

        tasks = []
        for filename in os.listdir(self._image_dir):
            if filename.lower().endswith(".png"):
                template_path = os.path.abspath(os.path.join(self._image_dir, filename))  # 절대 경로 변환
                tasks.append(self.load_template(template_path))

        await asyncio.gather(*tasks)
        logging.info(f"Loaded {len(self._cache)} templates into cache.")

    def get_template(self, template_path: str) -> Optional[np.ndarray]:
        """캐싱된 템플릿 반환 (경로 정규화 적용)"""
        template_path = os.path.abspath(template_path)  # 절대 경로 변환
        return self._cache.get(template_path, None)


def image_to_array(image: Image) -> np.ndarray:
    """
    Convert a PIL Image to a NumPy array (grayscale).

    :param image: PIL Image object
    :return: NumPy array of the image
    """
    return np.array(image.convert("L"))  # Convert to grayscale

async def template_match(adb_interaction: ADBInteraction, device_id: str, template_path: str, threshold: float = 0.80) -> Optional[Tuple[int, int]]:
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

    if screenshot is None:
        logging.error("Error: Screenshot not available.")
        return None

    template_cache = TemplateCache()
    template = template_cache.get_template(os.path.abspath(template_path))

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


async def count_template_matches(adb_interaction: ADBInteraction, device_id: str, template_path: str,
                                 threshold: float = 0.95, y_limit: int = None) -> int:
    """
    Capture a screenshot and count the number of matches for the template image,
    searching only up to the specified y-axis pixel (if provided).

    :param adb_interaction: Instance of ADBInteraction to take screenshots.
    :param device_id: The ADB device ID.
    :param template_path: Path to the template image file.
    :param threshold: Matching confidence threshold (0 to 1).
    :param y_limit: The y-axis pixel limit (height) up to which to search the screenshot.
                    If None, the entire screenshot is used.
    :return: The number of times the template was found in the (cropped) screenshot.
    """
    # Capture a fresh screenshot (returns a PIL Image)
    screenshot = await adb_interaction.take_screenshot(device_id, return_bitmap=True)
    if screenshot is None:
        logging.error("Error: Screenshot not available.")
        return 0

    template_cache = TemplateCache()
    template = template_cache.get_template(os.path.abspath(template_path))
    if template is None:
        logging.error("Error: Template not available.")
        return 0

    screenshot_array = image_to_array(screenshot)

    if y_limit is not None:
        screenshot_height = screenshot_array.shape[0]
        if y_limit < screenshot_height:
            screenshot_array = screenshot_array[:y_limit, :]

    result = cv2.matchTemplate(screenshot_array, template, cv2.TM_CCOEFF_NORMED)
    loc = np.where(result >= threshold)
    matches = list(zip(*loc[::-1]))  # 좌표 배열을 (x, y) 튜플의 리스트로 변환

    return len(matches)

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
