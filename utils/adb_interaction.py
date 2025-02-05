import logging
import os
import hashlib
import asyncio
import time
from PIL import Image
from utils.adb_client import ADBClient

logging.basicConfig(level=logging.INFO)

class ADBInteraction:
    """Class to interact with ADB devices for simulated input, screenshots, and app management."""

    def __init__(self, adb_client: ADBClient):
        """Initialize with an instance of ADBClient."""
        self.adb_client = adb_client
        self.screenshot_dir = os.path.join(os.getcwd(), "temp")
        os.makedirs(self.screenshot_dir, exist_ok=True)

    def _run_command(self, command: str):
        """Run an ADB command and handle errors."""
        output, error = self.adb_client.run_command(command)
        if error:
            logging.error(f"Error running command '{command}': {error}")
            return None
        return output

    def simulate_tap(self, device_id: str, x: int, y: int):
        """Simulate a tap at the specified (x, y) coordinates on the device."""
        command = f"-s {device_id} shell input tap {x} {y}"
        return self._run_command(command)

    def simulate_swipe(self, device_id: str, x1: int, y1: int, x2: int, y2: int, duration: int = 500):
        """Simulate a swipe from (x1, y1) to (x2, y2) over the specified duration in milliseconds."""
        command = f"-s {device_id} shell input swipe {x1} {y1} {x2} {y2} {duration}"
        return self._run_command(command)

    def simulate_string(self, device_id: str, string: str):
        """Simulate a text input on the device."""
        command = f"-s {device_id} shell input text {string}"
        return self._run_command(command)

    def _generate_hashed_filename(self) -> str:
        """Generate a unique hashed filename for the screenshot."""
        timestamp = str(time.time()).encode()
        hash_object = hashlib.sha256(timestamp)
        return f"{hash_object.hexdigest()}.png"

    async def wait_for_valid_png(self, file_path, timeout=5, interval=0.1):
        elapsed_time = 0

        while elapsed_time < timeout:
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                try:
                    with Image.open(file_path) as img:
                        img.verify()
                    return True
                except (OSError, IOError):
                    pass

            await asyncio.sleep(interval)
            elapsed_time += interval

        return False

    async def take_screenshot(self, device_id: str, return_bitmap: bool = False):
        """
        Capture a screenshot, save it in the temp directory, and return its path or bitmap image.
        """
        remote_path = "/sdcard/screen.png"
        capture_command = f"-s {device_id} shell screencap {remote_path}"

        try:
            # Execute the screenshot command
            self._run_command(capture_command)
        except Exception as e:
            logging.error(f"Failed to capture screenshot on device {device_id}: {e}")
            return None

        filename = self._generate_hashed_filename()
        save_path = os.path.join(self.screenshot_dir, filename)

        try:
            # Pull the screenshot from the device
            self.pull(device_id, remote_path, save_path)
        except Exception as e:
            logging.error(f"Failed to pull screenshot from {remote_path} to {save_path}: {e}")
            return None
        finally:
            # Ensure remote file is removed even if pull fails
            try:
                self.remove(device_id, remote_path, recursive=False)
            except Exception as e:
                logging.warning(f"Failed to remove remote screenshot file {remote_path}: {e}")

        if return_bitmap:
            try:
                # Ensure the PNG file is fully saved before loading
                if not await self.wait_for_valid_png(save_path):
                    logging.error(f"Image save failed or is incomplete: {save_path}")
                    return None

                # Load the image safely
                image = Image.open(save_path)
                image.load()
                return image
            except Exception as e:
                logging.error(f"Error loading image from {save_path}: {e}")
                return None
            finally:
                # Ensure local file cleanup
                try:
                    os.remove(save_path)
                except Exception as e:
                    logging.warning(f"Failed to delete local file {save_path}: {e}")

        return save_path

    # Temp sync function. Not used in the final code.
    def take_screenshot_(self, device_id: str, return_bitmap: bool = False):
        """Capture a screenshot, save it in the temp directory, and return its path or bitmap image."""
        remote_path = "/sdcard/screen.png"
        capture_command = f"-s {device_id} shell screencap {remote_path}"
        self._run_command(capture_command)

        filename = self._generate_hashed_filename()
        save_path = os.path.join(self.screenshot_dir, filename)
        self.pull(device_id, remote_path, save_path)
        self.remove(device_id, remote_path, recursive=False)

        if return_bitmap:
            while not os.path.exists(save_path):
                time.sleep(0.1)
            try:
                image = Image.open(save_path)
                image.load()
            except Exception as e:
                logging.error(f"Error loading image: {e}")
                return None
            finally:
                os.remove(save_path)
            return image

        return save_path

    def start_app(self, device_id: str, package_name: str, activity_name: str):
        """Start an application on the device using its package name and activity name."""
        command = f"-s {device_id} shell am start -n {package_name}/{activity_name}"
        return self._run_command(command)

    def close_app(self, device_id: str, package_name: str):
        """Close an application on the device using its package name."""
        command = f"-s {device_id} shell am force-stop {package_name}"
        return self._run_command(command)

    def is_app_running(self, device_id: str, package: str) -> bool:
        """Check if an app (identified by its package name) is running on the device."""
        command = f"-s {device_id} shell pidof {package}"
        output = self._run_command(command)

        if output is None or not output.strip():
            return False
        return True

    def remove(self, device_id: str, path: str, recursive: bool):
        """Remove a file or directory on the device."""
        if recursive:
            command = f"-s {device_id} shell rm -rf {path}"
        else:
            command = f"-s {device_id} shell rm {path}"
        return self._run_command(command)

    def copy(self, device_id: str, src: str, dest: str):
        """Copy files from one location to another on the device."""
        command = f"-s {device_id} shell cp {src} {dest}"
        return self._run_command(command)

    def pull(self, device_id: str, src: str, dest: str):
        """Pull files from the device to the local machine."""
        command = f"-s {device_id} pull {src} {dest}"
        return self._run_command(command)

    def push(self, device_id: str, src: str, dest: str):
        """Push files from the local machine to the device."""
        command = f"-s {device_id} push {src} {dest}"
        return self._run_command(command)