from modules.player_manager import get_all_players
from utils.config_loader import load_settings
from utils.adb_client import ADBClient
from utils.adb_interaction import ADBInteraction
from modules.game_interaction import GameInteraction
from modules.game_manager import GameManager

def main():
    """Main execution function."""
    settings = load_settings()
    instance_count = settings.get("instance_count", 0)

    players = get_all_players()

    if not players:
        print("No MuMuPlayer instances found.")
        return

    selected_players = [
        player for player in players
        if player['playerName'] and player['playerName'].isdigit() and 1 <= int(player['playerName']) <= instance_count
    ]

    adb_client = ADBClient()
    adb = ADBInteraction(adb_client)
    game = GameInteraction(adb)

    print(f"Configured instance count: {instance_count}")
    print(f"Instances to connect: {[p['playerName'] for p in selected_players]}")

    for player in selected_players:
        port = player["adb_host_port"]
        if not port:
            print(f"Skipping {player['playerName']}: No ADB port information found.")
            continue

        device_id = f"127.0.0.1:{port}"

        if adb_client.connect(port):
            print(f"{player['playerName']} (ADB Port: {port}) connected successfully.")

            adb.take_screenshot(device_id, return_bitmap=False)

            # Automated gameplay
            #game_manager = GameManager(game, adb, device_id)

            #game_manager.automated_gameplay()
            """
            # Restart game with full data clearance
            game.restart_game(device_id, clear=True)

            # Backup account data
            backup_success = game.backup_account(device_id, "./backup")
            if backup_success:
                print(f"Account backup successful for {player['playerName']}")

            # Simulated user interaction
            adb.simulate_tap(device_id, 100, 200)

            # Take and save a screenshot
            screenshot_path = adb.take_screenshot(device_id, return_bitmap=False)
            if screenshot_path:
                print(f"Screenshot saved to {screenshot_path}")
            """

        else:
            print(f"Failed to connect {player['playerName']} (ADB Port: {port}).")

if __name__ == "__main__":
    main()
