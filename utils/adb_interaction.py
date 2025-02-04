import os
import hashlib
import time
from PIL import Image
from utils.adb_client import ADBClient


class ADBInteraction:
    """Class to interact with ADB devices for simulated input, screenshots, and app management."""

    def __init__(self, adb_client: ADBClient):
        """Initialize with an instance of ADBClient."""
        self.adb_client = adb_client
        self.screenshot_dir = os.path.join(os.getcwd(), "temp")

        # Ensure the temp directory exists
        os.makedirs(self.screenshot_dir, exist_ok=True)

    def simulate_tap(self, device_id, x, y):
        """Simulate a tap at the specified (x, y) coordinates on the device."""
        command = f"-s {device_id} shell input tap {x} {y}"
        output, error = self.adb_client.run_command(command)
        if error:
            print(f"Error simulating tap on device {device_id}: {error}")
        return output

    def simulate_swipe(self, device_id, x1, y1, x2, y2, duration=500):
        """Simulate a swipe from (x1, y1) to (x2, y2) over the specified duration in milliseconds."""
        command = f"-s {device_id} shell input swipe {x1} {y1} {x2} {y2} {duration}"
        output, error = self.adb_client.run_command(command)
        if error:
            print(f"Error simulating swipe on device {device_id}: {error}")
        return output

    def simulate_string(self, device_id, string):
        """Simulate a text input on the device."""
        command = f"-s {device_id} shell input text {string}"
        output, error = self.adb_client.run_command(command)
        if error:
            print(f"Error simulating tap on device {device_id}: {error}")
        return output

    def _generate_hashed_filename(self):
        """Generate a unique hashed filename for the screenshot."""
        timestamp = str(time.time()).encode()
        hash_object = hashlib.sha256(timestamp)
        return f"{hash_object.hexdigest()}.png"

    def take_screenshot(self, device_id, return_bitmap=False):
        """Capture a screenshot, save it in the temp directory, and return its path or bitmap image."""
        remote_path = "/sdcard/screen.png"  # Use /sdcard instead of /data

        capture_command = f"-s {device_id} shell screencap -p {remote_path}"
        output, error = self.adb_client.run_command(capture_command)
        if error:
            print(f"Error taking screenshot on device {device_id}: {error}")
            return None

        filename = self._generate_hashed_filename()
        save_path = os.path.join(self.screenshot_dir, filename)

        pull_command = f"-s {device_id} pull {remote_path} {save_path}"
        output, error = self.adb_client.run_command(pull_command)
        if error:
            print(f"Error pulling screenshot to {save_path}: {error}")
            return None

        remove_command = f"-s {device_id} shell rm {remote_path}"
        self.adb_client.run_command(remove_command)

        if return_bitmap:
            try:
                # Load the image as a PIL Bitmap object
                image = Image.open(save_path)
                image.load()  # Force loading before deletion
            except Exception as e:
                print(f"Error loading image: {e}")
                return None
            finally:
                os.remove(save_path)
            return image  # Return the bitmap image

        return save_path

    def start_app(self, device_id, package_name, activity_name):
        """
        Start an application on the device using its package name and activity name.

        :param device_id: The ADB device ID.
        :param package_name: The package name of the application.
        :param activity_name: The activity name of the application.
        """
        command = f"-s {device_id} shell am start -n {package_name}/{activity_name}"
        output, error = self.adb_client.run_command(command)
        if error:
            print(f"Error starting app {package_name} on device {device_id}: {error}")
        return output

    def close_app(self, device_id, package_name):
        """
        Close an application on the device using its package name.

        :param device_id: The ADB device ID.
        :param package_name: The package name of the application.
        """
        command = f"-s {device_id} shell am force-stop {package_name}"
        output, error = self.adb_client.run_command(command)
        if error:
            print(f"Error closing app {package_name} on device {device_id}: {error}")
        return output
