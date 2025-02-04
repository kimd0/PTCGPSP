import json
import os
import logging

logging.basicConfig(level=logging.INFO)

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "settings.json")

def load_settings() -> dict:
    """
    Load settings from the settings.json file.

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