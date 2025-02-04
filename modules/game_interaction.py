import logging
import time
from utils.adb_interaction import ADBInteraction

logging.basicConfig(level=logging.INFO)

class GameInteraction:
    """Class for handling game-specific interactions."""

    def __init__(self, adb_interaction: ADBInteraction):
        """Initialize with an instance of ADBInteraction."""
        self.adb_interaction = adb_interaction
        self.package_name = "jp.pokemon.pokemontcgp"
        self.activity_name = "com.unity3d.player.UnityPlayerActivity"
        self.remote_account_path = "/data/data/jp.pokemon.pokemontcgp/shared_prefs/deviceAccount:.xml"
        self.sdcard_account_path = "/sdcard/deviceAccount.xml"
        self.cache_path = "/data/data/jp.pokemon.pokemontcgp/*"

    def start_game(self, device_id: str) -> bool:
        """Start the game."""
        result = self.adb_interaction.start_app(device_id, self.package_name, self.activity_name)
        if result is None:
            logging.error(f"Error starting {self.package_name} on {device_id}")
            return False
        return True

    def restart_game(self, device_id: str, clear: bool = False) -> bool:
        """Force stop and restart the game. If `clear=True`, clear cache and delete account."""
        self.adb_interaction.close_app(device_id, self.package_name)
        if clear and not self.delete_account(device_id):
            return False
        return self.start_game(device_id)

    def clear_cache(self, device_id: str) -> bool:
        """Clear game cache data."""
        result = self.adb_interaction.remove(device_id, self.cache_path)
        if result is None:
            logging.error(f"Error clearing cache for {self.package_name}")
            return False
        time.sleep(2)  # Delay for cache clearance
        return True

    def backup_account(self, device_id: str, save_dir: str) -> bool:
        """Backup account data."""
        if self.adb_interaction.copy(device_id, self.remote_account_path, self.sdcard_account_path) is None:
            logging.error(f"Error copying account data on {device_id}")
            return False
        time.sleep(1)

        if self.adb_interaction.pull(device_id, self.sdcard_account_path, save_dir) is None:
            logging.error(f"Error pulling account data from {device_id}")
            return False
        time.sleep(1)

        if self.adb_interaction.remove(device_id, self.sdcard_account_path) is None:
            logging.error(f"Error deleting temporary account file on {device_id}")
            return False
        time.sleep(1)

        return True

    def delete_account(self, device_id: str) -> bool:
        """Delete account data from the game."""
        result = self.adb_interaction.remove(device_id, self.remote_account_path)
        if result is None:
            logging.error(f"Error deleting account data on {device_id}")
            return False
        return True

    def inject_account(self, device_id: str, account_dir: str) -> bool:
        """Inject account data into the game."""
        if self.adb_interaction.push(device_id, account_dir, self.sdcard_account_path) is None:
            logging.error(f"Error pushing account data to {device_id}")
            return False
        time.sleep(1)

        if self.adb_interaction.copy(device_id, self.sdcard_account_path, self.remote_account_path) is None:
            logging.error(f"Error copying account data on {device_id}")
            return False
        time.sleep(1)

        if self.adb_interaction.remove(device_id, self.sdcard_account_path) is None:
            logging.error(f"Error deleting temporary account file on {device_id}")
            return False
        time.sleep(1)

        return True
