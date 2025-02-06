import sys
import json
import os
import datetime
import pywinctl
import asyncio
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QLabel,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QFileDialog,
    QDialog, QDialogButtonBox, QCheckBox, QGroupBox)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QIcon
from modules.game_manager import GameManager
from modules.player_manager import get_all_players
from utils.adb_interaction import ADBInteraction
from utils.adb_client import ADBClient
from modules.game_interaction import GameInteraction
from utils.config_loader import load_settings

class PlayerWindowNotFound(Exception):
    """Raised when the emulator window is not found."""
    pass

class ADBPortNotFound(Exception):
    """Raised when ADB port information is missing."""
    pass

class InitializationThread(QThread):
    """Thread to initialize ADB and game interaction asynchronously."""
    log_signal = pyqtSignal(str)
    init_done_signal = pyqtSignal(object, object, dict, object)
    error_signal = pyqtSignal(str)

    def run(self):
        """Run initialization in a separate thread."""
        self.log_signal.emit("🔄 시스템 초기화 시작...")

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
                error_msg = "❌ 뮤뮤 플레이어 인스턴스 찾을 수 없음."
                self.log_signal.emit(error_msg)
                raise RuntimeError(error_msg)  # Stop execution

            instance_count = settings.get("instance_count", 0)
            selected_players = [
                player for player in players
                if player['playerName'] and player['playerName'].isdigit() and 1 <= int(
                    player['playerName']) <= instance_count
            ]

            # Initialize device connections
            self.log_signal.emit(f"🔄 인스턴스 연결 중... ({instance_count}개 인스턴스)")
            device_list = {}

            for player in selected_players:
                if not self.window_exists(player["playerName"]):
                    error_msg = f"❌ 인스턴스 {player['playerName']}: 앱플레이어가 실행되지 않음."
                    self.log_signal.emit(error_msg)
                    raise PlayerWindowNotFound(error_msg)  # Stop execution

                port = player.get("adb_host_port")  # Use `.get()` to avoid KeyError
                if not port:
                    error_msg = f"❌ 인스턴스 {player['playerName']}: ADB 포트 정보를 찾을 수 없음."
                    self.log_signal.emit(error_msg)
                    raise ADBPortNotFound(error_msg)  # Stop execution

                if adb_client.connect(port):
                    self.log_signal.emit(f"✅ 인스턴스 {player['playerName']} 연결 성공. (ADB 포트: {port})")
                    device_list[player['playerName']] = f"127.0.0.1:{port}"
                else:
                    self.log_signal.emit(f"❌ 인스턴스 {player['playerName']} 연결 실패. (ADB 포트: {port})")

            # Signal completion
            self.init_done_signal.emit(adb, game, device_list, settings)

        except (PlayerWindowNotFound, ADBPortNotFound, RuntimeError) as e:
            self.log_signal.emit(f"🚨 초기화 중단: {str(e)}")  # Stop and log the error
            self.error_signal.emit(str(e))  # Signal the error to the main thread
        except Exception as e:
            self.log_signal.emit(f"❌ 초기화 실패. 오류: {str(e)}")  # Handle unexpected errors
            self.error_signal.emit(str(e))  # Signal the error to the main thread

    def window_exists(self, window_name: str) -> bool:
        """Check if a window with the given title exists (even if minimized)."""
        return window_name in pywinctl.getAllTitles()


