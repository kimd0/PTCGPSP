import subprocess
import os
from utils.config_loader import load_settings

class ADBClient:
    """Class to execute ADB commands with superuser privileges if available."""

    def __init__(self):
        """Load ADB path from settings."""
        self.settings = load_settings()
        self.adb_path = self.settings.get("adb_path", "")
        self.superuser_enabled = False  # Track if superuser is available

        if not os.path.exists(self.adb_path):
            raise FileNotFoundError(f"ADB executable not found: {self.adb_path}")

    def run_command(self, command):
        """Execute an ADB command, ensuring superuser access is applied correctly."""
        is_shell_command = " shell " in command  # Detect shell commands correctly

        if self.superuser_enabled and is_shell_command:
            if "su -c" not in command:
                command = command.replace("shell", 'shell su -c "', 1) + '"'  # Add `su -c` correctly

        full_command = [self.adb_path] + command.split()
        try:
            result = subprocess.run(full_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
            return result.stdout.strip(), result.stderr.strip()
        except UnicodeDecodeError as e:
            print(f"UnicodeDecodeError occurred: {e}")
            return "", f"UnicodeDecodeError: {e}"
        except Exception as e:
            print(f"Error executing ADB: {e}")
            return "", str(e)

    def is_device_connected(self, port):
        """Check if the ADB port is already connected."""
        output, error = self.run_command("devices")
        if error:
            print(f"Error fetching ADB devices: {error}")
            return False
        return any(f"127.0.0.1:{port}" in line for line in output.split("\n"))

    def disconnect(self, port):
        """Disconnect the ADB port before reconnecting."""
        output, error = self.run_command(f"disconnect 127.0.0.1:{port}")
        if error:
            print(f"Error disconnecting ADB on port {port}: {error}")
        return "disconnected" in output.lower()

    def connect(self, port):
        """Connect to ADB on the given port and enable superuser mode if possible."""
        if self.is_device_connected(port):
            print(f"ADB port {port} is already connected, disconnecting first")
            self.disconnect(port)

        output, error = self.run_command(f"connect 127.0.0.1:{port}")
        if output and "connected" in output.lower():
            print(f"ADB connected on port {port}, requesting superuser access...")
            self.enable_superuser(f"127.0.0.1:{port}")
            return True

        print(f"Failed to connect ADB on port {port}: {error}")
        return False

    def enable_superuser(self, device_id):
        """Attempt to enable superuser mode for all future shell commands."""
        output, error = self.run_command(f"-s {device_id} shell su -c 'whoami'")

        if "root" in output:
            print(f"Superuser access granted for {device_id}. All shell commands will run as root.")
            self.superuser_enabled = True  # Enable root mode for future shell commands
        else:
            print(f"Superuser access not available on {device_id}. Running in normal mode.")
            self.superuser_enabled = False
