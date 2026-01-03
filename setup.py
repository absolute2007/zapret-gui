
import sys
import os
import shutil
import zipfile
import subprocess
import traceback
import time
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLabel, 
                           QPushButton, QProgressBar, QMessageBox, QFrame, QCheckBox)
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
    
    def __init__(self, create_shortcut=True):
        super().__init__()
        self.create_shortcut_flag = create_shortcut

    def run(self):
        try:
            # 1. Prepare dirs
            self.progress.emit(10, "Подготовка директорий...")
            base_dir = get_base_install_dir()
            app_dir = get_app_dir()

            # Kill existing process if running
            subprocess.run("taskkill /F /IM ZapretGUI.exe", shell=True, 
                         creationflags=subprocess.CREATE_NO_WINDOW, capture_output=True)
            time.sleep(1)  # Wait for process to fully terminate
            
            # Remove existing app dir with retry
            if app_dir.exists():
                for attempt in range(3):
                    try:
                        shutil.rmtree(app_dir)
                        break
                    except PermissionError:
                        time.sleep(1)
                        if attempt == 2:
                            raise
            app_dir.mkdir(parents=True, exist_ok=True)
            
            # Create zapret dir
            zapret_dir = base_dir / "zapret"
            zapret_dir.mkdir(parents=True, exist_ok=True)

            # 2. Extract payload
            self.progress.emit(30, "Распаковка файлов...")
            
            # Look for bundled zip (added via PyInstaller datas)
            # In onefile mode, resources are in sys._MEIPASS
            if hasattr(sys, '_MEIPASS'):
                zip_path = Path(sys._MEIPASS) / "app.zip"
            else:
                zip_path = Path("app.zip") # Dev mode
                
            if not zip_path.exists():
                raise FileNotFoundError("app.zip not found in installer")

            with zipfile.ZipFile(zip_path, 'r') as z:
                # Get total size for progress
                total_size = sum(info.file_size for info in z.infolist())
                extracted_size = 0
                
                for info in z.infolist():
                    z.extract(info, app_dir)
                    extracted_size += info.file_size
                    # Progress from 30 to 90
                    pct = 30 + int((extracted_size / total_size) * 60)
                    self.progress.emit(pct, f"Распаковка: {info.filename}")

            # 3. Create Shortcut (if enabled)
            target_exe = app_dir / "ZapretGUI.exe"
            if self.create_shortcut_flag:
                self.progress.emit(90, "Создание ярлыка...")
                create_shortcut(target_exe)
            else:
                self.progress.emit(90, "Завершение...")
            
            self.progress.emit(100, "Готово!")
            self.finished.emit(True, str(target_exe))
            
        except Exception as e:
            traceback.print_exc()
            self.finished.emit(False, str(e))

def create_shortcut(target_path: Path):
    try:
        desktop = Path.home() / "Desktop"
        shortcut_path = desktop / "Zapret GUI.lnk"
        
        # Convert paths to strings with proper escaping for PowerShell
        shortcut_str = str(shortcut_path).replace("'", "''")
        target_str = str(target_path).replace("'", "''")
        workdir_str = str(target_path.parent).replace("'", "''")
        
        ps_script = f'''
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('{shortcut_str}')
$Shortcut.TargetPath = '{target_str}'
$Shortcut.WorkingDirectory = '{workdir_str}'
$Shortcut.IconLocation = '{target_str},0'
$Shortcut.Save()
'''
        # Use full path to powershell to work in PyInstaller bundle
        ps_path = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
        result = subprocess.run(
            [ps_path, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            creationflags=subprocess.CREATE_NO_WINDOW,
            capture_output=True,
            text=True
        )
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

        # Checkbox for desktop shortcut
        self.shortcut_checkbox = QCheckBox("Создать ярлык на рабочем столе")
        self.shortcut_checkbox.setChecked(True)
        self.shortcut_checkbox.setStyleSheet("color: #ccc; font-size: 13px;")
        layout.addWidget(self.shortcut_checkbox)

        # Button
        self.install_btn = QPushButton("Установить")
        self.install_btn.setMinimumHeight(40)
        self.install_btn.clicked.connect(self.start_install)
        layout.addWidget(self.install_btn)

    def start_install(self):
        self.install_btn.setEnabled(False)
        self.install_btn.setText("Установка...")
        self.shortcut_checkbox.setEnabled(False)
        
        self.worker = InstallThread(create_shortcut=self.shortcut_checkbox.isChecked())
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_progress(self, val, text):
        self.progress.setValue(val)
        self.status_label.setText(text)

    def on_finished(self, success, result):
        if success:
            self.status_label.setText("Установка завершена!")
            self.target_exe = result
            
            # Hide shortcut checkbox and show launch checkbox
            self.shortcut_checkbox.hide()
            self.launch_checkbox = QCheckBox("Запустить Zapret GUI")
            self.launch_checkbox.setChecked(True)
            self.launch_checkbox.setStyleSheet("color: #ccc; font-size: 13px;")
            self.layout().insertWidget(self.layout().indexOf(self.install_btn), self.launch_checkbox)
            
            self.install_btn.setText("Готово")
            self.install_btn.setEnabled(True)
            self.install_btn.clicked.disconnect()
            self.install_btn.clicked.connect(self.finish_install)
        else:
            self.status_label.setText(f"Ошибка: {result}")
            self.install_btn.setEnabled(True)
            self.install_btn.setText("Повторить")
            QMessageBox.critical(self, "Ошибка", f"Не удалось установить:\n{result}")

    def finish_install(self):
        if hasattr(self, 'launch_checkbox') and self.launch_checkbox.isChecked():
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