class WorkerThread(QThread):
    """Worker thread for running automated gameplay."""
    log_signal = pyqtSignal(str)  # Signal for logging messages
    finished_signal = pyqtSignal(object)  # Signal when worker finishes execution

    def __init__(self, game, adb, device_name, device_id, task_kind, max_retry):
        super().__init__()
        self.game = game
        self.adb = adb
        self.device_name = device_name
        self.device_id = device_id
        self.task_kind = task_kind
        self.max_retry = max_retry
        self.running = True  # Flag to control execution
        self.current_task = None  # Store the currently running asyncio task
        self.result = None  # Store the result of the task
        self.game_manager = GameManager(game, adb, device_name, device_id,
                                        self.log_signal)  # Instance of GameManager for each device

    def run(self):
        """Run the worker thread with an event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.task())
        except asyncio.CancelledError:
            self.log_signal.emit(f"🛑 [인스턴스 {self.device_name}] 강제 중지됨.")
        finally:
            loop.close()

    async def task(self):
        """Execute automated gameplay with retry and stop support."""
        self.log_signal.emit(f"🔄 [인스턴스 {self.device_name}] 자동 {self.task_kind} 시작 중... (최대 재시도 횟수: {self.max_retry})")

        retry = 0
        while self.running and retry < self.max_retry:
            try:
                # Create and store the current async task
                if self.task_kind == "gather":
                    self.current_task = asyncio.create_task(self.game_manager.pack_gather())
                elif self.task_kind == "open":
                    self.current_task = asyncio.create_task(self.game_manager.pack_open())
                elif self.task_kind == "add":
                    self.current_task = asyncio.create_task(self.game_manager.friend_add())
                elif self.task_kind == "delete":
                    self.current_task = asyncio.create_task(self.game_manager.data_delete())
                else:
                    self.log_signal.emit(f"❌ [인스턴스 {self.device_name}] 알 수 없는 작업 종류: {self.task_kind}")
                    break
                success = await self.current_task  # Await execution

                result = await self.current_task
                if result is not None:
                    self.result = result
                    if self.task_kind == "gather":
                        self.log_signal.emit(f"✅ [인스턴스 {self.device_name}] 작업 완료. 닉네임: {result[0]}, 친구ID: {result[1]}")
                    else:
                        self.log_signal.emit(f"✅ [인스턴스 {self.device_name}] 작업 완료.")
                    break  # 작업 성공 시 종료
                else:
                    retry += 1
                    self.log_signal.emit(f"⚠️ [인스턴스 {self.device_name}] 작업 실패. 재시도 중... ({retry}/{self.max_retry})")
                    await asyncio.sleep(1)

            except asyncio.CancelledError:
                self.log_signal.emit(f"🛑 [인스턴스 {self.device_name}] 강제 중지됨.")
                break  # Exit loop immediately when canceled

            except Exception as e:
                self.log_signal.emit(f"❌ [인스턴스 {self.device_name}] 오류 발생: {str(e)}")
                retry += 1
                await asyncio.sleep(1)

        if retry >= self.max_retry:
            self.log_signal.emit(f"❌ [인스턴스 {self.device_name}] 작업 실패. 최대 재시도 횟수 초과.")

        self.finished_signal.emit(self)  # Signal to remove the worker

    def stop(self):
        """Forcefully stop the worker and cancel ongoing tasks."""
        self.running = False  # Set flag to stop execution

        # Cancel the currently running async task
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()

        self.log_signal.emit(f"🛑 [인스턴스 {self.device_name}] 강제 종료 요청됨.")

        self.quit()  # Stop the QThread
        self.wait()  # Ensure the thread is properly cleaned up

class DeviceSelectionDialog(QDialog):
    def __init__(self, devices: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("삭제할 인스턴스 선택")
        self.devices = devices
        self.checkboxes = {}

        layout = QVBoxLayout(self)

        instruction_label = QLabel("삭제할 인스턴스를 선택하세요:")
        layout.addWidget(instruction_label)

        for device_name, device_id in self.devices.items():
            checkbox = QCheckBox(f"{device_name} ({device_id})")
            layout.addWidget(checkbox)
            self.checkboxes[device_name] = checkbox

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_selected_devices(self) -> dict:
        selected_devices = {}
        for device_name, checkbox in self.checkboxes.items():
            print(device_name, checkbox.isChecked())
            if checkbox.isChecked():
                selected_devices[device_name] = self.devices[device_name]
        return selected_devices

class SettingsWindow(QWidget):
    """GUI for modifying the JSON settings file."""

    def __init__(self):
        super().__init__()
        self.init_ui()
        self.settings_data = {}
        self.load_settings()

    def init_ui(self):
        """Initialize the settings UI."""
        self.setWindowTitle("설정 편집")
        self.setGeometry(200, 200, 400, 300)

        layout = QVBoxLayout()

        self.settings_table = QTableWidget(self)
        layout.addWidget(self.settings_table)

        self.save_btn = QPushButton("설정 저장", self)
        self.save_btn.clicked.connect(self.save_settings)
        layout.addWidget(self.save_btn)

        self.setLayout(layout)

    def load_settings(self):
        """Load JSON settings from file."""
        if not os.path.exists("./config.json"):
            QMessageBox.critical(self, "오류", "설정 파일을 찾을 수 없음")
            return

        try:
            with open("./config.json", "r", encoding="utf-8") as file:
                self.settings_data = json.load(file)
                self.populate_table()
        except Exception as e:
            QMessageBox.critical(self, "오류", f"설정 불러오기 실패\n{str(e)}")

    def populate_table(self):
        """Display JSON data in the table."""
        self.settings_table.clear()
        self.settings_table.setRowCount(len(self.settings_data))
        self.settings_table.setColumnCount(2)
        self.settings_table.setHorizontalHeaderLabels(["Key", "Value"])

        for row, (key, value) in enumerate(self.settings_data.items()):
            self.settings_table.setItem(row, 0, QTableWidgetItem(str(key)))
            self.settings_table.setItem(row, 1, QTableWidgetItem(str(value)))

        # Adjust table layout
        self.settings_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.settings_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

    def save_settings(self):
        """Save modified JSON settings."""
        updated_data = {}

        for row in range(self.settings_table.rowCount()):
            key = self.settings_table.item(row, 0).text()
            value = self.settings_table.item(row, 1).text()
            try:
                updated_data[key] = json.loads(value)  # Convert value to original type
            except json.JSONDecodeError:
                updated_data[key] = value  # Keep as string if parsing fails

        try:
            with open("./config.json", "w", encoding="utf-8") as file:
                json.dump(updated_data, file, indent=4, ensure_ascii=False)

            QMessageBox.information(self, "성공", "세팅 저장 성공!")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"세팅 저장 실패\n{str(e)}")

class MainGUI(QWidget):
    """GUI for controlling automation workers."""

    def __init__(self):
        super().__init__()
        self.init_ui()

        # initialize ADB and Games
        self.adb = None
        self.game = None
        self.device_list = {}
        self.settings = None
        self.settings_window = None

        for widget in self.findChildren(QWidget):
            widget.setEnabled(False)
        self.log_text.setEnabled(True)

        # Start initialization in a separate thread
        self.init_thread = InitializationThread()
        self.init_thread.log_signal.connect(self.update_log)
        self.init_thread.init_done_signal.connect(self.initialization_complete)
        self.init_thread.error_signal.connect(self.initialization_failed)
        self.init_thread.start()

    def init_ui(self):
        """Initialize the main UI layout with grouped buttons."""
        self.setWindowTitle("PTCGPSP - Challenge Racing Automator")
        self.setWindowIcon(QIcon("data/ui/icon.ico"))
        self.setGeometry(100, 100, 500, 500)

        main_layout = QVBoxLayout()

        # Log output
        self.log_text = QTextEdit(self)
        self.log_text.setReadOnly(True)
        main_layout.addWidget(self.log_text)

        self.is_running = False

        # "매크로" GroupBox
        macro_group = QGroupBox("매크로", self)
        macro_layout = QVBoxLayout()

        self.gather_btn = QPushButton("팩 모으기 시작", self)
        self.gather_btn.setFixedHeight(25)
        self.gather_btn.clicked.connect(self.toggle_gather_task)
        macro_layout.addWidget(self.gather_btn)

        self.open_btn = QPushButton("팩 열기 시작", self)
        self.open_btn.setFixedHeight(25)
        self.open_btn.clicked.connect(self.toggle_open_task)
        macro_layout.addWidget(self.open_btn)

        self.add_btn = QPushButton("친구 추가 시작", self)
        self.add_btn.setFixedHeight(25)
        self.add_btn.clicked.connect(self.toggle_add_task)
        macro_layout.addWidget(self.add_btn)

        self.del_btn = QPushButton("일괄 계정 삭제 시작", self)
        self.del_btn.setFixedHeight(25)
        self.del_btn.clicked.connect(self.toggle_del_task)
        macro_layout.addWidget(self.del_btn)

        macro_group.setLayout(macro_layout)
        main_layout.addWidget(macro_group)

        # 기타" GroupBox
        etc_group = QGroupBox("기타", self)
        etc_layout = QVBoxLayout()

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

        self.delete_btn = QPushButton("삭제", self)
        self.delete_btn.setFixedHeight(25)
        self.delete_btn.clicked.connect(self.delete)
        instance_row.addWidget(self.delete_btn)

        etc_layout.addLayout(instance_row)

        button_row = QHBoxLayout()

        self.capture_btn = QPushButton("캡처", self)
        self.capture_btn.setFixedHeight(25)
        self.capture_btn.clicked.connect(self.capture_screenshot)
        button_row.addWidget(self.capture_btn)

        self.setting_btn = QPushButton("설정", self)
        self.setting_btn.setFixedHeight(25)
        self.setting_btn.clicked.connect(self.open_settings)
        button_row.addWidget(self.setting_btn)

        etc_layout.addLayout(button_row)

        etc_group.setLayout(etc_layout)
        main_layout.addWidget(etc_group)

        self.setLayout(main_layout)
        self.workers = []

    def initialization_complete(self, adb, game, device_list, settings):
        """Called when initialization is complete."""
        self.adb = adb
        self.game = game
        self.device_list = device_list
        self.settings = settings
        self.update_device_list()
        self.update_log("✅ 시스템 초기화 완료.")
        for widget in self.findChildren(QWidget):
            widget.setEnabled(True)

    def initialization_failed(self, error_message):
        """Called when initialization fails."""
        self.update_log(f"❌ 시스템 초기화 실패: {error_message}")
        for widget in self.findChildren(QWidget):
            widget.setEnabled(False)
        self.log_text.setEnabled(True)

    def start_task(self, task_kind):
        """Start automation for all detected devices."""

        if task_kind == "gather":
            self.open_btn.setEnabled(False)
            self.add_btn.setEnabled(False)
            self.del_btn.setEnabled(False)
            self.task_results = []
            timestamp = datetime.datetime.now().strftime("%y%m%d%H%M%S")
            result_dir = os.path.join(os.getcwd(), "result")
            os.makedirs(result_dir, exist_ok=True)
            self.result_file_path = os.path.join(result_dir, f"ids_{timestamp}.txt")
        elif task_kind == "open":
            self.gather_btn.setEnabled(False)
            self.add_btn.setEnabled(False)
            self.del_btn.setEnabled(False)
        elif task_kind == "add":
            self.gather_btn.setEnabled(False)
            self.open_btn.setEnabled(False)
            self.del_btn.setEnabled(False)

        for device_name, device_id in self.device_list.items():
            worker = WorkerThread(self.game, self.adb, device_name, device_id, task_kind, self.settings.get("max_retry", 3))
            worker.log_signal.connect(self.update_log)
            if task_kind == "gather":
                worker.finished_signal.connect(self.gather_task_finished)
            elif task_kind == "open":
                worker.finished_signal.connect(self.open_task_finished)
            elif task_kind == "add":
                worker.finished_signal.connect(self.add_task_finished)
            self.workers.append(worker)
            worker.start()

    def stop_task(self):
        """Stop all running workers."""
        for worker in self.workers:
            worker.stop()
        self.workers.clear()

    def toggle_gather_task(self):
        """Toggle start and stop for automation."""
        if self.is_running:
            self.stop_task()
            self.gather_btn.setText("팩 모으기 시작")
        else:
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setWindowTitle("경고")
            msg_box.setText("계속 진행 시 모든 인스턴스의 데이터가 초기화됩니다.\n계속 진행하시겠습니까?")
            msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg_box.setDefaultButton(QMessageBox.StandardButton.No)

            result = msg_box.exec()

            if result == QMessageBox.StandardButton.No:
                return

            self.start_task("gather")
            self.gather_btn.setText("팩 모으기 정지")

        self.is_running = not self.is_running

    def toggle_open_task(self):
        """Toggle start and stop for automation."""
        if self.is_running:
            self.stop_task()
            self.open_btn.setText("팩 열기 시작")
        else:
            self.start_task("open")
            self.open_btn.setText("팩 열기 정지")

        self.is_running = not self.is_running

    def toggle_add_task(self):
        """Toggle start and stop for automation."""
        if self.is_running:
            self.stop_task()
            self.add_btn.setText("친구 추가 시작")
        else:
            self.start_task("add")
            self.add_btn.setText("친구 추가 정지")

        self.is_running = not self.is_running

    def select_devices(self) -> dict:
        dialog = DeviceSelectionDialog(self.device_list, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.get_selected_devices()
        else:
            return {}

    def start_deletion_task(self, device_list: dict):
        """Start automation for selected devices."""

        for device_name, device_id in device_list.items():
            worker = WorkerThread(self.game, self.adb, device_name, device_id, "delete", self.settings.get("max_retry", 3))
            worker.log_signal.connect(self.update_log)
            worker.finished_signal.connect(self.del_task_finished)
            self.workers.append(worker)
            worker.start()

    def toggle_del_task(self):
        """Toggle start and stop for automation."""
        if self.is_running:
            self.stop_task()
            self.del_btn.setText("일괄 계정 삭제 시작")
        else:
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setWindowTitle("경고")
            msg_box.setText("계속 진행 시 인스턴스의 데이터가 초기화됩니다.\n계속 진행하시겠습니까?")
            msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg_box.setDefaultButton(QMessageBox.StandardButton.No)

            result = msg_box.exec()

            if result == QMessageBox.StandardButton.No:
                return

            devices = self.select_devices()
            print(devices)
            self.start_deletion_task(devices)
            self.del_btn.setText("일괄 계정 삭제 정지")

        self.is_running = not self.is_running

    def update_log(self, message):
        """Update the log text area."""
        self.log_text.append(message)

    def update_device_list(self):
        """Update the dropdown list with device_list keys."""
        self.instance_input.clear()
        self.instance_input.addItems(self.device_list.keys())

    def gather_task_finished(self, worker):
        """Handle worker completion."""
        if worker in self.workers:
            self.workers.remove(worker)

        if worker.result is not None:
            self.task_results.append(worker.result)

        if not self.workers:
            self.is_running = False
            self.gather_btn.setText("팩 모으기 시작")
            self.open_btn.setEnabled(True)
            self.add_btn.setEnabled(True)
            self.del_btn.setEnabled(True)
            with open(self.result_file_path, "w", encoding="utf-8") as f:
                for nickname, friend_id in self.task_results:
                    f.write(f"{nickname}, {friend_id}\n")
            self.update_log(f"✅ 팩 모으기 결과 저장됨: {self.result_file_path}")

    def open_task_finished(self, worker):
        """Handle worker completion."""
        if worker in self.workers:
            self.workers.remove(worker)

        if not self.workers:
            self.is_running = False
            self.open_btn.setText("팩 열기 시작")
            self.gather_btn.setEnabled(True)
            self.add_btn.setEnabled(True)
            self.del_btn.setEnabled(True)

    def add_task_finished(self, worker):
        """Handle worker completion."""
        if worker in self.workers:
            self.workers.remove(worker)

        if not self.workers:
            self.is_running = False
            self.add_btn.setText("친구 추가 시작")
            self.gather_btn.setEnabled(True)
            self.open_btn.setEnabled(True)
            self.del_btn.setEnabled(True)

    def del_task_finished(self, worker):
        """Handle worker completion."""
        if worker in self.workers:
            self.workers.remove(worker)

        if not self.workers:
            self.is_running = False
            self.del_btn.setText("일괄 계정 삭제 시작")
            self.gather_btn.setEnabled(True)
            self.open_btn.setEnabled(True)
            self.add_btn.setEnabled(True)

    def capture_screenshot(self):
        """Capture screenshot from the first connected device."""
        instance_name = self.instance_input.currentText()
        if instance_name not in self.device_list:
            self.update_log(f"❌ 인스턴스 '{instance_name}'를 찾을 수 없습니다.")
            return
        saved_path = self.adb.take_screenshot_(self.device_list[instance_name], return_bitmap=False)
        self.update_log(f"✅ 인스턴스 {instance_name} 스크린샷 저장 완료. (저장 위치: {saved_path})")

    def open_settings(self):
        """Open the settings editor."""
        if self.settings_window is None or not self.settings_window.isVisible():
            self.settings_window = SettingsWindow()
            self.settings_window.show()

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
    gui = MainGUI()
    gui.show()
    sys.exit(app.exec())
