import sys
import os
import datetime
import asyncio
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QLabel, QLineEdit, QFileDialog, QComboBox
from PyQt6.QtCore import QThread, pyqtSignal
from modules.game_manager import GameManager
from modules.player_manager import get_all_players
from utils.adb_interaction import ADBInteraction
from utils.adb_client import ADBClient
from modules.game_interaction import GameInteraction
from utils.config_loader import load_settings

class InitializationThread(QThread):
    """Thread to initialize ADB and game interaction asynchronously."""
    log_signal = pyqtSignal(str)
    init_done_signal = pyqtSignal(object, object, dict)  # ✅ ADBInteraction, GameInteraction, device_list 전달

    def run(self):
        """Run initialization in a separate thread."""
        self.log_signal.emit("🔄 시스템 초기화를 시작합니다.")

        try:
            # Initialize settings
            settings = load_settings()

            # Initialize ADB Client
            self.log_signal.emit("🔄 ADB와 게임 컨트롤러 초기화 중...")
            adb_client = ADBClient()
            adb = ADBInteraction(adb_client)
            self.log_signal.emit("✅ ADB interaction 준비됨.")

            # Initialize Game Interaction
            game = GameInteraction(adb)
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
            device_list = {}
            for player in selected_players:
                port = player["adb_host_port"]
                if not port:
                    self.log_signal.emit(f"❌ 인스턴스 {player['playerName']}: ADB 포트 정보를 찾을 수 없습니다.")
                    continue

                if adb_client.connect(port):
                    self.log_signal.emit(f"✅ 인스턴스 {player['playerName']} 연결에 성공하였습니다. (ADB 포트: {port})")
                    device_list[player['playerName']] = f"127.0.0.1:{port}"
                else:
                    self.log_signal.emit(f"❌ 인스턴스 {player['playerName']} 연결에 실패하였습니다. (ADB 포트: {port})")

            # Signal completion
            self.init_done_signal.emit(adb, game, device_list)

        except Exception as e:
            self.log_signal.emit(f"❌ 초기화 실패. 오류: {str(e)}")


