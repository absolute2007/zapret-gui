"""
Zapret GUI v2 - Fluent Design
PyQt6 + QFluentWidgets
"""

import os
import sys
import subprocess
import threading
import socket
import time
import requests
import zipfile
import shutil
import ctypes
import re
import webbrowser
import json
import logging
import traceback
from pathlib import Path

# Setup simple file logging for startup debugging
# log_file = Path(__file__).parent / "startup.log"
# logging.basicConfig(
#     filename=str(log_file),
#     level=logging.DEBUG,
#     format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
# )

# def handle_exception(exc_type, exc_value, exc_traceback):
#     if issubclass(exc_type, KeyboardInterrupt):
#         sys.__excepthook__(exc_type, exc_value, exc_traceback)
#         return
#     logging.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

# sys.excepthook = handle_exception

# logging.info("ZapretGUI starting...")

from typing import Optional, Tuple, Dict
from packaging import version

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                              QStackedWidget, QFileDialog, QMessageBox)
from PyQt6.QtGui import QIcon

from qfluentwidgets import (NavigationInterface, NavigationItemPosition,
                            FluentWindow, SubtitleLabel, BodyLabel,
                            PushButton, PrimaryPushButton, ToggleButton,
                            TextEdit, LineEdit, ComboBox, SwitchButton,
                            CardWidget, IconWidget, ProgressBar, InfoBar,
                            InfoBarPosition, setTheme, Theme, FluentIcon,
                            NavigationAvatarWidget, isDarkTheme)

# Constants
GITHUB_REPO = "Flowseal/zapret-discord-youtube"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"
GUI_VERSION = "2.0.0"
APP_NAME = f"ZapretGUI v{GUI_VERSION}"

INSTALL_DIR_NAME = "zapret-gui"
CONFIG_FILE = "zapret_gui_config.json"


def get_base_install_dir() -> Path:
    return Path.home() / INSTALL_DIR_NAME

def get_zapret_dir() -> Path:
    return get_base_install_dir() / "zapret"

def get_app_dir() -> Path:
    return get_base_install_dir() / "app"

def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def request_admin_restart() -> bool:
    """Show notification that admin rights are needed. Returns False always."""
    if is_admin():
        return False
    
    # Just show a notification instead of dialog to avoid crashes
    # User should restart app manually as admin
    return False


def show_admin_required(parent):
    """Show InfoBar that admin rights are required."""
    InfoBar.warning(
        "Требуются права администратора",
        "Перезапустите приложение от имени администратора",
        parent=parent,
        duration=4000,
        position=InfoBarPosition.TOP
    )


class Config:
    def __init__(self, app_dir: Path):
        self.config_path = app_dir / CONFIG_FILE
        self.data = {"theme": "dark", "check_updates": True}
        self.load()

    def load(self):
        try:
            if self.config_path.exists():
                with open(self.config_path, "r") as f:
                    self.data.update(json.load(f))
        except:
            pass

    def save(self):
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w") as f:
                json.dump(self.data, f, indent=2)
        except:
            pass

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()


class Installer:
    def __init__(self):
        self.base_dir = get_base_install_dir()
        self.zapret_dir = get_zapret_dir()
        self.app_dir = get_app_dir()
        self.bin_dir = self.zapret_dir / "bin"
        self.lists_dir = self.zapret_dir / "lists"
        self.service_bat = self.zapret_dir / "service.bat"

    def check_installed(self) -> bool:
        return self.bin_dir.exists() and self.service_bat.exists()

    def get_local_version(self) -> Optional[str]:
        if not self.service_bat.exists():
            return None
        try:
            with open(self.service_bat, "r", encoding="utf-8", errors="ignore") as f:
                match = re.search(r'set\s+"LOCAL_VERSION=([^"]+)"', f.read())
                if match:
                    return match.group(1)
        except:
            pass
        return None

    def get_latest_tag(self) -> Optional[str]:
        headers = {"User-Agent": APP_NAME}
        # Try API first
        try:
            response = requests.get(GITHUB_API_URL, headers=headers, timeout=5)
            if response.status_code == 200:
                tag = response.json()["tag_name"]
                print(f"API found tag: {tag}")
                return tag
        except Exception as e:
            print(f"API check failed: {e}")
            pass
            
        # Fallback to web (follows redirects)
        try:
            # Added headers because GitHub blocks requests without User-Agent
            response = requests.get(GITHUB_RELEASES_URL, headers=headers, timeout=10)
            # URL should be .../releases/tag/v1.9.2
            if "/releases/tag/" in response.url:
                tag = response.url.split("/")[-1]
                print(f"Web found tag: {tag}")
                return tag
        except Exception as e:
            print(f"Web check failed: {e}")
            pass
            
        return None

    def check_updates(self) -> Tuple[bool, str]:
        latest = self.get_latest_tag()
        if not latest:
            return False, ""
            
        local = self.get_local_version()
        if not local:
            return True, latest
            
        try:
            return version.parse(latest.lstrip('v')) > version.parse(local.lstrip('v')), latest
        except:
            return True, latest

    def _get_release_urls(self, tag: str) -> list[str]:
        """Return list of possible download URLs in order of preference"""
        # 1. Binary release (zip) - matches user's rar pattern but zip
        # 2. Source code (zip) - fallback
        return [
            f"https://github.com/{GITHUB_REPO}/releases/download/{tag}/zapret-discord-youtube-{tag}.zip",
            f"https://github.com/{GITHUB_REPO}/archive/refs/tags/{tag}.zip"
        ]

    def download_and_install(self, progress_callback, reset: bool = False) -> bool:
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            self.zapret_dir.mkdir(parents=True, exist_ok=True)
            self.app_dir.mkdir(parents=True, exist_ok=True)

            if reset and self.zapret_dir.exists():
                progress_callback("Удаление старых файлов...", 10)
                try:
                    for item in self.zapret_dir.iterdir():
                        if item.is_dir():
                            shutil.rmtree(item)
                        else:
                            item.unlink()
                except Exception as e:
                    print(f"Error cleaning dir: {e}")

            progress_callback("Получение информации о релизе...", 20)
            tag = self.get_latest_tag()
            if not tag:
                progress_callback("Ошибка: Не удалось найти релиз (проверьте интернет)", 0)
                return False

            progress_callback(f"Скачивание версии {tag}...", 30)
            headers = {"User-Agent": APP_NAME}
            
            # Try URLs in order
            urls = self._get_release_urls(tag)
            success = False
            temp_zip = self.base_dir / "zapret_download.zip"

            for url in urls:
                try:
                    print(f"Trying url: {url}")
                    r = requests.get(url, headers=headers, stream=True, timeout=120)
                    if r.status_code == 200:
                        with open(temp_zip, "wb") as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                f.write(chunk)
                        success = True
                        break
                    else:
                        print(f"URL failed with status {r.status_code}: {url}")
                except Exception as e:
                    print(f"URL download error: {e}")
            
            if not success:
               progress_callback("Ошибка: Не удалось скачать файл релиза (404/Connection Error)", 0)
               return False

            progress_callback("Распаковка...", 60)
            extract_dir = self.base_dir / "temp_extract"
            if extract_dir.exists():
                shutil.rmtree(extract_dir)
            extract_dir.mkdir()

            try:
                with zipfile.ZipFile(temp_zip, 'r') as z:
                    z.extractall(extract_dir)
            except zipfile.BadZipFile:
                 progress_callback("Ошибка: Скачанный файл поврежден или не является zip архивом", 0)
                 return False

            contents = list(extract_dir.iterdir())
            source_dir = contents[0] if len(contents) == 1 and contents[0].is_dir() else extract_dir

            progress_callback("Установка файлов...", 80)
            for item in source_dir.iterdir():
                if item.name in ["gui", ".git", ".github"]:
                    continue
                dest = self.zapret_dir / item.name
                if dest.exists():
                    if dest.is_dir():
                        shutil.rmtree(dest)
                    else:
                        dest.unlink()
                shutil.move(str(item), str(dest))

            shutil.rmtree(extract_dir)
            if temp_zip.exists():
                temp_zip.unlink()

            progress_callback("Готово!", 100)
            return True
        except Exception as e:
            progress_callback(f"Ошибка: {str(e)[:50]}", 0)
            return False


