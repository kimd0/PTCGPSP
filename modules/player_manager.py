import os
import json
import logging
from utils.config_loader import load_settings

logging.basicConfig(level=logging.INFO)

settings = load_settings()
BASE_PATH = os.getenv("BASE_PATH", settings.get("base_path", ""))

def get_player_info(vm_path: str) -> dict:
    """
    Retrieve player information from the given VM path.

    :param vm_path: Path to the VM directory.
    :return: Dictionary containing player name and ADB host port.
    """
    configs_path = os.path.join(vm_path, "configs")
    vm_config_file = os.path.join(configs_path, "vm_config.json")
    extra_config_file = os.path.join(configs_path, "extra_config.json")

    player_name = None
    adb_host_port = None

    if os.path.exists(vm_config_file):
        try:
            with open(vm_config_file, "r", encoding="utf-8") as f:
                vm_config = json.load(f)
                adb_host_port = vm_config.get("vm", {}).get("nat", {}).get("port_forward", {}).get("adb", {}).get("host_port")
        except json.JSONDecodeError:
            logging.error(f"Error parsing {vm_config_file}")

    if os.path.exists(extra_config_file):
        try:
            with open(extra_config_file, "r", encoding="utf-8") as f:
                extra_config = json.load(f)
                player_name = extra_config.get("playerName")
        except json.JSONDecodeError:
            logging.error(f"Error parsing {extra_config_file}")

    return {"playerName": player_name, "adb_host_port": adb_host_port}

def get_all_players() -> list:
    """
    Retrieve information for all players.

    :return: List of dictionaries containing player information.
    """
    if not BASE_PATH or not os.path.exists(BASE_PATH):
        logging.error("Error: Invalid base path in settings.")
        return []

    players_info = []
    for folder in os.listdir(BASE_PATH):
        vm_folder = os.path.join(BASE_PATH, folder)
        if os.path.isdir(vm_folder):
            player_info = get_player_info(vm_folder)
            if player_info["playerName"] and player_info["adb_host_port"]:
                players_info.append(player_info)

    return players_info