import time
import random
import asyncio
from typing import Tuple, Any

import pyperclip
from modules.game_interaction import GameInteraction
from modules.image_search import template_match, search_until_found, search_until_found_pixel, TemplateCache
from utils.adb_interaction import ADBInteraction

class GameManager:
    def __init__(self, game, adb, device_name, device_id, log):
        """Initialize with an instance of GameInteraction."""
        self.game = game
        self.adb = adb
        self.device_name = device_name
        self.device_id = device_id
        self.log = log
        self.current_step = 0
        self.nickname = None
        self.friend_id = None
        self.template_cache = TemplateCache()

    async def pack_gather(self) -> tuple[Any, Any] | None:
        """Execute the full automated gameplay process and return success status."""
        self.log.emit(f"⏳ [인스턴스 {self.device_name}] 이미지 캐싱 중...")
        await self.template_cache.load_all_templates()
        self.log.emit(f"⏳ [인스턴스 {self.device_name}] 게임 시작 중...")
        total_start_time = time.time()  # 전체 실행 시작 시간

        async def log_step(step_name, step_func):
            start_time = time.time()
            result = await step_func()
            elapsed_time = time.time() - start_time
            self.log.emit(f"⏳ [인스턴스 {self.device_name}] {step_name} 완료 (소요 시간: {elapsed_time:.2f}초)")
            return result, elapsed_time

        total_elapsed = 0
        steps = [
            ("기본 정보 입력", self.do_opening),
            ("닉네임 설정", self.do_nickname),
            ("기본팩 오픈", self.do_firstpack),
            ("튜토리얼", self.do_tutorial),
            ("첫 챌린지", self.do_first_challenge),
            ("추가 챌린지", self.do_additional_challenge),
            ("미션 보상 수령", self.do_final_mission),
            ("아이디 복사", self.do_copy_id),
        ]

        for step_name, step_func in steps:
            success, elapsed_time = await log_step(step_name, step_func)
            total_elapsed += elapsed_time
            if not success:
                self.log.emit(f"⏳ [인스턴스 {self.device_name}] {step_name} 단계에서 실패, 프로세스 중단.")
                return None

        total_time = time.time() - total_start_time
        self.log.emit(f"⏳ [인스턴스 {self.device_name}] 모든 단계 완료! 총 소요 시간: {total_time:.2f}초")
        self.log.emit(f"⏳ [인스턴스 {self.device_name}] 닉네임: {self.nickname}, 친구 ID: {self.friend_id}")

        return self.nickname, self.friend_id

    async def pack_open(self) -> bool:
        """Open packs and return success status."""
        if not await self.do_pack_opening():
            return False
        # Temp code to test ui
        await asyncio.sleep(5)
        return True

    async def friend_add(self) -> bool:
        """Add friends and return success status."""
        if not await self.do_add_friend():
            return False
        # Temp code to test ui
        await asyncio.sleep(5)
        return True

    async def do_opening(self):
        # Restart game with full data clearance
        self.game.restart_game(self.device_id, clear=True)

        # Check title screen
        await self.find_and_tap("data/images/title.png", 5)

        # Enable speed mode
        await self.find_and_tap("data/images/mod.png", 1)
        self.adb.simulate_swipe(self.device_id, 35, 260, 200, 260, duration=300)
        await self.find_and_tap("data/images/mod_minimize.png", 1)

        # Check birthday screen
        if not await search_until_found(self.adb, self.device_id, "data/images/birth_ok.png"):
            print("Birth screen not found.")
            return False

        # Set year
        self.adb.simulate_tap(self.device_id, 150, 700)
        await asyncio.sleep(0.5)
        self.adb.simulate_swipe(self.device_id, 150, 440, 150, 900, duration=200)
        self.adb.simulate_tap(self.device_id, 150, 550)
        await asyncio.sleep(0.5)

        # Set month
        self.adb.simulate_tap(self.device_id, 400, 700)
        await asyncio.sleep(0.5)
        self.adb.simulate_tap(self.device_id, 400, 600)
        await asyncio.sleep(0.5)

        # Press OK
        self.adb.simulate_tap(self.device_id, 270, 860)
        await asyncio.sleep(0.5)

        # Press OK again
        await self.find_and_tap("data/images/birth_ok2.png", 1)

        # Read terms
        await self.find_and_tap("data/images/term1.png", 1)
        await self.find_and_tap("data/images/term_x.png", 1)
        await self.find_and_tap("data/images/term2.png", 1)
        await self.find_and_tap("data/images/term_x.png", 1)

        # Agree to terms and ok
        self.adb.simulate_tap(self.device_id, 85, 645)
        await asyncio.sleep(0.2)
        self.adb.simulate_tap(self.device_id, 85, 710)
        await asyncio.sleep(0.2)
        self.adb.simulate_tap(self.device_id, 270, 860)
        await asyncio.sleep(0.2)

        # Set data usage
        self.adb.simulate_tap(self.device_id, 160, 475)
        await asyncio.sleep(0.2)
        self.adb.simulate_tap(self.device_id, 160, 610)
        await asyncio.sleep(0.2)
        self.adb.simulate_tap(self.device_id, 160, 745)
        await asyncio.sleep(0.2)
        self.adb.simulate_tap(self.device_id, 270, 865)
        await asyncio.sleep(0.5)

        # No sync
        self.adb.simulate_tap(self.device_id, 260, 590)
        await asyncio.sleep(0.5)
        self.adb.simulate_tap(self.device_id, 270, 820)
        await asyncio.sleep(2)

        # Check for movie
        if not await search_until_found_pixel(self.adb, self.device_id, (2, 2, 2), tolerance=3):
            print("Movie screen not found.")
            return False

        # Skip movie
        self.adb.simulate_tap(self.device_id, 485, 900)
        await asyncio.sleep(0.1)
        self.adb.simulate_tap(self.device_id, 485, 900)
        await asyncio.sleep(0.1)
        self.adb.simulate_tap(self.device_id, 485, 900)
        await asyncio.sleep(0.1)
        self.adb.simulate_tap(self.device_id, 485, 900)
        await asyncio.sleep(0.5)


        self.adb.simulate_tap(self.device_id, 270, 770)
        await asyncio.sleep(0.3)
        self.adb.simulate_tap(self.device_id, 400, 770)
        await asyncio.sleep(0.5)
        return True

    async def do_nickname(self):
        await self.find_and_tap("data/images/nickname.png", 1)
        self.adb.simulate_tap(self.device_id, 260, 410)
        await asyncio.sleep(1)
        self.nickname = self.get_random_nickname()
        self.adb.simulate_string(self.device_id, self.nickname)
        await asyncio.sleep(0.2)

        await self.find_and_tap("data/images/nick_ok1.png", 1)
        await self.find_and_tap("data/images/nick_ok2.png", 1)
        await self.find_and_tap("data/images/nick_ok1.png", 1)
        return True

    async def do_firstpack(self):
        if not await search_until_found(self.adb, self.device_id, "data/images/firstpack.png"):
            print("First pack screen not found.")
            return False

        # Tap m2 pack
        self.adb.simulate_tap(self.device_id, 260, 550)
        await asyncio.sleep(0.3)
        self.adb.simulate_tap(self.device_id, 260, 750)

        if not await search_until_found(self.adb, self.device_id, "data/images/firstpack_open.png"):
            print("First pack open screen not found.")
            return False

        # Open pack swiping
        for _ in range(5):
            self.adb.simulate_swipe(self.device_id, 40, 550, 530, 550, duration=600)
            await asyncio.sleep(0.2)

        await asyncio.sleep(0.3)

        for _ in range(10):
            self.adb.simulate_tap(self.device_id, 270, 400)
            await asyncio.sleep(0.1)

        if not await search_until_found(self.adb, self.device_id, "data/images/firstpack_swipe.png"):
            print("First pack swipe screen not found.")
            return False

        for _ in range(5):
            self.adb.simulate_swipe(self.device_id, 260, 800, 260, 40, duration=100)
            await asyncio.sleep(0.2)

        if not await search_until_found(self.adb, self.device_id, "data/images/firstpack_logo.png"):
            print("First pack book screen not found.")
            return False

        for _ in range(5):
            self.adb.simulate_tap(self.device_id, 270, 640)
            await asyncio.sleep(0.1)

        await self.find_and_tap("data/images/firstpack_next.png", 1)
        await self.find_and_tap("data/images/firstpack_ok.png", 1)
        return True

    async def do_tutorial(self):
        if not await search_until_found_pixel(self.adb, self.device_id, (75, 251, 234), tolerance=3):
            print("Gray screen not found.")
            return False
        await self.find_and_tap("data/images/mission.png", 1)
        await self.find_and_tap("data/images/mission_get1.png", 1)
        await self.find_and_tap("data/images/mission_get1.png", 1)
        await asyncio.sleep(0.5)

        if not await search_until_found(self.adb, self.device_id, "data/images/mission_reward.png"):
            print("Mission gray reward screen not found.")
            return False
        self.adb.simulate_tap(self.device_id, 270, 900)

        await self.find_and_tap("data/images/mission_ok.png", 1)

        await asyncio.sleep(0.5)
        self.adb.simulate_tap(self.device_id, 270, 500)
        await asyncio.sleep(0.5)

        for _ in range(5):
            self.adb.simulate_tap(self.device_id, 270, 500)
            await asyncio.sleep(0.1)

        await asyncio.sleep(3)

        for _ in range(5):
            self.adb.simulate_tap(self.device_id, 270, 500)
            await asyncio.sleep(0.1)

        await self.find_and_tap("data/images/mission_ok.png", 1)
        await self.find_and_tap("data/images/realpack_open.png", 1)
        await self.find_and_tap("data/images/realpack_pass.png", 2)

        # Open pack swiping
        for _ in range(5):
            self.adb.simulate_swipe(self.device_id, 40, 550, 530, 550, duration=600)
            await asyncio.sleep(0.2)

        # Tap card
        for _ in range(7):
            self.adb.simulate_tap(self.device_id, 270, 480)
            await asyncio.sleep(0.1)

        await self.find_and_tap("data/images/realpack_next.png", 1)
        await self.find_and_tap("data/images/realpack_pass.png", 1)
        await self.find_and_tap("data/images/realpack_next.png", 1)
        await self.find_and_tap("data/images/realpack_ok.png", 1)

        await asyncio.sleep(1)
        for _ in range(5):
            self.adb.simulate_tap(self.device_id, 270, 480)
            await asyncio.sleep(0.2)

        return True

    async def do_first_challenge(self):
        await self.find_and_tap("data/images/challenge_icon.png", 1)

        if not await search_until_found(self.adb, self.device_id, "data/images/challenge_free.png"):
            print("Challenge start screen not found.")
            return False

        # Tap free challenge
        self.adb.simulate_tap(self.device_id, 270, 480)
        await asyncio.sleep(0.2)

        # Skip guide
        for _ in range(6):
            self.adb.simulate_tap(self.device_id, 370, 770)
            await asyncio.sleep(0.5)

        # Tap card and ok
        self.adb.simulate_tap(self.device_id, 350, 620)
        await asyncio.sleep(0.5)

        if not await search_until_found(self.adb, self.device_id, "data/images/challenge_free_enabled.png"):
            print("Challenge start screen not found.")
            return False
        self.adb.simulate_tap(self.device_id, 390, 820)
        await asyncio.sleep(0.5)

        # Pick card
        await self.find_and_tap("data/images/challenge_pick.png", 5)
        await self.find_and_tap("data/images/challenge_get.png", 1)
        await self.find_and_tap("data/images/realpack_pass.png", 1)
        await self.find_and_tap("data/images/realpack_next.png", 1)
        await self.find_and_tap("data/images/challenge_result.png", 1)

        # Skip final guide
        await self.find_and_tap("data/images/realpack_next.png", 1)
        for _ in range(5):
            self.adb.simulate_tap(self.device_id, 370, 770)
            await asyncio.sleep(0.5)
        return True

    async def do_additional_challenge(self):
        await self.find_and_tap("data/images/challenge_icon.png", 1)
        if not await search_until_found(self.adb, self.device_id, "data/images/challenge_title.png"):
            print("Challenge start screen not found.")
            return False

        self.adb.simulate_tap(self.device_id, 270, 400)
        await asyncio.sleep(0.2)

        await self.find_and_tap("data/images/challenge_ok.png", 1)
        await self.find_and_tap("data/images/challenge_pick.png", 5)
        await self.find_and_tap("data/images/challenge_get.png", 1)
        await self.find_and_tap("data/images/realpack_pass.png", 1)
        await self.find_and_tap("data/images/realpack_next.png", 1)
        await self.find_and_tap("data/images/challenge_result.png", 1)
        await self.find_and_tap("data/images/term_x.png", 1)
        await self.find_and_tap("data/images/challenge_back.png", 1)
        return True

    async def do_final_mission(self):
        if not await search_until_found(self.adb, self.device_id, "data/images/home_enabled.png"):
            print("Home screen not found.")
            return False
        await self.find_and_tap("data/images/mission_enabled.png", 1)
        await self.find_and_tap("data/images/mission_get1.png", 1)
        await self.find_and_tap("data/images/mission_get3.png", 1)
        await self.find_and_tap("data/images/mission_ok.png", 1)
        await asyncio.sleep(2)
        await self.find_and_tap("data/images/mission_x.png", 1)
        return True

    async def do_copy_id(self):
        if not await search_until_found(self.adb, self.device_id, "data/images/home_enabled.png"):
            print("Home screen not found.")
            return False
        await self.find_and_tap("data/images/social.png", 1)
        await self.find_and_tap("data/images/social_friend.png", 1)
        await self.find_and_tap("data/images/social_add.png", 1)
        await self.find_and_tap("data/images/social_copy.png", 1)
        self.friend_id = pyperclip.paste()
        return True

    async def do_add_friend(self):
        return True

    async def do_pack_opening(self):
        return True

    def get_random_nickname(self):
        with open("nickname.txt", "r", encoding="utf-8") as file:
            words = file.read().splitlines()
        return random.choice(words)

    async def find_and_tap(self, template_path, taps=1):
        result = await search_until_found(self.adb, self.device_id, template_path)

        if result is None:
            print(f"Template {template_path} not found.")
            return False

        x, y = result

        if x and y:
            for _ in range(taps):
                self.adb.simulate_tap(self.device_id, x, y)
                await asyncio.sleep(0.05)