class ServiceManager:
    @staticmethod
    def stop_service():
        subprocess.run("net stop zapret", shell=True, capture_output=True,
                      creationflags=subprocess.CREATE_NO_WINDOW)
        subprocess.run("taskkill /F /IM winws.exe", shell=True, capture_output=True,
                      creationflags=subprocess.CREATE_NO_WINDOW)
        time.sleep(0.5)

    @staticmethod
    def remove_service():
        ServiceManager.stop_service()
        subprocess.run("sc delete zapret", shell=True, capture_output=True,
                      creationflags=subprocess.CREATE_NO_WINDOW)
        subprocess.run("sc delete WinDivert", shell=True, capture_output=True,
                      creationflags=subprocess.CREATE_NO_WINDOW)
        subprocess.run("sc delete WinDivert14", shell=True, capture_output=True,
                      creationflags=subprocess.CREATE_NO_WINDOW)

    @staticmethod
    def install_service(strategy_path: Path, app_dir: Path) -> Tuple[bool, str]:
        try:
            with open(strategy_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            game_filter_file = app_dir / "utils" / "game_filter.enabled"
            game_filter = "1024-65535" if game_filter_file.exists() else "12"

            lines = content.split('\n')
            args_parts = []
            capturing = False

            for line in lines:
                line = line.strip()
                if 'winws.exe' in line.lower():
                    capturing = True
                    idx = line.lower().find('winws.exe')
                    rest = line[idx + len('winws.exe'):]
                    rest = rest.lstrip('"').strip()
                    if rest and rest != '^':
                        args_parts.append(rest.rstrip('^').strip())
                elif capturing:
                    if line.startswith('start ') or line.startswith('::') or line.startswith('rem ') or not line:
                        break
                    args_parts.append(line.rstrip('^').strip())

            args = ' '.join(args_parts)
            bin_path = str(app_dir / "bin")
            lists_path = str(app_dir / "lists")

            args = args.replace('%BIN%', bin_path + '\\')
            args = args.replace('%LISTS%', lists_path + '\\')
            args = args.replace('%~dp0', str(app_dir) + '\\')
            args = args.replace('%GameFilter%', game_filter)
            args = args.replace('^!', '!')
            args = re.sub(r'\s+', ' ', args)

            winws_path = app_dir / "bin" / "winws.exe"
            ServiceManager.remove_service()
            time.sleep(0.5)

            subprocess.run("netsh interface tcp set global timestamps=enabled",
                          shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)

            bin_path_quoted = f'"{winws_path}"'
            cmd = f'sc create zapret binPath= "{bin_path_quoted} {args}" DisplayName= "zapret" start= auto'
            result = subprocess.run(cmd, shell=True, capture_output=True,
                                   creationflags=subprocess.CREATE_NO_WINDOW)

            if result.returncode != 0:
                return False, f"sc create failed"

            subprocess.run('sc description zapret "Zapret DPI bypass"',
                          shell=True, creationflags=subprocess.CREATE_NO_WINDOW)

            subprocess.run("sc start zapret", shell=True, capture_output=True,
                          creationflags=subprocess.CREATE_NO_WINDOW)

            strat_name = strategy_path.stem
            subprocess.run(f'reg add "HKLM\\System\\CurrentControlSet\\Services\\zapret" /v zapret-discord-youtube /t REG_SZ /d "{strat_name}" /f',
                          shell=True, creationflags=subprocess.CREATE_NO_WINDOW)

            return True, "Служба установлена"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def get_status() -> Dict[str, Tuple[str, bool]]:
        res = {}
        try:
            o = subprocess.check_output('tasklist /FI "IMAGENAME eq winws.exe"',
                                       creationflags=subprocess.CREATE_NO_WINDOW).decode('cp866', errors='ignore')
            res["winws"] = ("РАБОТАЕТ", True) if "winws.exe" in o else ("ОСТАНОВЛЕН", False)
        except:
            res["winws"] = ("НЕИЗВЕСТНО", False)

        try:
            o = subprocess.check_output("sc query zapret",
                                       creationflags=subprocess.CREATE_NO_WINDOW).decode('cp866', errors='ignore')
            if "RUNNING" in o:
                res["zapret"] = ("ЗАПУЩЕНА", True)
            elif "STOPPED" in o:
                res["zapret"] = ("ОСТАНОВЛЕНА", False)
            else:
                res["zapret"] = ("НЕ УСТАНОВЛЕНА", False)
        except:
            res["zapret"] = ("НЕ УСТАНОВЛЕНА", False)

        try:
            o = subprocess.check_output("sc query WinDivert",
                                       creationflags=subprocess.CREATE_NO_WINDOW).decode('cp866', errors='ignore')
            res["windivert"] = ("ЗАГРУЖЕН", True) if "RUNNING" in o else ("ВЫГРУЖЕН", False)
        except:
            res["windivert"] = ("НЕ НАЙДЕН", False)

        return res


class InstallWorker(QThread):
    progress = pyqtSignal(str, int)
    finished = pyqtSignal(bool)

    def __init__(self, installer, reset=False):
        super().__init__()
        self.installer = installer
        self.reset = reset

    def run(self):
        def callback(text, val):
            self.progress.emit(text, val)
        result = self.installer.download_and_install(callback, self.reset)
        self.finished.emit(result)


class StatusWorker(QThread):
    result = pyqtSignal(dict, list, list, str)  # status, strategies, lists, version

    def __init__(self, zapret_dir, lists_dir):
        super().__init__()
        self.zapret_dir = zapret_dir
        self.lists_dir = lists_dir

    def run(self):
        status = ServiceManager.get_status()
        strategies = []
        lists = []
        version = "неизвестна"
        
        # Find strategy files - look for all .bat files that look like strategies
        try:
            if self.zapret_dir.exists():
                all_bats = list(self.zapret_dir.glob("*.bat"))
                # Filter out service/utility scripts
                excluded = {"service.bat", "uninstall.bat", "install.bat", "start.bat", "stop.bat"}
                strategies = sorted([f.name for f in all_bats 
                                    if f.name.lower() not in excluded])
        except Exception as e:
            print(f"Strategy search error: {e}")
        
        # Find list files
        try:
            if self.lists_dir.exists():
                lists = sorted([f.name for f in self.lists_dir.glob("*.txt")])
        except Exception as e:
            print(f"Lists search error: {e}")

        # Get version
        try:
            # 1. Try to get from GitHub API (Most reliable for "latest release")
            try:
                if not version or version == "неизвестна":
                    import requests
                    # Try API first
                    try:
                        headers = {"User-Agent": "ZapretGUI"}
                        resp = requests.get("https://api.github.com/repos/Flowseal/zapret-discord-youtube/releases/latest", headers=headers, timeout=3)
                        if resp.status_code == 200:
                            data = resp.json()
                            version = data.get("tag_name", "неизвестна")
                    except:
                        pass
                        
                    # Fallback to web if API failed
                    if not version or version == "неизвестна":
                        try:
                            resp = requests.get("https://github.com/Flowseal/zapret-discord-youtube/releases/latest", timeout=5)
                            if "/releases/tag/" in resp.url:
                                version = resp.url.split("/")[-1]
                        except:
                            pass
            except:
                pass

            # 2. If API failed, try local README
            if version == "неизвестна":
                readme_path = self.zapret_dir / "README.md"
                if readme_path.exists():
                    content = readme_path.read_text(encoding="utf-8", errors="ignore")
                    # Look for version patterns like "v1.2.3" or "Ver 1.2"
                    import re
                    # Try getting first version-like string
                    match = re.search(r"tag: v?(\d+\.\d+(\.\d+)?)", content)
                    if not match:
                        match = re.search(r"zapret-discord-youtube v?(\d+\.\d+)", content)
                    
                    if match:
                        version = match.group(1)
        except:
            pass
            
        self.result.emit(status, strategies, lists, version)


# ========== UI Pages ==========

class ListsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lists_dir = None
        self.current_file = "list-general.txt"
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Header card
        header_card = CardWidget()
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(20, 15, 20, 15)

        # Icon and title
        icon_label = BodyLabel("📝")
        icon_label.setStyleSheet("font-size: 24px;")
        header_layout.addWidget(icon_label)

        title_layout = QVBoxLayout()
        title_layout.addWidget(SubtitleLabel("Редактор списков"))
        file_hint = BodyLabel("Выберите файл для редактирования")
        file_hint.setStyleSheet("color: #888;")
        title_layout.addWidget(file_hint)
        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        # File selector
        self.file_combo = ComboBox()
        self.file_combo.setMinimumWidth(280)
        self.file_combo.currentTextChanged.connect(self._load_file)
        header_layout.addWidget(self.file_combo)

        layout.addWidget(header_card)

        # Buttons row
        btn_row = QHBoxLayout()

        self.import_btn = PushButton("📥 Импорт")
        self.import_btn.setStyleSheet("padding: 8px 16px;")
        self.import_btn.clicked.connect(self._import_list)
        btn_row.addWidget(self.import_btn)

        self.save_btn = PrimaryPushButton("💾 Сохранить")
        self.save_btn.setStyleSheet("padding: 8px 16px; background-color: #107c10;")
        self.save_btn.clicked.connect(self._save_list)
        btn_row.addWidget(self.save_btn)

        btn_row.addStretch()

        # Stats label
        self.stats_label = BodyLabel("0 доменов")
        self.stats_label.setStyleSheet("color: #888;")
        btn_row.addWidget(self.stats_label)

        layout.addLayout(btn_row)

        # Editor
        self.editor = TextEdit()
        self.editor.setPlaceholderText("Один домен на строку...\n\nПример:\ndiscord.com\nyoutube.com")
        self.editor.setStyleSheet("font-family: Consolas, monospace; font-size: 13px;")
        self.editor.textChanged.connect(self._update_stats)
        layout.addWidget(self.editor)

        # Hint card
        hint_card = CardWidget()
        hint_layout = QHBoxLayout(hint_card)
        hint_layout.setContentsMargins(15, 10, 15, 10)
        hint_icon = BodyLabel("💡")
        hint_layout.addWidget(hint_icon)
        hint_text = BodyLabel("Один домен на строку. Строки с # в начале — комментарии.")
        hint_text.setStyleSheet("color: #888;")
        hint_layout.addWidget(hint_text)
        hint_layout.addStretch()
        layout.addWidget(hint_card)

    def _update_stats(self):
        text = self.editor.toPlainText()
        lines = [l.strip() for l in text.split('\n') if l.strip() and not l.startswith('#')]
        self.stats_label.setText(f"{len(lines)} доменов")

    def set_lists_dir(self, path):
        self.lists_dir = path

    def update_lists(self, lists):
        current = self.file_combo.currentText()
        self.file_combo.clear()
        self.file_combo.addItems(lists)
        if current in lists:
            self.file_combo.setCurrentText(current)
        elif lists:
            self.file_combo.setCurrentIndex(0)

    def _load_file(self, filename):
        if not filename or not self.lists_dir:
            return
        self.current_file = filename
        path = self.lists_dir / filename
        if path.exists():
            try:
                self.editor.setPlainText(path.read_text(encoding="utf-8", errors="ignore"))
            except:
                pass

    def _save_list(self):
        if not self.lists_dir:
            return
        try:
            path = self.lists_dir / self.current_file
            path.write_text(self.editor.toPlainText(), encoding="utf-8")
            InfoBar.success("Сохранено", f"{self.current_file}", parent=self,
                           position=InfoBarPosition.TOP_RIGHT, duration=2000)
        except Exception as e:
            InfoBar.error("Ошибка", str(e), parent=self)

    def _import_list(self):
        path, _ = QFileDialog.getOpenFileName(self, "Импорт списка", "",
                                               "Text Files (*.txt);;All Files (*)")
        if not path:
            return
        try:
            new = set(l.strip().lower() for l in Path(path).read_text(errors='ignore').split('\n')
                     if l.strip() and not l.startswith('#'))
            current = set(l.strip().lower() for l in self.editor.toPlainText().split('\n')
                         if l.strip())
            to_add = new - current
            if to_add:
                txt = self.editor.toPlainText().rstrip() + '\n' + '\n'.join(to_add) + '\n'
                self.editor.setPlainText(txt)
                InfoBar.success("Импорт", f"Добавлено {len(to_add)} доменов", parent=self,
                               position=InfoBarPosition.TOP_RIGHT, duration=2000)
            else:
                InfoBar.info("Импорт", "Все домены уже есть", parent=self)
        except Exception as e:
            InfoBar.error("Ошибка", str(e), parent=self)


class StrategiesPage(QWidget):
    refresh_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.zapret_dir = None
        self.strategies = []
        self.is_running = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Status card at top
        status_card = CardWidget()
        status_layout = QHBoxLayout(status_card)
        status_layout.setContentsMargins(20, 15, 20, 15)

        status_left = QVBoxLayout()
        status_left.addWidget(SubtitleLabel("Состояние winws.exe"))
        self.status_label = BodyLabel("Проверка...")
        status_left.addWidget(self.status_label)
        status_layout.addLayout(status_left)
        status_layout.addStretch()

        # Status indicator (colored dot)
        self.status_indicator = BodyLabel("●")
        self.status_indicator.setStyleSheet("font-size: 24px; color: gray;")
        status_layout.addWidget(self.status_indicator)

        self.stop_btn = PushButton("Остановить")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_winws)
        status_layout.addWidget(self.stop_btn)

        layout.addWidget(status_card)

        # Hint
        hint = BodyLabel("Выберите стратегию для запуска обхода DPI:")
        hint.setStyleSheet("color: #888; font-size: 13px;")
        layout.addWidget(hint)

        # Strategies container with scroll
        from qfluentwidgets import ScrollArea
        scroll = ScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("ScrollArea { border: none; background: transparent; }")

        self.strat_container = QWidget()
        self.strat_layout = QVBoxLayout(self.strat_container)
        self.strat_layout.setSpacing(8)
        self.strat_layout.setContentsMargins(0, 0, 0, 0)
        self.strat_layout.addStretch()

        scroll.setWidget(self.strat_container)
        layout.addWidget(scroll)

    def set_zapret_dir(self, path):
        self.zapret_dir = path

    def update_status(self, status: dict):
        winws_status = status.get("winws", ("НЕИЗВЕСТНО", False))
        text, running = winws_status
        self.is_running = running

        if running:
            self.status_label.setText("Запущен и работает")
            self.status_label.setStyleSheet("color: #6ccb5f;")
            self.status_indicator.setStyleSheet("font-size: 24px; color: #6ccb5f;")
            self.stop_btn.setEnabled(True)
            self.stop_btn.setStyleSheet("background-color: #c42b1c;")
        else:
            self.status_label.setText("Не запущен")
            self.status_label.setStyleSheet("color: #c42b1c;")
            self.status_indicator.setStyleSheet("font-size: 24px; color: #c42b1c;")
            self.stop_btn.setEnabled(False)
            self.stop_btn.setStyleSheet("background-color: #555;")

    def update_strategies(self, strategies):
        self.strategies = strategies

        # Clear old widgets
        while self.strat_layout.count() > 1:  # Keep stretch
            item = self.strat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not strategies:
            no_strat = BodyLabel("Стратегии не найдены. Установите Zapret.")
            no_strat.setStyleSheet("color: #888; padding: 20px;")
            self.strat_layout.insertWidget(0, no_strat)
            return

        # Add strategy cards with colors
        colors = ["#0078d4", "#107c10", "#5c2d91", "#e81123", "#ff8c00", "#00b7c3"]

        for i, name in enumerate(strategies):
            card = CardWidget()
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(15, 15, 15, 15)

            # Color indicator
            color = colors[i % len(colors)]
            color_dot = BodyLabel("●")
            color_dot.setStyleSheet(f"font-size: 16px; color: {color};")
            card_layout.addWidget(color_dot)

            # Strategy name
            label = SubtitleLabel(name.replace(".bat", ""))
            label.setStyleSheet("font-size: 15px;")
            card_layout.addWidget(label)
            card_layout.addStretch()

            # Run button
            btn = PrimaryPushButton("▶ Запустить")
            btn.setStyleSheet(f"background-color: {color};")
            btn.clicked.connect(lambda checked, n=name: self._run_strategy(n))
            card_layout.addWidget(btn)

            self.strat_layout.insertWidget(i, card)

    def _run_strategy(self, name):
        if not self.zapret_dir:
            InfoBar.error("Ошибка", "Директория не найдена", parent=self)
            return
        p = self.zapret_dir / name
        if not p.exists():
            InfoBar.error("Ошибка", f"Файл не найден: {name}", parent=self)
            return
        if is_admin():
            subprocess.Popen(str(p), cwd=str(self.zapret_dir),
                           creationflags=subprocess.CREATE_NEW_CONSOLE, shell=True)
            InfoBar.success("Запущено", name, parent=self,
                           position=InfoBarPosition.TOP_RIGHT, duration=2000)
        else:
            ctypes.windll.shell32.ShellExecuteW(None, "runas", str(p), None, str(self.zapret_dir), 1)
        # Request status refresh after a delay
        QTimer.singleShot(2000, lambda: self.refresh_requested.emit())

    def _stop_winws(self):
        subprocess.run("taskkill /F /IM winws.exe", shell=True,
                      creationflags=subprocess.CREATE_NO_WINDOW)
        InfoBar.success("Остановлено", "winws.exe", parent=self,
                       position=InfoBarPosition.TOP_RIGHT, duration=2000)
        self.refresh_requested.emit()


