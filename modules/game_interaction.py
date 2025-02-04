import time
from utils.adb_interaction import ADBInteraction

class GameInteraction:
    """Class for handling game-specific interactions."""

    def __init__(self, adb_interaction: ADBInteraction):
        """Initialize with an instance of ADBInteraction."""
        self.adb_interaction = adb_interaction
        self.package_name = "jp.pokemon.pokemontcgp"
        self.activity_name = "com.unity3d.player.UnityPlayerActivity"
        self.remote_account_path = "/data/data/jp.pokemon.pokemontcgp/shared_prefs/deviceAccount:.xml"
        self.sdcard_account_path = "/sdcard/deviceAccount.xml"
        self.cache_path = "/data/data/jp.pokemon.pokemontcgp/cache/*"

    def start_game(self, device_id):
        """Start the game."""
        command = f"-s {device_id} shell am start -n {self.package_name}/{self.activity_name}"
        output, error = self.adb_interaction.adb_client.run_command(command)
        if error:
            print(f"Error starting app {self.package_name} on device {device_id}: {error}")
            return False
        return True

    def restart_game(self, device_id, clear=False):
        """Force stop and restart the game. If `clear=True`, clear cache and delete account."""
        self.adb_interaction.close_app(device_id, self.package_name)

        if clear:
            self.delete_account(device_id)
            self.clear_cache(device_id)

        self.start_game(device_id)

    def clear_cache(self, device_id):
        """Clear game cache with a delay of 1500ms."""
        command = f"-s {device_id} shell rm -rf {self.cache_path}"
        output, error = self.adb_interaction.adb_client.run_command(command)
        if error:
            print(f"Error clearing cache for {device_id}: {error}")
            return False

        time.sleep(2)  # Delay for cache clearance
        return True

    def backup_account(self, device_id, save_dir):
        """Backup account data."""
        copy_command = f"-s {device_id} shell cp {self.remote_account_path} {self.sdcard_account_path}"
        output, error = self.adb_interaction.adb_client.run_command(copy_command)
        if error:
            print(f"Error copying account data on device {device_id}: {error}")
            return False

        pull_command = f"-s {device_id} pull {self.sdcard_account_path} {save_dir}"
        output, error = self.adb_interaction.adb_client.run_command(pull_command)
        if error:
            print(f"Error pulling account backup from device {device_id}: {error}")
            return False

        delete_command = f"-s {device_id} shell rm {self.sdcard_account_path}"
        self.adb_interaction.adb_client.run_command(delete_command)

        return True

    def delete_account(self, device_id):
        """Delete account data from the game."""
        command = f"-s {device_id} shell rm {self.remote_account_path}"
        output, error = self.adb_interaction.adb_client.run_command(command)
        if error:
            print(f"Error deleting account on device {device_id}: {error}")
            return False
        return True
