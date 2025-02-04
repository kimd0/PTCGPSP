import logging
import os
import subprocess
from typing import Tuple
from utils.config_loader import load_settings

logging.basicConfig(level=logging.INFO)

class ADBClient:
    """Class to execute ADB commands with superuser privileges if available."""

    def __init__(self):
        """Load ADB path from settings."""
        self.settings = load_settings()
        self.adb_path = os.getenv("ADB_PATH", self.settings.get("adb_path", ""))
        self.superuser_enabled = False  # Track if superuser is available

        if not os.path.exists(self.adb_path):
            raise FileNotFoundError(f"ADB executable not found: {self.adb_path}")

    def run_command(self, command: str) -> Tuple[str, str]:
        """
        Execute an ADB command, ensuring superuser access is applied correctly.

        :param command: The ADB command to execute.
        :return: A tuple containing the command's stdout and stderr output.
        """
        is_shell_command = " shell " in command

        if self.superuser_enabled and is_shell_command:
            if "su -c" not in command:
                command = command.replace("shell", 'shell su -c "', 1) + '"'

        full_command = [self.adb_path] + command.split()
        try:
            result = subprocess.run(full_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
            return result.stdout.strip(), result.stderr.strip()
        except UnicodeDecodeError as e:
            logging.error(f"UnicodeDecodeError occurred: {e}")
            return "", f"UnicodeDecodeError: {e}"
        except Exception as e:
            logging.error(f"Error executing ADB: {e}")
            return "", str(e)

    def is_device_connected(self, port: int) -> bool:
        """
        Check if the ADB port is already connected.

        :param port: The ADB port number.
        :return: True if the device is connected, False otherwise.
        """
        output, error = self.run_command("devices")
        if error:
            logging.error(f"Error fetching ADB devices: {error}")
            return False
        return any(f"127.0.0.1:{port}" in line for line in output.split("\n"))

    def disconnect(self, port: int) -> bool:
        """
        Disconnect the ADB port before reconnecting.

        :param port: The ADB port number.
        :return: True if the disconnection was successful, False otherwise.
        """
        output, error = self.run_command(f"disconnect 127.0.0.1:{port}")
        if error:
            logging.error(f"Error disconnecting ADB on port {port}: {error}")
        return "disconnected" in output.lower()

    def connect(self, port: int) -> bool:
        """
        Connect to ADB on the given port and enable superuser mode if possible.

        :param port: The ADB port number.
        :return: True if the connection was successful, False otherwise.
        """
        if self.is_device_connected(port):
            logging.info(f"ADB port {port} is already connected, disconnecting first")
            self.disconnect(port)

        output, error = self.run_command(f"connect 127.0.0.1:{port}")
        if output and "connected" in output.lower():
            logging.info(f"ADB connected on port {port}, requesting superuser access...")
            self.enable_superuser(f"127.0.0.1:{port}")
            return True

        logging.error(f"Failed to connect ADB on port {port}: {error}")
        return False

    def enable_superuser(self, device_id: str) -> None:
        """
        Attempt to enable superuser mode for all future shell commands.

        :param device_id: The ADB device ID.
        """
        output, error = self.run_command(f"-s {device_id} shell su -c 'whoami'")

        if "root" in output:
            logging.info(f"Superuser access granted for {device_id}. All shell commands will run as root.")
            self.superuser_enabled = True  # Enable root mode for future shell commands
        else:
            logging.info(f"Superuser access not available on {device_id}. Running in normal mode.")
            self.superuser_enabled = False