class AutorunPage(QWidget):
    refresh_requested = pyqtSignal()
    _install_done = pyqtSignal(bool, str)  # Internal signal for thread completion

    def __init__(self, parent=None):
        super().__init__(parent)
        self.zapret_dir = None
        self.strategies = []
        self._install_done.connect(self._on_install_done)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Info card
        info_card = CardWidget()
        info_layout = QHBoxLayout(info_card)
        info_layout.setContentsMargins(20, 18, 20, 18)

        icon = BodyLabel("⚡")
        icon.setStyleSheet("font-size: 28px;")
        info_layout.addWidget(icon)

        text_layout = QVBoxLayout()
        text_layout.addWidget(SubtitleLabel("Установка службы Windows"))
        text_layout.addWidget(BodyLabel("Zapret будет запускаться автоматически при включении ПК"))
        info_layout.addLayout(text_layout)
        info_layout.addStretch()

        layout.addWidget(info_card)

        # Strategy selection
        strat_card = CardWidget()
        strat_layout = QVBoxLayout(strat_card)
        strat_layout.setContentsMargins(20, 15, 20, 15)
        strat_layout.setSpacing(10)

        strat_layout.addWidget(SubtitleLabel("Выберите стратегию:"))

        self.strat_combo = ComboBox()
        self.strat_combo.setMinimumWidth(400)
        strat_layout.addWidget(self.strat_combo)

        btn_row = QHBoxLayout()
        self.install_btn = PrimaryPushButton("⚡ Установить службу")
        self.install_btn.clicked.connect(self._install_service)
        btn_row.addWidget(self.install_btn)

        self.stop_btn = PushButton("⏹ Остановить")
        self.stop_btn.clicked.connect(self._stop_service)
        btn_row.addWidget(self.stop_btn)

        self.remove_btn = PushButton("🗑 Удалить")
        self.remove_btn.setStyleSheet("background-color: #c42b1c;")
        self.remove_btn.clicked.connect(self._remove_service)
        btn_row.addWidget(self.remove_btn)

        btn_row.addStretch()
        strat_layout.addLayout(btn_row)

        layout.addWidget(strat_card)
        layout.addStretch()

    def set_zapret_dir(self, path):
        self.zapret_dir = path

    def update_strategies(self, strategies):
        self.strategies = strategies
        current = self.strat_combo.currentText()
        self.strat_combo.clear()
        self.strat_combo.addItems(strategies)
        if current in strategies:
            self.strat_combo.setCurrentText(current)
        elif strategies:
            self.strat_combo.setCurrentIndex(0)

    def _install_service(self):
        strat = self.strat_combo.currentText()
        if not strat or not self.zapret_dir:
            InfoBar.warning("Внимание", "Выберите стратегию", parent=self)
            return

        self.install_btn.setEnabled(False)
        self.install_btn.setText("Установка...")

        def do_install():
            strat_path = self.zapret_dir / strat
            success, msg = ServiceManager.install_service(strat_path, self.zapret_dir)
            self._install_done.emit(success, msg)

        import threading
        threading.Thread(target=do_install, daemon=True).start()

    def _on_install_done(self, success, msg):
        self.install_btn.setEnabled(True)
        self.install_btn.setText("⚡ Установить службу")
        if success:
            InfoBar.success("Успешно", "Служба установлена и запущена", parent=self,
                           position=InfoBarPosition.TOP_RIGHT, duration=3000)
        else:
            InfoBar.error("Ошибка", msg, parent=self,
                         position=InfoBarPosition.TOP_RIGHT, duration=5000)
        self.refresh_requested.emit()

    def _stop_service(self):
        ServiceManager.stop_service()
        InfoBar.success("Остановлено", "Служба остановлена", parent=self, duration=2000)
        self.refresh_requested.emit()

    def _remove_service(self):
        ServiceManager.remove_service()
        InfoBar.success("Удалено", "Служба удалена", parent=self, duration=2000)
        self.refresh_requested.emit()


class OptionsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.zapret_dir = None
        self.utils_dir = None
        self.lists_dir = None
        self.game_filter_enabled = False
        self.ipset_status = "any"
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Game Filter card
        gf_card = CardWidget()
        gf_layout = QHBoxLayout(gf_card)
        gf_layout.setContentsMargins(20, 18, 20, 18)

        gf_icon = BodyLabel("🎮")
        gf_icon.setStyleSheet("font-size: 28px;")
        gf_layout.addWidget(gf_icon)

        gf_text = QVBoxLayout()
        gf_text.addWidget(SubtitleLabel("Game Filter"))
        gf_desc = BodyLabel("Расширяет диапазон портов для игр (1024-65535)")
        gf_desc.setStyleSheet("color: #888;")
        gf_text.addWidget(gf_desc)
        gf_layout.addLayout(gf_text)
        gf_layout.addStretch()

        self.gf_switch = SwitchButton()
        self.gf_switch.checkedChanged.connect(self._toggle_game_filter)
        gf_layout.addWidget(self.gf_switch)

        layout.addWidget(gf_card)

        # IPset card
        ip_card = CardWidget()
        ip_layout = QHBoxLayout(ip_card)
        ip_layout.setContentsMargins(20, 18, 20, 18)

        ip_icon = BodyLabel("🌐")
        ip_icon.setStyleSheet("font-size: 28px;")
        ip_layout.addWidget(ip_icon)

        ip_text = QVBoxLayout()
        ip_text.addWidget(SubtitleLabel("IPset"))
        self.ipset_label = BodyLabel("Режим: загрузка...")
        self.ipset_label.setStyleSheet("color: #888;")
        ip_text.addWidget(self.ipset_label)
        ip_layout.addLayout(ip_text)
        ip_layout.addStretch()

        self.toggle_ip_btn = PushButton("🔄 Переключить")
        self.toggle_ip_btn.clicked.connect(self._toggle_ipset)
        ip_layout.addWidget(self.toggle_ip_btn)

        self.update_ip_btn = PrimaryPushButton("⬇ Обновить")
        self.update_ip_btn.setStyleSheet("background-color: #0078d4;")
        self.update_ip_btn.clicked.connect(self._update_ipset)
        ip_layout.addWidget(self.update_ip_btn)

        layout.addWidget(ip_card)

        # Hosts card
        hosts_card = CardWidget()
        hosts_layout = QHBoxLayout(hosts_card)
        hosts_layout.setContentsMargins(20, 18, 20, 18)

        hosts_icon = BodyLabel("💬")
        hosts_icon.setStyleSheet("font-size: 28px;")
        hosts_layout.addWidget(hosts_icon)

        hosts_text = QVBoxLayout()
        hosts_text.addWidget(SubtitleLabel("Discord Hosts"))
        hosts_layout.addWidget(BodyLabel("Обновить hosts файл для голосовых серверов Discord"))

        self.hosts_btn = PushButton("Обновить hosts")
        self.hosts_btn.clicked.connect(self._update_hosts)
        hosts_layout.addWidget(self.hosts_btn)

        layout.addWidget(hosts_card)
        layout.addStretch()

    def set_dirs(self, zapret_dir, utils_dir, lists_dir):
        self.zapret_dir = zapret_dir
        self.utils_dir = utils_dir
        self.lists_dir = lists_dir
        self._load_state()

    def _load_state(self):
        if self.utils_dir:
            gf = self.utils_dir / "game_filter.enabled"
            self.game_filter_enabled = gf.exists()
            self.gf_switch.setChecked(self.game_filter_enabled)

        if self.lists_dir:
            ipset_file = self.lists_dir / "ipset-all.txt"
            if ipset_file.exists():
                try:
                    content = ipset_file.read_text(errors='ignore').strip()
                    if not content:
                        self.ipset_status = "any"
                    elif "203.0.113.113/32" in content:
                        self.ipset_status = "none"
                    else:
                        self.ipset_status = "loaded"
                except:
                    self.ipset_status = "any"
        self.ipset_label.setText(f"Текущий режим: {self.ipset_status.upper()}")

    def _toggle_game_filter(self, checked):
        if not self.utils_dir:
            return
        self.utils_dir.mkdir(exist_ok=True)
        gf_file = self.utils_dir / "game_filter.enabled"

        if checked:
            gf_file.write_text("ENABLED")
            InfoBar.success("Game Filter", "Включен. Перезапустите Zapret.", parent=self, duration=3000)
        else:
            if gf_file.exists():
                gf_file.unlink()
            InfoBar.info("Game Filter", "Отключен. Перезапустите Zapret.", parent=self, duration=3000)

    def _toggle_ipset(self):
        if not self.lists_dir:
            return
        ipset_file = self.lists_dir / "ipset-all.txt"
        backup_file = self.lists_dir / "ipset-all.txt.backup"

        if self.ipset_status == "loaded":
            if backup_file.exists():
                backup_file.unlink()
            if ipset_file.exists():
                ipset_file.rename(backup_file)
            ipset_file.write_text("203.0.113.113/32\n")
            self.ipset_status = "none"
        elif self.ipset_status == "none":
            ipset_file.write_text("")
            self.ipset_status = "any"
        else:
            if backup_file.exists():
                if ipset_file.exists():
                    ipset_file.unlink()
                backup_file.rename(ipset_file)
                self.ipset_status = "loaded"
            else:
                InfoBar.warning("Внимание", "Нет бэкапа. Обновите список.", parent=self)
                return

        self.ipset_label.setText(f"Текущий режим: {self.ipset_status.upper()}")
        InfoBar.success("IPset", f"Режим: {self.ipset_status}. Перезапустите Zapret.", parent=self, duration=3000)

    def _update_ipset(self):
        def do_update():
            try:
                url = "https://raw.githubusercontent.com/Flowseal/zapret-discord-youtube/refs/heads/main/.service/ipset-service.txt"
                r = requests.get(url, timeout=15)
                r.raise_for_status()
                (self.lists_dir / "ipset-all.txt").write_text(r.text)
                self.ipset_status = "loaded"
                QTimer.singleShot(0, lambda: self.ipset_label.setText("Текущий режим: LOADED"))
                QTimer.singleShot(0, lambda: InfoBar.success("IPset", "Обновлен", parent=self, duration=2000))
            except Exception as e:
                QTimer.singleShot(0, lambda: InfoBar.error("Ошибка", str(e), parent=self))

        import threading
        threading.Thread(target=do_update, daemon=True).start()
        InfoBar.info("IPset", "Обновление...", parent=self, duration=1500)

    def _update_hosts(self):
        if not is_admin():
            request_admin_restart()
            return

        def do_update():
            try:
                url = "https://raw.githubusercontent.com/Flowseal/zapret-discord-youtube/refs/heads/main/.service/discord-hosts.txt"
                r = requests.get(url, timeout=15)
                r.raise_for_status()

                hosts_path = Path(os.environ.get('SystemRoot', 'C:\\Windows')) / "System32" / "drivers" / "etc" / "hosts"
                new_entries = r.text.strip()
                current = hosts_path.read_text(errors='ignore') if hosts_path.exists() else ""

                if new_entries not in current:
                    with open(hosts_path, "a") as f:
                        f.write("\n# Discord Voice (zapret-gui)\n" + new_entries + "\n")
                    QTimer.singleShot(0, lambda: InfoBar.success("Hosts", "Обновлен", parent=self, duration=2000))
                else:
                    QTimer.singleShot(0, lambda: InfoBar.info("Hosts", "Уже содержит записи", parent=self, duration=2000))
            except Exception as e:
                QTimer.singleShot(0, lambda: InfoBar.error("Ошибка", str(e), parent=self))

        import threading
        threading.Thread(target=do_update, daemon=True).start()


