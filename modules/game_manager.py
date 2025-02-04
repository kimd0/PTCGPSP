import time
import random
from modules.game_interaction import GameInteraction
from modules.image_search import template_match, search_until_found
from utils.adb_interaction import ADBInteraction

class GameManager:
    def __init__(self, game, adb, device_id):
        """Initialize with an instance of GameInteraction."""
        self.game = game
        self.adb = adb
        self.device_id = device_id
        self.current_step = 0

    def automated_gameplay(self):
        self.do_opening()
        self.do_nickname()
        #self.do_tutorial()
        return

    def do_opening(self):
        # Restart game with full data clearance
        self.game.restart_game(self.device_id, clear=True)

        # Check the title screen
        if not search_until_found(self.adb, self.device_id, "data/images/title.png"):
            print("Title screen not found.")
            self.restart_game()
            return
        self.adb.simulate_tap(self.device_id, 100, 100)
        time.sleep(1)

        # Enable speed mode
        self.adb.simulate_tap(self.device_id, 35, 145)
        time.sleep(1)
        self.adb.simulate_swipe(self.device_id, 35, 260, 200, 260, duration=300)
        self.adb.simulate_tap(self.device_id, 330, 500)

        # Set birthday
        if not search_until_found(self.adb, self.device_id, "data/images/birth_ok.png"):
            print("Birth screen not found.")
            self.restart_game()
            return
        self.adb.simulate_tap(self.device_id, 150, 700)
        time.sleep(0.5)
        self.adb.simulate_swipe(self.device_id, 150, 440, 150, 900, duration=300)
        self.adb.simulate_tap(self.device_id, 150, 550)
        time.sleep(0.5)
        self.adb.simulate_tap(self.device_id, 400, 700)
        time.sleep(0.5)
        self.adb.simulate_tap(self.device_id, 400, 600)
        time.sleep(0.5)
        self.adb.simulate_tap(self.device_id, 270, 860)
        time.sleep(0.5)
        self.adb.simulate_tap(self.device_id, 390, 640)

        # Agree to terms
        if not search_until_found(self.adb, self.device_id, "data/images/term.png"):
            print("Terms screen not found.")
            self.restart_game()
            return
        self.adb.simulate_tap(self.device_id, 260, 500)
        if not search_until_found(self.adb, self.device_id, "data/images/term_x.png"):
            print("Terms screen not found.")
            self.restart_game()
            return
        self.adb.simulate_tap(self.device_id, 260, 860)
        time.sleep(0.5)
        self.adb.simulate_tap(self.device_id, 260, 580)
        if not search_until_found(self.adb, self.device_id, "data/images/term_x.png"):
            print("Terms screen not found.")
            self.restart_game()
            return
        self.adb.simulate_tap(self.device_id, 260, 860)
        time.sleep(0.5)
        self.adb.simulate_tap(self.device_id, 260, 645)
        time.sleep(0.5)
        self.adb.simulate_tap(self.device_id, 260, 700)
        time.sleep(0.5)
        self.adb.simulate_tap(self.device_id, 260, 865)
        time.sleep(0.5)

        # Set data usage
        self.adb.simulate_tap(self.device_id, 160, 475)
        time.sleep(0.2)
        self.adb.simulate_tap(self.device_id, 160, 610)
        time.sleep(0.2)
        self.adb.simulate_tap(self.device_id, 160, 745)
        time.sleep(0.2)
        self.adb.simulate_tap(self.device_id, 270, 865)
        time.sleep(0.5)

        # No sync
        self.adb.simulate_tap(self.device_id, 260, 590)
        time.sleep(0.5)
        self.adb.simulate_tap(self.device_id, 270, 820)
        time.sleep(2)

        # Skip movie
        self.adb.simulate_tap(self.device_id, 485, 900)
        time.sleep(0.1)
        self.adb.simulate_tap(self.device_id, 485, 900)
        time.sleep(0.1)
        self.adb.simulate_tap(self.device_id, 485, 900)
        time.sleep(0.1)
        self.adb.simulate_tap(self.device_id, 485, 900)
        time.sleep(0.5)

        self.adb.simulate_tap(self.device_id, 270, 770)
        time.sleep(0.5)
        self.adb.simulate_tap(self.device_id, 400, 770)
        time.sleep(0.5)
        return

    def do_nickname(self):
        if not search_until_found(self.adb, self.device_id, "data/images/nickname.png"):
            print("Nickname screen not found.")
            self.restart_game()
            return
        self.adb.simulate_tap(self.device_id, 260, 410)
        time.sleep(1)
        self.adb.simulate_tap(self.device_id, 260, 410)
        time.sleep(1)
        self.adb.simulate_string(self.device_id, self.get_random_nickname())
        time.sleep(1)
        self.adb.simulate_tap(self.device_id, 390, 640)
        time.sleep(0.5)
        self.adb.simulate_tap(self.device_id, 260, 640)
        time.sleep(0.5)
        return

    def do_tutorial(self):
        return

    def do_add_friend(self):
        return

    def do_pack_opening(self):
        return

    def restart_game(self):
        self.game.restart_game(self.device_id, clear=True)
        self.current_step = 0
        self.automated_gameplay()
        return

    def get_random_nickname(self):
        with open("nickname.txt", "r", encoding="utf-8") as file:
            words = file.read().splitlines()
        return random.choice(words)

    def find_and_tap(self, template_path):
        x, y = search_until_found(self.adb, self.device_id, template_path)
        if x and y:
            self.adb.simulate_tap(self.device_id, x, y)
        self.restart_game()
