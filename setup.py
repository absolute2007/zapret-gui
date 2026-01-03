
import sys
import os
import shutil
import zipfile
import subprocess
import traceback
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLabel, 
                           QPushButton, QProgressBar, QMessageBox, QFrame)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer


# Constants
INSTALL_DIR_NAME = "zapret-gui"
APP_NAME = "Zapret GUI"

def get_base_install_dir() -> Path:
    return Path.home() / INSTALL_DIR_NAME

def get_app_dir() -> Path:
    return get_base_install_dir() / "app"

class InstallThread(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)

    def run(self):
        try:
            # 1. Prepare dirs
            logging.info("Preparing directories...")
            self.progress.emit(10, "Подготовка директорий...")
            base_dir = get_base_install_dir()
            app_dir = get_app_dir()
            
            logging.info(f"Base dir: {base_dir}")
            logging.info(f"App dir: {app_dir}")

            # Kill existing process if running
            logging.info("Killing existing processes...")
            subprocess.run("taskkill /F /IM ZapretGUI.exe", shell=True, 
                         creationflags=subprocess.CREATE_NO_WINDOW, capture_output=True)
            
            if app_dir.exists():
                logging.info("Removing existing app dir...")
                shutil.rmtree(app_dir)
            app_dir.mkdir(parents=True, exist_ok=True)
            
            # Create zapret dir
            zapret_dir = base_dir / "zapret"
            zapret_dir.mkdir(parents=True, exist_ok=True)
            logging.info(f"Zapret dir created: {zapret_dir}")

            # 2. Extract payload
            self.progress.emit(30, "Распаковка файлов...")
            
            # Look for bundled zip (added via PyInstaller datas)
            # In onefile mode, resources are in sys._MEIPASS
            if hasattr(sys, '_MEIPASS'):
                zip_path = Path(sys._MEIPASS) / "app.zip"
                logging.info(f"Found _MEIPASS: {sys._MEIPASS}")
            else:
                zip_path = Path("app.zip") # Dev mode
                logging.info("Running in dev mode (no _MEIPASS)")
                
            logging.info(f"Zip path: {zip_path}")
                
            if not zip_path.exists():
                logging.error("app.zip not found!")
                raise FileNotFoundError("app.zip not found in installer")

            logging.info("Starting extraction...")
            with zipfile.ZipFile(zip_path, 'r') as z:
                # Get total size for progress
                total_size = sum(info.file_size for info in z.infolist())
                extracted_size = 0
                
                logging.info(f"Total size to extract: {total_size}")
                
                for info in z.infolist():
                    logging.debug(f"Extracting {info.filename}")
                    z.extract(info, app_dir)
                    extracted_size += info.file_size
                    # Progress from 30 to 90
                    pct = 30 + int((extracted_size / total_size) * 60)
                    self.progress.emit(pct, f"Распаковка: {info.filename}")

            # 3. Create Shortcut
            self.progress.emit(90, "Создание ярлыка...")
            target_exe = app_dir / "ZapretGUI.exe"
            create_shortcut(target_exe)
            
            self.progress.emit(100, "Готово!")
            self.finished.emit(True, str(target_exe))
            
        except Exception as e:
            logging.error(f"Installation failed: {e}")
            logging.error(traceback.format_exc())
            traceback.print_exc()
            self.finished.emit(False, str(e))

def create_shortcut(target_path: Path):
    try:
        desktop = Path.home() / "Desktop"
        shortcut_path = desktop / "Zapret GUI.lnk"
        
        ps_script = f'''
        $WshShell = New-Object -comObject WScript.Shell
        $Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
        $Shortcut.TargetPath = "{target_path}"
        $Shortcut.WorkingDirectory = "{target_path.parent}"
        $Shortcut.IconLocation = "{target_path}"
        $Shortcut.Save()
        '''
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], 
                      creationflags=subprocess.CREATE_NO_WINDOW, capture_output=True)
    except:
        pass

class InstallerWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Установка {APP_NAME}")
        self.setFixedSize(500, 350)
        
        # Style
        self.setStyleSheet("""
            QWidget { background-color: #202020; color: white; font-family: 'Segoe UI', sans-serif; }
            QPushButton { 
                background-color: #0078d4; border: none; border-radius: 4px; 
                padding: 8px 16px; font-weight: bold; font-size: 14px;
            }
            QPushButton:hover { background-color: #1084d6; }
            QPushButton:pressed { background-color: #006cc1; }
            QPushButton:disabled { background-color: #333; color: #888; }
            QProgressBar {
                border: none; background-color: #333; border-radius: 2px; height: 4px;
                text-align: center;
            }
            QProgressBar::chunk { background-color: #0078d4; border-radius: 2px; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)

        # Title
        title_box = QVBoxLayout()
        title_box.setSpacing(10)
        
        self.icon_label = QLabel("⚡")
        self.icon_label.setStyleSheet("font-size: 48px;")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_box.addWidget(self.icon_label)
        
        self.title_label = QLabel(f"Установка {APP_NAME}")
        self.title_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_box.addWidget(self.title_label)
        
        layout.addLayout(title_box)
        
        layout.addStretch()

        # Status
        self.status_label = QLabel("Готов к установке")
        self.status_label.setStyleSheet("color: #ccc; font-size: 13px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # Progress
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)

        layout.addStretch()

        # Button
        self.install_btn = QPushButton("Установить")
        self.install_btn.setMinimumHeight(40)
        self.install_btn.clicked.connect(self.start_install)
        layout.addWidget(self.install_btn)

    def start_install(self):
        self.install_btn.setEnabled(False)
        self.install_btn.setText("Установка...")
        
        self.worker = InstallThread()
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_progress(self, val, text):
        self.progress.setValue(val)
        self.status_label.setText(text)

    def on_finished(self, success, result):
        if success:
            self.status_label.setText("Установка завершена!")
            self.install_btn.setText("Запустить и закрыть")
            self.install_btn.setEnabled(True)
            self.target_exe = result
            self.install_btn.clicked.disconnect()
            self.install_btn.clicked.connect(self.launch_and_exit)
            
            # Auto-launch timer
            self.timer = QTimer()
            self.timer.timeout.connect(self.launch_and_exit)
            self.timer.start(3000)
            self.install_btn.setText("Запуск через 3с...")
        else:
            self.status_label.setText(f"Ошибка: {result}")
            self.install_btn.setEnabled(True)
            self.install_btn.setText("Повторить")
            QMessageBox.critical(self, "Ошибка", f"Не удалось установить:\n{result}")

    def launch_and_exit(self):
        try:
            subprocess.Popen([self.target_exe], cwd=str(Path(self.target_exe).parent))
        except:
            pass
        self.close()

if __name__ == "__main__":
    # High DPI fix
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        
    app = QApplication(sys.argv)
    
    # Try to load icon
    try:
        if hasattr(sys, '_MEIPASS'):
            icon_path = Path(sys._MEIPASS) / "app.ico"
        else:
            icon_path = Path("app.ico")
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))
    except:
        pass

    window = InstallerWindow()
    window.show()
    sys.exit(app.exec())
