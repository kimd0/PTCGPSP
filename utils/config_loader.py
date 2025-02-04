import json
import os

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "settings.json")

def load_settings():
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: '{SETTINGS_FILE}' not found.")
    except json.JSONDecodeError:
        print(f"Error: Failed to parse '{SETTINGS_FILE}'.")
    return {}