class TestWorker(QThread):
    result = pyqtSignal(str)
    
    def __init__(self, domain):
        super().__init__()
        self.domain = domain
        
    def run(self):
        results = []
        try:
            t = time.time()
            ip = socket.gethostbyname(self.domain)
            results.append(f"✓ DNS: {ip} ({int((time.time()-t)*1000)}ms)")
        except Exception as e:
            results.append(f"✗ DNS: {e}")

        try:
            t = time.time()
            r = requests.get(f"https://{self.domain}", timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            results.append(f"✓ HTTPS: {r.status_code} ({int((time.time()-t)*1000)}ms)")
        except Exception as e:
            results.append(f"✗ HTTPS: {e}")
            
        self.result.emit("\n".join(results))

class TestPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Input
        input_row = QHBoxLayout()
        self.input = LineEdit()
        self.input.setPlaceholderText("discord.com")
        self.input.returnPressed.connect(self._run_test)
        input_row.addWidget(self.input)

        self.test_btn = PrimaryPushButton("Проверить")
        self.test_btn.clicked.connect(self._run_test)
        input_row.addWidget(self.test_btn)

        layout.addLayout(input_row)

        # Results
        self.results = TextEdit()
        self.results.setReadOnly(True)
        self.results.setPlaceholderText("Результаты проверки появятся здесь...")
        layout.addWidget(self.results)

    def _run_test(self):
        domain = self.input.text().strip().replace("https://", "").replace("http://", "").split("/")[0]
        if not domain:
            domain = "discord.com"
            self.input.setText(domain)

        self.results.clear()
        self.results.append(f"Проверка {domain}...\n")
        self.test_btn.setEnabled(False)
        
        self.worker = TestWorker(domain)
        self.worker.result.connect(self._on_result)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()
        
    def _on_result(self, text):
        self.results.append(text)
        
    def _on_finished(self):
        self.test_btn.setEnabled(True)


class StatusPage(QWidget):
    refresh_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # Status cards
        self.status_widgets = {}

        # winws.exe
        card1 = CardWidget()
        card1_layout = QHBoxLayout(card1)
        card1_layout.setContentsMargins(20, 15, 20, 15)

        left1 = QVBoxLayout()
        left1.addWidget(SubtitleLabel("winws.exe"))
        left1.addWidget(BodyLabel("Процесс обхода DPI"))
        card1_layout.addLayout(left1)
        card1_layout.addStretch()

        self.status_widgets["winws"] = BodyLabel("...")
        card1_layout.addWidget(self.status_widgets["winws"])

        stop_btn = PushButton("Остановить")
        stop_btn.setStyleSheet("background-color: #c42b1c;")
        stop_btn.clicked.connect(self._stop_winws)
        card1_layout.addWidget(stop_btn)

        layout.addWidget(card1)

        # zapret service
        card2 = CardWidget()
        card2_layout = QHBoxLayout(card2)
        card2_layout.setContentsMargins(20, 15, 20, 15)

        left2 = QVBoxLayout()
        left2.addWidget(SubtitleLabel("Служба zapret"))
        left2.addWidget(BodyLabel("Автозапуск Windows"))
        card2_layout.addLayout(left2)
        card2_layout.addStretch()

        self.status_widgets["zapret"] = BodyLabel("...")
        card2_layout.addWidget(self.status_widgets["zapret"])

        stop_svc_btn = PushButton("Стоп")
        stop_svc_btn.clicked.connect(self._stop_service)
        card2_layout.addWidget(stop_svc_btn)

        del_svc_btn = PushButton("Удалить")
        del_svc_btn.setStyleSheet("background-color: #c42b1c;")
        del_svc_btn.clicked.connect(self._remove_service)
        card2_layout.addWidget(del_svc_btn)

        layout.addWidget(card2)

        # WinDivert
        card3 = CardWidget()
        card3_layout = QHBoxLayout(card3)
        card3_layout.setContentsMargins(20, 15, 20, 15)

        left3 = QVBoxLayout()
        left3.addWidget(SubtitleLabel("WinDivert"))
        left3.addWidget(BodyLabel("Сетевой драйвер"))
        card3_layout.addLayout(left3)
        card3_layout.addStretch()

        self.status_widgets["windivert"] = BodyLabel("...")
        card3_layout.addWidget(self.status_widgets["windivert"])

        del_wd_btn = PushButton("Удалить")
        del_wd_btn.setStyleSheet("background-color: #c42b1c;")
        del_wd_btn.clicked.connect(self._remove_windivert)
        card3_layout.addWidget(del_wd_btn)

        layout.addWidget(card3)

        # Version info card
        ver_card = CardWidget()
        ver_layout = QHBoxLayout(ver_card)
        ver_layout.setContentsMargins(20, 15, 20, 15)

        ver_icon = BodyLabel("📦")
        ver_icon.setStyleSheet("font-size: 20px;")
        ver_layout.addWidget(ver_icon)

        ver_text = QVBoxLayout()
        ver_text.addWidget(SubtitleLabel("Версия Zapret"))
        self.version_label = BodyLabel("Загрузка...")
        self.version_label.setStyleSheet("color: #888;")
        ver_text.addWidget(self.version_label)
        ver_layout.addLayout(ver_text)
        ver_layout.addStretch()

        layout.addWidget(ver_card)

        # Buttons row
        btn_row = QHBoxLayout()
        
        refresh_btn = PrimaryPushButton("🔄 Обновить статус")
        refresh_btn.clicked.connect(lambda: self.refresh_requested.emit())
        btn_row.addWidget(refresh_btn)

        btn_row.addStretch()

        layout.addLayout(btn_row)

        # GitHub links row
        github_row = QHBoxLayout()
        
        zapret_btn = PushButton("📂 GitHub: zapret-discord-youtube")
        zapret_btn.clicked.connect(lambda: webbrowser.open("https://github.com/Flowseal/zapret-discord-youtube"))
        github_row.addWidget(zapret_btn)

        gui_btn = PushButton("💻 GitHub: zapret-gui")
        gui_btn.clicked.connect(lambda: webbrowser.open("https://github.com/absolute2007/zapret-gui"))
        github_row.addWidget(gui_btn)

        github_row.addStretch()
        layout.addLayout(github_row)

        layout.addStretch()

    def set_version(self, version: str):
        self.version_label.setText(f"v{version}")

    def update_status(self, status: dict):
        for key, (text, running) in status.items():
            if key in self.status_widgets:
                color = "#6ccb5f" if running else "#c42b1c"
                icon = "✓" if running else "✗"
                self.status_widgets[key].setText(f"{icon} {text}")
                self.status_widgets[key].setStyleSheet(f"color: {color};")

    def _stop_winws(self):
        subprocess.run("taskkill /F /IM winws.exe", shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        self.refresh_requested.emit()

    def _stop_service(self):
        if not is_admin():
            request_admin_restart()
            return
        ServiceManager.stop_service()
        self.refresh_requested.emit()

    def _remove_service(self):
        if not is_admin():
            request_admin_restart()
            return
        subprocess.run("net stop zapret", shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        subprocess.run("sc delete zapret", shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        self.refresh_requested.emit()

    def _remove_windivert(self):
        if not is_admin():
            request_admin_restart()
            return
        subprocess.run("net stop WinDivert", shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        subprocess.run("sc delete WinDivert", shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        subprocess.run("sc delete WinDivert14", shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        self.refresh_requested.emit()


class SettingsPage(QWidget):
    theme_changed = pyqtSignal(str)
    reset_requested = pyqtSignal()

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Theme
        theme_card = CardWidget()
        theme_layout = QVBoxLayout(theme_card)
        theme_layout.setContentsMargins(20, 15, 20, 15)

        theme_layout.addWidget(SubtitleLabel("Тема оформления"))

        self.theme_combo = ComboBox()
        self.theme_combo.addItems(["dark", "light"])
        self.theme_combo.setCurrentText(self.config.get("theme", "dark"))
        self.theme_combo.currentTextChanged.connect(self._on_theme_change)
        theme_layout.addWidget(self.theme_combo)

        layout.addWidget(theme_card)

        # Updates
        upd_card = CardWidget()
        upd_layout = QVBoxLayout(upd_card)
        upd_layout.setContentsMargins(20, 15, 20, 15)

        upd_layout.addWidget(SubtitleLabel("Проверка обновлений"))

        self.upd_switch = SwitchButton()
        self.upd_switch.setChecked(self.config.get("check_updates", True))
        self.upd_switch.checkedChanged.connect(self._on_upd_change)
        upd_layout.addWidget(self.upd_switch)

        layout.addWidget(upd_card)

        # Reset
        reset_card = CardWidget()
        reset_layout = QVBoxLayout(reset_card)
        reset_layout.setContentsMargins(20, 15, 20, 15)

        reset_layout.addWidget(SubtitleLabel("Сброс настроек"))
        reset_layout.addWidget(BodyLabel("Удаляет все файлы Zapret и скачивает заново"))

        reset_btn = PushButton("Сбросить всё")
        reset_btn.setStyleSheet("background-color: #c42b1c;")
        reset_btn.clicked.connect(self._reset)
        reset_layout.addWidget(reset_btn)

        layout.addWidget(reset_card)
        layout.addStretch()

    def _on_theme_change(self, theme):
        self.config.set("theme", theme)
        self.theme_changed.emit(theme)

    def _on_upd_change(self, checked):
        self.config.set("check_updates", checked)

    def _reset(self):
        reply = QMessageBox.question(self, "Сброс", "Удалить все файлы Zapret и скачать заново?")
        if reply == QMessageBox.StandardButton.Yes:
            self.reset_requested.emit()


# ========== Main Window ==========

class ZapretWindow(FluentWindow):
    def __init__(self):
        super().__init__()

        # Paths
        self.base_dir = get_base_install_dir()
        self.zapret_dir = get_zapret_dir()
        self.app_dir = get_app_dir()
        self.lists_dir = self.zapret_dir / "lists"
        self.utils_dir = self.zapret_dir / "utils"

        # Config
        self.app_dir.mkdir(parents=True, exist_ok=True)
        self.config = Config(self.app_dir)
        self.installer = Installer()

        # Apply theme
        theme = Theme.DARK if self.config.get("theme", "dark") == "dark" else Theme.LIGHT
        setTheme(theme)

        # Setup window
        self.setWindowTitle("Zapret GUI v2")
        self.resize(1100, 750)
        self.setMinimumSize(900, 600)

        # Check if installed
        if not self.installer.check_installed():
            self._show_install_screen()
        else:
            self._init_main_ui()

    def _show_install_screen(self):
        # Simple install widget
        install_widget = QWidget()
        layout = QVBoxLayout(install_widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = SubtitleLabel("Zapret GUI")
        title.setStyleSheet("font-size: 32px; font-weight: bold;")
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)

        info = BodyLabel(f"Установка в: {self.base_dir}")
        layout.addWidget(info, alignment=Qt.AlignmentFlag.AlignCenter)

        self.install_progress = ProgressBar()
        self.install_progress.setMinimumWidth(400)
        self.install_progress.setValue(0)
        layout.addWidget(self.install_progress, alignment=Qt.AlignmentFlag.AlignCenter)

        self.install_label = BodyLabel("Нажмите кнопку для установки")
        layout.addWidget(self.install_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.install_btn = PrimaryPushButton("Установить Zapret")
        self.install_btn.setMinimumWidth(200)
        self.install_btn.clicked.connect(self._start_install)
        layout.addWidget(self.install_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # Add to stacked widget
        install_widget.setObjectName("installPage")
        self.addSubInterface(install_widget, FluentIcon.DOWNLOAD, "Установка")

    def _start_install(self, reset=False):
        self.install_btn.setEnabled(False)
        self.install_btn.setText("Установка...")

        self.worker = InstallWorker(self.installer, reset)
        self.worker.progress.connect(self._on_install_progress)
        self.worker.finished.connect(self._on_install_finished)
        self.worker.start()

    def _on_install_progress(self, text, value):
        self.install_label.setText(text)
        self.install_progress.setValue(value)

    def _on_install_finished(self, success):
        if success:
            # Recreate window with main UI
            self.close()
            self.new_window = ZapretWindow()
            self.new_window.show()
        else:
            self.install_btn.setEnabled(True)
            self.install_btn.setText("Повторить")

    def _init_main_ui(self):
        # Create pages
        self.lists_page = ListsPage()
        self.lists_page.set_lists_dir(self.lists_dir)

        self.strategies_page = StrategiesPage()
        self.strategies_page.set_zapret_dir(self.zapret_dir)
        self.strategies_page.refresh_requested.connect(self._refresh_data)

        self.autorun_page = AutorunPage()
        self.autorun_page.set_zapret_dir(self.zapret_dir)
        self.autorun_page.refresh_requested.connect(self._refresh_data)

        self.options_page = OptionsPage()
        self.options_page.set_dirs(self.zapret_dir, self.utils_dir, self.lists_dir)

        self.test_page = TestPage()

        self.status_page = StatusPage()
        self.status_page.refresh_requested.connect(self._refresh_data)

        self.settings_page = SettingsPage(self.config)
        self.settings_page.theme_changed.connect(self._on_theme_change)
        self.settings_page.reset_requested.connect(self._on_reset)

        # Set object names (required by FluentWindow)
        self.lists_page.setObjectName("listsPage")
        self.strategies_page.setObjectName("strategiesPage")
        self.autorun_page.setObjectName("autorunPage")
        self.options_page.setObjectName("optionsPage")
        self.test_page.setObjectName("testPage")
        self.status_page.setObjectName("statusPage")
        self.settings_page.setObjectName("settingsPage")

        # Add navigation
        self.addSubInterface(self.lists_page, FluentIcon.DOCUMENT, "Списки")
        self.addSubInterface(self.strategies_page, FluentIcon.PLAY, "Стратегии")
        self.addSubInterface(self.autorun_page, FluentIcon.POWER_BUTTON, "Автозапуск")
        self.addSubInterface(self.options_page, FluentIcon.SETTING, "Опции")
        self.addSubInterface(self.test_page, FluentIcon.WIFI, "Тест")
        self.addSubInterface(self.status_page, FluentIcon.INFO, "Статус")

        self.addSubInterface(self.settings_page, FluentIcon.SETTING, "Настройки",
                            position=NavigationItemPosition.BOTTOM)

        # Initial data load
        self._refresh_data()

        # Check updates
        if self.config.get("check_updates", True):
            import threading
            threading.Thread(target=self._check_updates, daemon=True).start()

    def _refresh_data(self):
        # Store worker as instance attribute to prevent garbage collection
        self._status_worker = StatusWorker(self.zapret_dir, self.lists_dir)
        self._status_worker.result.connect(self._on_data_loaded)
        self._status_worker.start()

    def _on_data_loaded(self, status, strategies, lists, version):
        # Update all pages with new data
        if hasattr(self, 'status_page'):
            self.status_page.update_status(status)
            self.status_page.set_version(version)
        if hasattr(self, 'strategies_page'):
            self.strategies_page.update_status(status)
            self.strategies_page.update_strategies(strategies)
        if hasattr(self, 'autorun_page'):
            self.autorun_page.update_strategies(strategies)
        if hasattr(self, 'lists_page'):
            self.lists_page.update_lists(lists)

    def _on_theme_change(self, theme_name):
        theme = Theme.DARK if theme_name == "dark" else Theme.LIGHT
        setTheme(theme)

    def _on_reset(self):
        ServiceManager.remove_service()
        # Clear zapret dir
        if self.zapret_dir.exists():
            try:
                shutil.rmtree(self.zapret_dir)
            except:
                pass
        # Restart with install
        self.close()
        self.new_window = ZapretWindow()
        self.new_window.show()

    def _check_updates(self):
        try:
            has_upd, ver = self.installer.check_updates()
            if has_upd:
                QTimer.singleShot(0, lambda: InfoBar.warning(
                    "Обновление доступно",
                    f"Версия {ver} доступна на GitHub",
                    parent=self,
                    duration=5000,
                    position=InfoBarPosition.TOP_RIGHT
                ))
        except:
            pass
def run_as_admin():
    """Restart the application with admin rights if not already admin."""
    if is_admin():
        return True  # Already admin
    
    try:
        if getattr(sys, 'frozen', False):
            # Running as compiled exe
            exe = sys.executable
            result = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, None, None, 1)
        else:
            # Running as script
            exe = sys.executable
            script = os.path.abspath(__file__)
            result = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, f'"{script}"', None, 1)
        
        # ShellExecuteW returns > 32 on success
        if result > 32:
            return False  # Will exit, new process started
        else:
            # User cancelled UAC or error
            ctypes.windll.user32.MessageBoxW(
                0,
                "Приложение требует прав администратора для работы.\n\nБез прав администратора невозможно управлять службами и применять настройки.",
                "Zapret GUI - Требуются права администратора",
                0x10  # MB_ICONERROR
            )
            return True  # Exit anyway
    except:
        ctypes.windll.user32.MessageBoxW(
            0,
            "Не удалось запросить права администратора.",
            "Ошибка",
            0x10
        )
        return True


def main():
    # Check admin rights and restart if needed
    if not is_admin():
        run_as_admin()
        sys.exit(0)  # Always exit, either new admin process started or user cancelled
    
    # Disable QFluentWidgets animations for better performance
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
    
    # High DPI
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    app.setApplicationName("Zapret GUI")

    # Icon
    icon_path = Path(__file__).parent / "app.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Self-install check
    if getattr(sys, 'frozen', False):
        try:
            check_and_install_self()
        except Exception as e:
            print(f"Self-install error: {e}")

    window = ZapretWindow()
    window.show()
    sys.exit(app.exec())

def create_shortcut(target_path: Path):
    """Create shortcut using PowerShell to avoid win32com dependency"""
    try:
        desktop = Path.home() / "Desktop"
        shortcut_path = desktop / "Zapret GUI.lnk"
        
        # PowerShell script to create shortcut
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
        return True
    except:
        return False

def check_and_install_self():
    """Check if running from install dir, if not - offer install"""
    current_exe = Path(sys.executable).resolve()
    install_dir = get_app_dir()
    target_exe = install_dir / "ZapretGUI.exe"
    
    # Check if we are already running from the correct location
    # Use string comparison for safety with path normalization
    if str(current_exe).lower() == str(target_exe.resolve()).lower():
        return

    # Prompt user
    msg = QMessageBox()
    msg.setWindowTitle("Установка Zapret GUI")
    msg.setText("Установить Zapret GUI?")
    msg.setInformativeText(f"Приложение будет скопировано в:\n{install_dir}\n\nБудет создан ярлык на рабочем столе.")
    msg.setIcon(QMessageBox.Icon.Question)
    msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    msg.setDefaultButton(QMessageBox.StandardButton.Yes)
    
    if msg.exec() == QMessageBox.StandardButton.Yes:
        try:
            # Create directories
            install_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy executable
            shutil.copy2(current_exe, target_exe)
            
            # Create shortcut
            create_shortcut(target_exe)
            
            # Notify
            QMessageBox.information(None, "Успешно", "Приложение установлено! Запускаем установленную версию...")
            
            # Launch installed version
            subprocess.Popen([str(target_exe)], cwd=str(install_dir))
            sys.exit(0)
            
        except Exception as e:
            QMessageBox.critical(None, "Ошибка установки", f"Не удалось установить: {str(e)}")



if __name__ == "__main__":
    main()
