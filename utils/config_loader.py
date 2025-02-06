import json
import os
import sys
import logging

logging.basicConfig(level=logging.INFO)

if getattr(sys, 'frozen', False):
    base_path = os.path.dirname(sys.executable)
else:
    base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

SETTINGS_FILE = os.path.join(base_path, "config.json")

def load_settings() -> dict:
    """
    Load settings from the config.json file.

    :return: Dictionary containing settings.
    """
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"Error: '{SETTINGS_FILE}' not found.")
    except json.JSONDecodeError:
        logging.error(f"Error: Failed to parse '{SETTINGS_FILE}'.")
    return {}