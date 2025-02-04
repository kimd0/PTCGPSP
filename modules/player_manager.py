import os
import json
from utils.config_loader import load_settings

settings = load_settings()
BASE_PATH = settings.get("base_path", "")


def get_player_info(vm_path):
    configs_path = os.path.join(vm_path, "configs")
    vm_config_file = os.path.join(configs_path, "vm_config.json")
    extra_config_file = os.path.join(configs_path, "extra_config.json")

    player_name = None
    adb_host_port = None

    if os.path.exists(vm_config_file):
        try:
            with open(vm_config_file, "r", encoding="utf-8") as f:
                vm_config = json.load(f)
                adb_host_port = vm_config.get("vm", {}).get("nat", {}).get("port_forward", {}).get("adb", {}).get(
                    "host_port")
        except json.JSONDecodeError:
            print(f"Error parsing {vm_config_file}")

    if os.path.exists(extra_config_file):
        try:
            with open(extra_config_file, "r", encoding="utf-8") as f:
                extra_config = json.load(f)
                player_name = extra_config.get("playerName")
        except json.JSONDecodeError:
            print(f"Error parsing {extra_config_file}")

    return {"playerName": player_name, "adb_host_port": adb_host_port}


def get_all_players():
    if not BASE_PATH or not os.path.exists(BASE_PATH):
        print("Error: Invalid base path in settings.")
        return []

    players_info = []
    for folder in os.listdir(BASE_PATH):
        vm_folder = os.path.join(BASE_PATH, folder)
        if os.path.isdir(vm_folder):
            player_info = get_player_info(vm_folder)
            if player_info["playerName"] and player_info["adb_host_port"]:
                players_info.append(player_info)

    return players_info