class WorkerThread(QThread):
    """Worker thread for running automated gameplay."""
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(object)

    def __init__(self, game, adb, device_name, device_id):
        super().__init__()
        self.game = game
        self.adb = adb
        self.device_name = device_name
        self.device_id = device_id
        self.running = True
        self.game_manager = GameManager(game, adb, device_name, device_id, self.log_signal)  # 각 디바이스에 대한 GameManager 인스턴스 생성

    def run(self):
        """Run the worker thread with an event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.task())

    async def task(self):
        """Execute automated gameplay."""
        self.log_signal.emit(f"🔄 [인스턴스 {self.device_name}] 자동화 시작 중...")
        try:
            await self.game_manager.automated_gameplay()
            self.log_signal.emit(f"✅ [인스턴스 {self.device_name}] 작업 완료.")
        except Exception as e:
            self.log_signal.emit(f"❌ [인스턴스 {self.device_name}] 오류 발생: {str(e)}")

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
        self.device_list = {}

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

        instance_row = QHBoxLayout()

        self.instance_label = QLabel("인스턴스 선택", self)
        instance_row.addWidget(self.instance_label)

        self.instance_input = QComboBox(self)
        self.instance_input.setEditable(False)
        instance_row.addWidget(self.instance_input)

        self.backup_btn = QPushButton("백업", self)
        self.backup_btn.setFixedHeight(25)
        self.backup_btn.clicked.connect(self.backup)
        instance_row.addWidget(self.backup_btn)

        self.restore_btn = QPushButton("복구", self)
        self.restore_btn.setFixedHeight(25)
        self.restore_btn.clicked.connect(self.restore)
        instance_row.addWidget(self.restore_btn)

        self.backup_btn = QPushButton("삭제", self)
        self.backup_btn.setFixedHeight(25)
        self.backup_btn.clicked.connect(self.delete)
        instance_row.addWidget(self.backup_btn)

        layout.addLayout(instance_row)

        self.setLayout(layout)
        self.workers = []

    def initialization_complete(self, adb, game, device_list):
        """Called when initialization is complete."""
        self.adb = adb
        self.game = game
        self.device_list = device_list
        self.update_device_list()
        self.update_log("✅ 시스템 초기화 완료.")

    def start_task(self):
        """Start automation for all detected devices."""

        for device_name, device_id in self.device_list.items():
            worker = WorkerThread(self.game, self.adb, device_name, device_id)
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

    def update_device_list(self):
        """Update the dropdown list with device_list keys."""
        self.instance_input.clear()
        self.instance_input.addItems(self.device_list.keys())

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
        saved_path = self.adb.take_screenshot_(self.device_list['1'], return_bitmap=False)
        self.update_log(f"Screenshot saved at {saved_path}.")

    def connect_device(self):
        devices = get_all_players()
        if not devices:
            self.update_log("No devices found.")
        else:
            self.update_log(f"Connected devices: {', '.join([d['adb_host_port'] for d in devices])}")

    def backup(self):
        """Perform backup with user-selected filename."""
        instance_name = self.instance_input.currentText()
        if instance_name not in self.device_list:
            self.update_log(f"❌ 인스턴스 '{instance_name}'를 찾을 수 없습니다.")
            return

        # Ensure the backup directory exists
        backup_dir = os.path.join(os.getcwd(), "backup")
        os.makedirs(backup_dir, exist_ok=True)

        # Generate default filename
        timestamp = datetime.datetime.now().strftime("%y%m%d%H%M%S")
        default_filename = f"save_{timestamp}.xml"

        # Open file dialog for saving
        file_path, _ = QFileDialog.getSaveFileName(self, "백업 파일 저장",
                                                   os.path.join(backup_dir, default_filename),
                                                   "XML Files (*.xml);;All Files (*)")

        # If the user cancels, do nothing
        if not file_path:
            self.update_log(f"⚠️ 인스턴스 {instance_name} 백업이 취소되었습니다.")
            return

        # Perform backup
        if not self.game.backup_account(self.device_list[instance_name], file_path):
            self.update_log(f"❌ 인스턴스 {instance_name} 백업 실패.")
            return

        self.update_log(f"✅ 인스턴스 {instance_name} 백업 완료: {file_path}")

    def restore(self):
        """Restore backup from user-selected file."""
        instance_name = self.instance_input.currentText()
        if instance_name not in self.device_list:
            self.update_log(f"❌ 인스턴스 '{instance_name}'를 찾을 수 없습니다.")
            return

        # Open file dialog for selecting the backup file
        file_path, _ = QFileDialog.getOpenFileName(self, "복구할 백업 파일 선택",
                                                   os.path.join(os.getcwd(), "backup"),
                                                   "XML Files (*.xml);;All Files (*)")

        # If the user cancels, do nothing
        if not file_path:
            self.update_log("⚠️ 인스턴스 {instance_name} 복구가 취소되었습니다.")
            return

        # Perform restore
        if not self.game.inject_account(self.device_list[instance_name], file_path):
            self.update_log("❌ 인스턴스 {instance_name} 복구 실패.")
            return

        self.update_log(f"✅ 인스턴스 {instance_name} 복구 완료: {file_path}")

    def delete(self):
        """Delete account data from the game."""
        instance_name = self.instance_input.currentText()
        if instance_name not in self.device_list:
            self.update_log(f"❌ 인스턴스 '{instance_name}'를 찾을 수 없습니다.")
            return

        if not self.game.delete_account(self.device_list[instance_name]):
            self.update_log(f"❌ 인스턴스 {instance_name} 세이브 삭제 실패.")
            return

        self.update_log(f"✅ 인스턴스 {instance_name} 세이브 삭제 완료.")

def launch_gui():
    """Launch the GUI application."""
    app = QApplication(sys.argv)
    gui = GameGUI()
    gui.show()
    sys.exit(app.exec())
