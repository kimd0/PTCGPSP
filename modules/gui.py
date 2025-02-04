import sys
import asyncio
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit
from PyQt6.QtCore import QThread, pyqtSignal, QTimer
from modules.game_manager import GameManager
from modules.player_manager import get_all_players
from utils.adb_interaction import ADBInteraction
from utils.adb_client import ADBClient
from modules.game_interaction import GameInteraction
from utils.config_loader import load_settings

class InitializationThread(QThread):
    """Thread to initialize ADB and game interaction asynchronously."""
    log_signal = pyqtSignal(str)
    init_done_signal = pyqtSignal(object, object)  # ADBInteraction, GameInteraction 전달

    def run(self):
        """Run initialization in a separate thread."""
        self.log_signal.emit("🔄 시스템 초기화를 시작합니다.")

        try:
            # Initialize settings
            settings = load_settings()

            # Initialize ADB Client
            self.log_signal.emit("🔌 ADB를 초기화합니다..")
            self.adb_client = ADBClient()
            self.adb = ADBInteraction(self.adb_client)
            self.log_signal.emit("✅ ADB interaction 준비됨.")

            # Initialize Game Interaction
            self.game = GameInteraction(self.adb)
            self.log_signal.emit("✅ Game interaction 준비됨.")

            # Fetch MuMuPlayer instances
            players = get_all_players()
            if not players:
                self.log_signal.emit("❌ 뮤뮤 플레이어 인스턴스를 찾을 수 없습니다.")
                return

            instance_count = settings.get("instance_count", 0)
            selected_players = [
                player for player in players
                if player['playerName'] and player['playerName'].isdigit() and 1 <= int(
                    player['playerName']) <= instance_count
            ]

            # Initialize device connections
            self.log_signal.emit(f"🔄 인스턴스와 연결 중입니다... ({instance_count}개 인스턴스)")
            self.device_list = {}
            for player in selected_players:
                port = player["adb_host_port"]
                if not port:
                    self.log_signal.emit(f"❌ 인스턴스 {player['playerName']}: ADB 포트 정보를 찾을 수 없습니다.")
                    continue
                self.device_list[player['playerName']] = f"127.0.0.1:{port}"
                if self.adb_client.connect(port):
                    self.log_signal.emit(f"✅ 인스턴스 {player['playerName']} 연결에 성공하였습니다. (ADB 포트: {port})")
                else:
                    self.log_signal.emit(f"❌ 인스턴스 {player['playerName']} 연결에 실패하였습니다. (ADB 포트: {port})")

        except Exception as e:
            self.log_signal.emit(f"❌ 초기화 실패. 오류: {str(e)}")

class WorkerThread(QThread):
    """Worker thread for running automated gameplay."""
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(object)

    def __init__(self, device_name, device_id):
        super().__init__()
        self.device_name = device_name
        self.device_id = device_id
        self.running = True
        self.game_manager = GameManager(device_id)  # 각 디바이스에 대한 GameManager 인스턴스 생성

    def run(self):
        """Run the worker thread with an event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.task())

    async def task(self):
        """Execute automated gameplay."""
        self.log_signal.emit(f"[{self.device_name} (port:{self.device_id})] Starting automation...")
        try:
            await self.game_manager.automated_gameplay()
            self.log_signal.emit(f"[{self.device_name} (port:{self.device_id})] Automation completed.")
        except Exception as e:
            self.log_signal.emit(f"[{self.device_name} (port:{self.device_id})] Error: {str(e)}")

        self.finished_signal.emit(self)  # Signal to remove the worker

    def stop(self):
        """Stop the worker."""
        self.running = False
        self.quit()
        self.wait()


class GameGUI(QWidget):
    """GUI for controlling automation workers."""

    def __init__(self):
        super().__init__()
        self.init_ui()

        # initialize ADB and Games
        self.adb = None
        self.game = None
        self.device_list = None

        # Start initialization in a separate thread
        self.init_thread = InitializationThread()
        self.init_thread.log_signal.connect(self.update_log)
        self.init_thread.init_done_signal.connect(self.initialization_complete)
        self.init_thread.start()

    def init_ui(self):
        self.setWindowTitle("Game Automation GUI")
        self.setGeometry(100, 100, 500, 400)  # Adjusted height for new layout

        layout = QVBoxLayout()

        self.log_text = QTextEdit(self)
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        self.start_btn = QPushButton("Start Automation", self)
        self.start_btn.setFixedHeight(25)  # Standard button size
        self.start_btn.clicked.connect(self.start_task)
        layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop Automation", self)
        self.stop_btn.setFixedHeight(25)
        self.stop_btn.clicked.connect(self.stop_task)
        self.stop_btn.setEnabled(False)
        layout.addWidget(self.stop_btn)

        # temporary debug buttons
        button_row = QHBoxLayout()

        self.capture_btn = QPushButton("Capture", self)
        self.capture_btn.setFixedHeight(25)
        self.capture_btn.clicked.connect(self.capture_screenshot)
        button_row.addWidget(self.capture_btn)

        self.connect_btn = QPushButton("Device List", self)
        self.connect_btn.setFixedHeight(25)
        self.connect_btn.clicked.connect(self.connect_device)
        button_row.addWidget(self.connect_btn)

        layout.addLayout(button_row)  # 가로 레이아웃 추가

        self.setLayout(layout)
        self.workers = []

    def initialization_complete(self, adb, game, device_list):
        """Called when initialization is complete."""
        self.adb = adb
        self.game = game
        self.device_list = device_list
        self.update_log("✅ System initialization complete!")

    def start_task(self):
        """Start automation for all detected devices."""
        devices = get_all_players()  # ADB에서 활성화된 플레이어 가져오기
        if not devices:
            self.update_log("No devices found!")
            return

        for player in devices:
            device_id = player["adb_host_port"]
            worker = WorkerThread(device_id)
            worker.log_signal.connect(self.update_log)
            worker.finished_signal.connect(self.task_finished)
            self.workers.append(worker)
            worker.start()

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def stop_task(self):
        """Stop all running workers."""
        for worker in self.workers:
            worker.stop()
        self.workers.clear()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def update_log(self, message):
        """Update the log text area."""
        self.log_text.append(message)

    def task_finished(self, worker):
        """Handle worker completion."""
        if worker in self.workers:
            self.workers.remove(worker)

        if not self.workers:
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)

    def capture_screenshot(self):
        """Capture screenshot from the first connected device."""
        self.update_log(f"{self.device_list['1']}로부터 스크린샷 시도")
        self.adb.take_screenshot(self.device_list['1'], return_bitmap=False)
        self.update_log(f"Screenshot saved.")

    def connect_device(self):
        devices = get_all_players()
        if not devices:
            self.update_log("No devices found.")
        else:
            self.update_log(f"Connected devices: {', '.join([d['adb_host_port'] for d in devices])}")


def launch_gui():
    """Launch the GUI application."""
    app = QApplication(sys.argv)
    gui = GameGUI()
    gui.show()
    sys.exit(app.exec())
