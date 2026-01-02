"""
Zapret GUI v1 - Графический интерфейс для zapret-discord-youtube
Автор: absolute2007
Репозиторий: https://github.com/absolute2007/zapret-gui
"""

import customtkinter as ctk
import os
import subprocess
import threading
import socket
import sys
import time
import requests
import zipfile
import shutil
import ctypes
import re
import webbrowser
import json
import tkinter.filedialog as fd
import tkinter.messagebox as mb
from pathlib import Path
from typing import Optional, Tuple, List, Dict
from packaging import version

# Константы
GITHUB_REPO = "Flowseal/zapret-discord-youtube"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"
APP_NAME = "ZapretGUI"
INSTALL_DIR_NAME = "zapret-gui"
CONFIG_FILE = "zapret_gui_config.json"

def get_base_install_dir() -> Path:
    """Базовая директория установки: %LOCALAPPDATA%/zapret-gui"""
    return Path(os.environ.get('LOCALAPPDATA', Path.home())) / INSTALL_DIR_NAME

def get_zapret_dir() -> Path:
    """Директория оригинального zapret"""
    return get_base_install_dir() / "zapret"

def get_app_dir() -> Path:
    """Директория GUI приложения"""
    return get_base_install_dir() / "app"

def create_desktop_shortcut(target_path: Path, shortcut_name: str = "Zapret GUI"):
    try:
        desktop = Path.home() / "Desktop"
        shortcut_path = desktop / f"{shortcut_name}.lnk"
        ps_script = f'''
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "{target_path}"
$Shortcut.WorkingDirectory = "{target_path.parent}"
$Shortcut.Save()
'''
        subprocess.run(["powershell", "-Command", ps_script], 
                      creationflags=subprocess.CREATE_NO_WINDOW, capture_output=True)
        return True
    except: return False

def check_and_self_install():
    """Проверяет установлено ли приложение, если нет - устанавливает себя"""
    if not getattr(sys, 'frozen', False):
        return  # Не exe, разработка
    
    current_exe = Path(sys.executable)
    app_dir = get_app_dir()
    installed_exe = app_dir / "ZapretGUI.exe"
    
    # Если уже запущено из правильного места - ничего не делаем
    if current_exe.parent == app_dir:
        return
    
    # Спрашиваем пользователя
    import tkinter.messagebox as msgbox
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    
    result = msgbox.askyesno(
        "Установка Zapret GUI",
        f"Установить Zapret GUI в:\n{app_dir}\n\nИ создать ярлык на рабочем столе?"
    )
    
    if not result:
        root.destroy()
        return
    
    try:
        # Создаём директории
        get_base_install_dir().mkdir(parents=True, exist_ok=True)
        app_dir.mkdir(parents=True, exist_ok=True)
        
        # Копируем exe
        shutil.copy2(current_exe, installed_exe)
        
        # Создаём ярлык
        create_desktop_shortcut(installed_exe)
        
        msgbox.showinfo("Готово!", f"Приложение установлено!\n\nЯрлык создан на рабочем столе.")
        
        # Запускаем установленную версию и выходим
        subprocess.Popen([str(installed_exe)])
        root.destroy()
        os._exit(0)
        
    except Exception as e:
        msgbox.showerror("Ошибка", f"Не удалось установить: {e}")
        root.destroy()


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def request_admin_restart() -> bool:
    """Ask user to restart app with admin rights. Returns True if restarting."""
    if is_admin():
        return False
    if mb.askyesno("Требуются права администратора", 
                   "Для этого действия нужны права администратора.\n\nПерезапустить программу от имени администратора?"):
        try:
            if getattr(sys, 'frozen', False):
                exe = sys.executable
                ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, None, None, 1)
            else:
                exe = sys.executable
                script = os.path.abspath(__file__)
                ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, f'"{script}"', None, 1)
            os._exit(0)  # Force close current window
        except:
            return False
    return False

class Config:
    """Управление настройками приложения"""
    def __init__(self, app_dir: Path):
        self.config_path = app_dir / CONFIG_FILE
        self.data = {"theme": "dark", "check_updates": True}
        self.load()
    
    def load(self):
        try:
            if self.config_path.exists():
                with open(self.config_path, "r") as f:
                    self.data.update(json.load(f))
        except: pass
    
    def save(self):
        try:
            with open(self.config_path, "w") as f:
                json.dump(self.data, f, indent=2)
        except: pass
    
    def get(self, key, default=None):
        return self.data.get(key, default)
    
    def set(self, key, value):
        self.data[key] = value
        self.save()

class AppState:
    def __init__(self):
        self.status_data = {}
        self.strategies = []
        self.current_list_file = "list-general.txt"
        self.available_lists = []
        self.game_filter_enabled = False
        self.ipset_status = "any"  # any, none, loaded

class Installer:
    """Установщик zapret из GitHub releases"""
    def __init__(self):
        self.base_dir = get_base_install_dir()
        self.zapret_dir = get_zapret_dir()
        self.app_dir = get_app_dir()
        self.bin_dir = self.zapret_dir / "bin"
        self.lists_dir = self.zapret_dir / "lists"
        self.utils_dir = self.zapret_dir / "utils"
        self.service_bat = self.zapret_dir / "service.bat"
        
    def check_installed(self) -> bool:
        return self.bin_dir.exists() and self.service_bat.exists()
    
    def get_local_version(self) -> Optional[str]:
        if not self.service_bat.exists(): return None
        try:
            with open(self.service_bat, "r", encoding="utf-8", errors="ignore") as f:
                match = re.search(r'set\s+"LOCAL_VERSION=([^"]+)"', f.read())
                if match: return match.group(1)
        except: pass
        return None

    def check_updates(self) -> Tuple[bool, str]:
        try:
            response = requests.get(GITHUB_API_URL, timeout=5)
            response.raise_for_status()
            data = response.json()
            latest = data["tag_name"]
            local = self.get_local_version()
            if not local: return True, latest
            return version.parse(latest.lstrip('v')) > version.parse(local.lstrip('v')), latest
        except: return False, ""

    def _get_release_zip_url(self) -> Optional[str]:
        """Получить URL zip-архива из последнего релиза"""
        try:
            response = requests.get(GITHUB_API_URL, timeout=10)
            response.raise_for_status()
            data = response.json()
            # Ищем zip-ассет в релизе
            for asset in data.get("assets", []):
                if asset["name"].endswith(".zip"):
                    return asset["browser_download_url"]
            # Если нет zip-ассета, используем zipball
            return data.get("zipball_url")
        except:
            return None

    def download_and_install(self, progress_callback, reset: bool = False) -> bool:
        try:
            # Создаём директории
            self.base_dir.mkdir(parents=True, exist_ok=True)
            self.zapret_dir.mkdir(parents=True, exist_ok=True)
            self.app_dir.mkdir(parents=True, exist_ok=True)
            
            if reset and self.zapret_dir.exists():
                progress_callback("Удаление старых файлов...", 0.1)
                for item in self.zapret_dir.iterdir():
                    if item.is_dir(): shutil.rmtree(item)
                    else: item.unlink()
            
            progress_callback("Получение информации о релизе...", 0.2)
            zip_url = self._get_release_zip_url()
            if not zip_url:
                # Fallback: скачиваем main ветку
                zip_url = f"https://github.com/{GITHUB_REPO}/archive/refs/heads/main.zip"
            
            progress_callback("Скачивание zapret...", 0.3)
            r = requests.get(zip_url, stream=True, timeout=120)
            r.raise_for_status()
            
            temp_zip = self.base_dir / "zapret_download.zip"
            with open(temp_zip, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
            
            progress_callback("Распаковка...", 0.6)
            extract_dir = self.base_dir / "temp_extract"
            if extract_dir.exists(): shutil.rmtree(extract_dir)
            extract_dir.mkdir()
            
            with zipfile.ZipFile(temp_zip, 'r') as z: z.extractall(extract_dir)
            
            # Находим папку внутри архива (обычно repo-name-version)
            contents = list(extract_dir.iterdir())
            source_dir = contents[0] if len(contents) == 1 and contents[0].is_dir() else extract_dir
            
            # Копируем содержимое в zapret_dir
            progress_callback("Установка файлов...", 0.8)
            for item in source_dir.iterdir():
                if item.name in ["gui", ".git", ".github"]: continue
                dest = self.zapret_dir / item.name
                if dest.exists():
                    if dest.is_dir(): shutil.rmtree(dest)
                    else: dest.unlink()
                shutil.move(str(item), str(dest))
            
            # Очистка
            shutil.rmtree(extract_dir)
            if temp_zip.exists(): temp_zip.unlink()
            
            progress_callback("Создание ярлыка...", 0.9)
            exe_path = Path(sys.executable) if getattr(sys, 'frozen', False) else Path(__file__)
            create_desktop_shortcut(exe_path)
            
            progress_callback("Готово!", 1.0)
            return True
        except Exception as e:
            progress_callback(f"Ошибка: {str(e)[:50]}", 0)
            return False

class ServiceManager:
    """Управление службой zapret"""
    
    @staticmethod
    def stop_service():
        """Полная остановка службы и процесса"""
        subprocess.run("net stop zapret", shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        subprocess.run("taskkill /F /IM winws.exe", shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        time.sleep(0.5)
    
    @staticmethod
    def remove_service():
        """Удаление службы zapret и WinDivert"""
        ServiceManager.stop_service()
        # Parallel cleanup to be faster
        subprocess.run("sc delete zapret", shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        subprocess.run("sc delete WinDivert", shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        subprocess.run("sc delete WinDivert14", shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        subprocess.run("net stop WinDivert", shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        subprocess.run("net stop WinDivert14", shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    
    @staticmethod
    def install_service(strategy_path: Path, app_dir: Path) -> Tuple[bool, str]:
        """Установка службы из стратегии"""
        log_path = app_dir / "install_debug.log"
        try:
            with open(log_path, "w", encoding="utf-8") as log:
                log.write(f"Strategy: {strategy_path}\n")
                log.write(f"Exists: {strategy_path.exists()}\n\n")
                
                # Читаем bat файл
                with open(strategy_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                
                log.write(f"Content length: {len(content)}\n\n")
                
                # Проверяем game filter
                game_filter_file = app_dir / "utils" / "game_filter.enabled"
                game_filter = "1024-65535" if game_filter_file.exists() else "12"
                
                # Ищем строку запуска winws.exe и собираем аргументы
                lines = content.split('\n')
                args_parts = []
                capturing = False
                
                for line in lines:
                    line = line.strip()
                    if 'winws.exe' in line.lower():
                        capturing = True
                        log.write(f"Found winws line: {line}\n")
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
                log.write(f"\nRaw args: {args[:500]}\n")
                
                # Заменяем переменные
                bin_path = str(app_dir / "bin")
                lists_path = str(app_dir / "lists")
                
                args = args.replace('%BIN%', bin_path + '\\')
                args = args.replace('%LISTS%', lists_path + '\\')
                args = args.replace('%~dp0', str(app_dir) + '\\')
                args = args.replace('%GameFilter%', game_filter)
                
                # Fix for ALT10 and other strategies using escaped special chars
                args = args.replace('^!', '!')
                
                args = re.sub(r'\s+', ' ', args)
                
                log.write(f"\nFinal args: {args[:500]}\n")
                
                winws_path = app_dir / "bin" / "winws.exe"
                log.write(f"\nwinws_path: {winws_path}, exists: {winws_path.exists()}\n")
                
                # Удаляем старую службу
                ServiceManager.remove_service()
                time.sleep(0.5)
                
                # TCP timestamps
                subprocess.run("netsh interface tcp set global timestamps=enabled", 
                              shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                
                # Создаем службу
                bin_path_quoted = f'"{winws_path}"'
                cmd = f'sc create zapret binPath= "{bin_path_quoted} {args}" DisplayName= "zapret" start= auto'
                log.write(f"\nCommand: {cmd[:400]}\n")
                
                result = subprocess.run(cmd, shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                log.write(f"\nsc create return: {result.returncode}\n")
                log.write(f"stdout: {result.stdout.decode('cp866', errors='ignore')}\n")
                log.write(f"stderr: {result.stderr.decode('cp866', errors='ignore')}\n")
                
                if result.returncode != 0:
                    return False, f"sc create failed: {result.stderr.decode('cp866', errors='ignore')}"
                
                subprocess.run('sc description zapret "Zapret DPI bypass software"', 
                              shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
                
                # Запускаем службу
                start_result = subprocess.run("sc start zapret", shell=True, capture_output=True, 
                                             creationflags=subprocess.CREATE_NO_WINDOW)
                log.write(f"\nsc start return: {start_result.returncode}\n")
                log.write(f"stderr: {start_result.stderr.decode('cp866', errors='ignore')}\n")
                
                # Сохраняем имя стратегии
                strat_name = strategy_path.stem
                subprocess.run(f'reg add "HKLM\\System\\CurrentControlSet\\Services\\zapret" /v zapret-discord-youtube /t REG_SZ /d "{strat_name}" /f',
                              shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
                
                return True, "Служба установлена"
                
        except Exception as e:
            with open(log_path, "a", encoding="utf-8") as log:
                log.write(f"\nException: {e}\n")
            return False, str(e)
    
    @staticmethod
    def get_status() -> Dict[str, Tuple[str, bool]]:
        """Получение статуса компонентов"""
        res = {}
        
        # winws.exe
        try:
            o = subprocess.check_output('tasklist /FI "IMAGENAME eq winws.exe"', 
                                       creationflags=subprocess.CREATE_NO_WINDOW).decode('cp866', errors='ignore')
            res["winws"] = ("РАБОТАЕТ", True) if "winws.exe" in o else ("ОСТАНОВЛЕН", False)
        except: res["winws"] = ("НЕИЗВЕСТНО", False)
        
        # zapret service
        try:
            o = subprocess.check_output("sc query zapret", creationflags=subprocess.CREATE_NO_WINDOW).decode('cp866', errors='ignore')
            if "RUNNING" in o:
                res["zapret"] = ("ЗАПУЩЕНА", True)
            elif "STOPPED" in o or "STOP_PENDING" in o:
                res["zapret"] = ("ОСТАНОВЛЕНА", False)
            else:
                res["zapret"] = ("НЕ УСТАНОВЛЕНА", False)
        except: res["zapret"] = ("НЕ УСТАНОВЛЕНА", False)
        
        # WinDivert
        try:
            o = subprocess.check_output("sc query WinDivert", creationflags=subprocess.CREATE_NO_WINDOW).decode('cp866', errors='ignore')
            res["windivert"] = ("ЗАГРУЖЕН", True) if "RUNNING" in o else ("ВЫГРУЖЕН", False)
        except: res["windivert"] = ("НЕ НАЙДЕН", False)
        
        return res

class ZapretGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Пути - используем новую структуру
        self.base_dir = get_base_install_dir()
        self.zapret_dir = get_zapret_dir()  # Здесь лежит оригинальный zapret
        self.app_config_dir = get_app_dir()  # Здесь конфиг GUI
        
        if getattr(sys, 'frozen', False):
            self.icon_path = Path(sys._MEIPASS) / "app.ico" if hasattr(sys, '_MEIPASS') else None
        else:
            self.icon_path = Path(__file__).parent / "app.ico"
        
        # Конфигурация хранится в app директории
        self.app_config_dir.mkdir(parents=True, exist_ok=True)
        self.config = Config(self.app_config_dir)
        
        # Применяем тему
        ctk.set_appearance_mode(self.config.get("theme", "dark"))
        ctk.set_default_color_theme("blue")
        
        if self.icon_path and self.icon_path.exists():
            try: self.iconbitmap(str(self.icon_path))
            except: pass

        # Пути к файлам zapret
        self.lists_dir = self.zapret_dir / "lists"
        self.utils_dir = self.zapret_dir / "utils"
        self.installer = Installer()
        self.app_state = AppState()
        
        self.title("Zapret GUI v1")
        self.geometry("1150x800")
        self.minsize(950, 650)
        
        self._setup_colors()
        
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        if not self.installer.check_installed():
            self._show_installation_screen()
        else:
            self._init_main_ui()
            if self.config.get("check_updates", True):
                threading.Thread(target=self._background_update_check, daemon=True).start()

    def _setup_colors(self):
        is_dark = self.config.get("theme", "dark") == "dark"
        self.colors = {
            "bg_sidebar": "#0a0a0a" if is_dark else "#e8e8e8",
            "bg_main": "#000000" if is_dark else "#f5f5f5",
            "bg_card": "#141414" if is_dark else "#ffffff",
            "accent": "#1a73e8" if is_dark else "#2196f3",
            "accent_hover": "#2b7de9" if is_dark else "#1976d2",
            "success": "#00c853",
            "error": "#ff1744",
            "warning": "#ffc107",
            "text": "#ffffff" if is_dark else "#333333",
            "text_dim": "#888888" if is_dark else "#666666",
            "border": "#2a2a2a" if is_dark else "#dddddd"
        }
        self.configure(fg_color=self.colors["bg_main"])

    def _show_installation_screen(self):
        self.install_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.install_frame.place(relx=0.5, rely=0.5, anchor="center")
        
        ctk.CTkLabel(self.install_frame, text="Zapret GUI", font=ctk.CTkFont(size=48, weight="bold")).pack(pady=20)
        ctk.CTkLabel(self.install_frame, text=f"Установка в: {self.base_dir}", font=ctk.CTkFont(size=13), text_color=self.colors["text_dim"]).pack(pady=5)
        ctk.CTkLabel(self.install_frame, text="Нажмите кнопку для автоматической установки\nфайлов утилиты Zapret.", font=ctk.CTkFont(size=16), justify="center").pack(pady=10)
        
        self.install_btn = ctk.CTkButton(self.install_frame, text="Установить", height=55, width=280, 
                                         font=ctk.CTkFont(size=20, weight="bold"),
                                         fg_color=self.colors["success"], command=self._start_install)
        self.install_btn.pack(pady=40)
        
        self.progress_bar = ctk.CTkProgressBar(self.install_frame, width=400, height=15)
        self.progress_label = ctk.CTkLabel(self.install_frame, text="", font=ctk.CTkFont(size=14))

    def _start_install(self, reset: bool = False):
        self.install_btn.configure(state="disabled", text="Установка...")
        self.progress_bar.pack(pady=15); self.progress_bar.set(0)
        self.progress_label.pack(pady=5)
        threading.Thread(target=lambda: self._run_install_process(reset), daemon=True).start()

    def _run_install_process(self, reset: bool = False):
        def up(t, v): 
            self.after(0, lambda: self.progress_label.configure(text=t))
            self.after(0, lambda: self.progress_bar.set(v))
        if self.installer.download_and_install(up, reset): 
            self.after(0, self._finish_install)
        else: 
            self.after(0, lambda: self.install_btn.configure(state="normal", text="Повторить"))

    def _finish_install(self):
        self.install_frame.destroy()
        self._init_main_ui()

    def _init_main_ui(self):
        self._load_state()
        self._create_sidebar()
        self._create_main_content()
        self._create_status_bar()
        self._refresh_all()

    def _load_state(self):
        # Game filter
        gf = self.utils_dir / "game_filter.enabled"
        self.app_state.game_filter_enabled = gf.exists()
        
        # IPset status
        ipset_file = self.lists_dir / "ipset-all.txt"
        if ipset_file.exists():
            try:
                content = ipset_file.read_text(errors='ignore').strip()
                if not content:
                    self.app_state.ipset_status = "any"
                elif "203.0.113.113/32" in content:
                    self.app_state.ipset_status = "none"
                else:
                    self.app_state.ipset_status = "loaded"
            except:
                self.app_state.ipset_status = "any"
        else:
            self.app_state.ipset_status = "any"

    def _create_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=230, corner_radius=0, fg_color=self.colors["bg_sidebar"])
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(8, weight=1)
        
        ctk.CTkLabel(self.sidebar, text="Zapret", font=ctk.CTkFont(size=28, weight="bold")).grid(row=0, column=0, padx=20, pady=(25, 15))
        
        self.nav_btns = {}
        nav = [
            ("Списки", "lists"),
            ("Стратегии", "strategies"),
            ("Автозапуск", "autorun"),
            ("Опции", "options"),
            ("Тест", "test"),
            ("Статус", "status"),
            ("Настройки", "settings")
        ]
        
        for i, (text, name) in enumerate(nav):
            btn = ctk.CTkButton(self.sidebar, text=text, height=42, corner_radius=8,
                               fg_color="transparent", text_color=self.colors["text"], anchor="w",
                               hover_color=self.colors["accent"], font=ctk.CTkFont(size=14),
                               command=lambda n=name: self._select_tab(n))
            btn.grid(row=i+1, column=0, padx=12, pady=3, sticky="ew")
            self.nav_btns[name] = btn
        
        ver = self.installer.get_local_version() or "?"
        ctk.CTkLabel(self.sidebar, text=f"v{ver}", text_color=self.colors["text_dim"]).grid(row=9, column=0, pady=10)

    def _create_main_content(self):
        self.main = ctk.CTkFrame(self, corner_radius=0, fg_color=self.colors["bg_main"])
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(1, weight=1)
        
        self.header = ctk.CTkFrame(self.main, height=55, fg_color="transparent")
        self.header.grid(row=0, column=0, sticky="ew", padx=25, pady=(15, 5))
        
        self.tab_title = ctk.CTkLabel(self.header, text="", font=ctk.CTkFont(size=24, weight="bold"))
        self.tab_title.pack(side="left")
        
        self.update_btn = ctk.CTkButton(self.header, text="Обновление", width=140, height=32,
                                        fg_color=self.colors["warning"], text_color="#000",
                                        command=lambda: webbrowser.open(GITHUB_RELEASES_URL))
        
        self.pages = {}
        for name in ["lists", "strategies", "autorun", "options", "test", "status", "settings"]:
            self.pages[name] = ctk.CTkFrame(self.main, fg_color="transparent")
            
        self._init_lists_page()
        self._init_strategies_page()
        self._init_autorun_page()
        self._init_options_page()
        self._init_test_page()
        self._init_status_page()
        self._init_settings_page()
        
        self._select_tab("lists")

    def _create_status_bar(self):
        self.statusbar = ctk.CTkFrame(self.main, height=28, fg_color=self.colors["bg_sidebar"])
        self.statusbar.grid(row=2, column=0, sticky="ew")
        self.status_lbl = ctk.CTkLabel(self.statusbar, text="Готово", text_color=self.colors["text_dim"], font=ctk.CTkFont(size=11))
        self.status_lbl.pack(side="left", padx=15, pady=4)

    def _select_tab(self, name):
        # Use grid_remove instead of grid_forget to preserve widget state
        for p in self.pages.values(): p.grid_remove()
        self.pages[name].grid(row=1, column=0, sticky="nsew", padx=25, pady=10)
        
        for n, btn in self.nav_btns.items():
            btn.configure(fg_color=self.colors["accent"] if n == name else "transparent")
        
        titles = {"lists": "Управление списками", "strategies": "Запуск стратегий", 
                  "autorun": "Автозапуск (служба)", "options": "Опции Zapret",
                  "test": "Проверка доступности", "status": "Состояние системы", "settings": "Настройки"}
        self.tab_title.configure(text=titles.get(name, ""))

    # === LISTS PAGE ===
    def _init_lists_page(self):
        page = self.pages["lists"]
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(1, weight=1)
        
        ctrl = ctk.CTkFrame(page, fg_color=self.colors["bg_card"], corner_radius=10)
        ctrl.grid(row=0, column=0, sticky="ew", pady=(0, 12), ipady=8)
        
        ctk.CTkLabel(ctrl, text="Файл:", font=ctk.CTkFont(size=14)).pack(side="left", padx=(15, 5))
        self.list_selector = ctk.CTkOptionMenu(ctrl, values=["list-general.txt"], width=220, command=self._on_list_change)
        self.list_selector.pack(side="left", padx=5)
        
        ctk.CTkButton(ctrl, text="Импорт", width=100, command=self._merge_list).pack(side="left", padx=10)
        ctk.CTkButton(ctrl, text="Сохранить", width=100, fg_color=self.colors["success"], command=self._save_list).pack(side="right", padx=15)
        
        self.list_editor = ctk.CTkTextbox(page, font=("Consolas", 13), corner_radius=10)
        self.list_editor.grid(row=1, column=0, sticky="nsew")
        
        ctk.CTkLabel(page, text="Один домен на строку. Строки с # игнорируются.", 
                    text_color=self.colors["text_dim"], font=ctk.CTkFont(size=11)).grid(row=2, column=0, sticky="w", pady=(8, 0))

    def _on_list_change(self, filename):
        self.app_state.current_list_file = filename
        self._load_list(filename)

    def _load_list(self, filename):
        path = self.lists_dir / filename
        self.list_editor.delete("1.0", "end")
        if path.exists():
            try:
                self.list_editor.insert("1.0", path.read_text(encoding="utf-8", errors="ignore"))
                self._status(f"Загружен: {filename}")
            except Exception as e:
                self._status(f"Ошибка: {e}")

    def _save_list(self):
        filename = self.app_state.current_list_file
        try:
            (self.lists_dir / filename).write_text(self.list_editor.get("1.0", "end-1c"), encoding="utf-8")
            self._status(f"Сохранено: {filename}")
        except Exception as e:
            self._status(f"Ошибка: {e}")

    def _merge_list(self):
        path = fd.askopenfilename(filetypes=[("Text", "*.txt"), ("All", "*.*")])
        if not path: return
        try:
            new = set(l.strip().lower() for l in Path(path).read_text(errors='ignore').split('\n') if l.strip() and not l.startswith('#'))
            current = set(l.strip().lower() for l in self.list_editor.get("1.0", "end-1c").split('\n') if l.strip())
            to_add = new - current
            if to_add:
                txt = self.list_editor.get("1.0", "end-1c").rstrip() + '\n' + '\n'.join(to_add) + '\n'
                self.list_editor.delete("1.0", "end")
                self.list_editor.insert("1.0", txt)
                self._status(f"Добавлено {len(to_add)} доменов")
            else:
                self._status("Все домены уже есть")
        except Exception as e:
            self._status(f"Ошибка: {e}")

    # === STRATEGIES PAGE ===
    def _init_strategies_page(self):
        page = self.pages["strategies"]
        
        ctk.CTkLabel(page, text="Выберите стратегию и нажмите 'Запустить'. Для остановки закройте консоль или нажмите кнопку ниже.",
                    text_color=self.colors["text_dim"], font=ctk.CTkFont(size=13)).pack(anchor="w", pady=(0, 10))
        
        btn_row = ctk.CTkFrame(page, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, 10))
        ctk.CTkButton(btn_row, text="Остановить winws.exe", fg_color=self.colors["error"],
                     command=self._stop_winws).pack(side="left")
        
        self.strats_scroll = ctk.CTkScrollableFrame(page, fg_color="transparent")
        self.strats_scroll.pack(fill="both", expand=True)

    def _render_strategies(self):
        for w in self.strats_scroll.winfo_children(): w.destroy()
        
        if not self.app_state.strategies:
            ctk.CTkLabel(self.strats_scroll, text="Стратегии не найдены", text_color=self.colors["text_dim"]).pack(pady=30)
            return
        
        for name in self.app_state.strategies:
            f = ctk.CTkFrame(self.strats_scroll, fg_color=self.colors["bg_card"], corner_radius=10)
            f.pack(fill="x", pady=4)
            
            ctk.CTkLabel(f, text=name, font=ctk.CTkFont(size=14, weight="bold")).pack(side="left", padx=18, pady=12)
            ctk.CTkButton(f, text="Запустить", width=120, height=35, fg_color=self.colors["success"],
                         command=lambda n=name: self._run_strategy(n)).pack(side="right", padx=12, pady=8)

    def _run_strategy(self, name):
        p = self.zapret_dir / name
        if not p.exists():
            self._status(f"Файл не найден: {name}")
            return
        
        if is_admin():
            subprocess.Popen(str(p), cwd=str(self.zapret_dir), creationflags=subprocess.CREATE_NEW_CONSOLE, shell=True)
            self._status(f"Запущено: {name}")
        else:
            ctypes.windll.shell32.ShellExecuteW(None, "runas", str(p), None, str(self.zapret_dir), 1)
            self._status("Запрос прав...")        

    def _stop_winws(self):
        subprocess.run("taskkill /F /IM winws.exe", shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        self._status("winws.exe остановлен")
        self._refresh_all()

    # === AUTORUN PAGE ===
    def _init_autorun_page(self):
        page = self.pages["autorun"]
        
        info = ctk.CTkFrame(page, fg_color=self.colors["bg_card"], corner_radius=8)
        info.pack(fill="x", pady=(0, 15), ipady=10)
        
        ctk.CTkLabel(info, text="Установка службы Windows", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=15, pady=(10, 3))
        ctk.CTkLabel(info, text="Zapret будет запускаться автоматически при включении компьютера.\nТребуются права администратора.",
                    text_color=self.colors["text_dim"], font=ctk.CTkFont(size=12)).pack(anchor="w", padx=15, pady=(0, 5))
        
        # Admin status
        self.admin_label = ctk.CTkLabel(info, text="", font=ctk.CTkFont(size=12))
        self.admin_label.pack(anchor="w", padx=15, pady=(0, 10))
        self._update_admin_label()
        
        # Strategy selection
        strat_frame = ctk.CTkFrame(page, fg_color=self.colors["bg_card"], corner_radius=8)
        strat_frame.pack(fill="x", pady=10, ipady=10)
        
        ctk.CTkLabel(strat_frame, text="Выберите стратегию:", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(10, 5))
        
        # Use StringVar to track selection
        self.selected_strategy = ctk.StringVar(value="Загрузка...")
        self.auto_strat_menu = ctk.CTkOptionMenu(strat_frame, values=["Загрузка..."], width=400, height=40,
                                                  fg_color=self.colors["bg_main"],
                                                  variable=self.selected_strategy)
        self.auto_strat_menu.pack(anchor="w", padx=15, pady=5)
        
        ctk.CTkButton(strat_frame, text="Установить службу", height=42, width=200,
                     fg_color=self.colors["success"], font=ctk.CTkFont(size=14),
                     command=self._install_service).pack(anchor="w", padx=15, pady=15)

    def _update_admin_label(self):
        if is_admin():
            self.admin_label.configure(text="Статус: Запущено с правами администратора", text_color=self.colors["success"])
        else:
            self.admin_label.configure(text="Статус: Нет прав администратора (нажмите для перезапуска)", text_color=self.colors["warning"])
            self.admin_label.bind("<Button-1>", lambda e: request_admin_restart())
            self.admin_label.configure(cursor="hand2")

    def _install_service(self):
        strat = self.selected_strategy.get()
        if strat == "Загрузка..." or not strat:
            self._status("Выберите стратегию")
            return
        
        if not is_admin():
            if request_admin_restart():
                return
            self._status("Отменено - нужны права администратора")
            return
        
        self._status(f"Установка: {strat}...")
        threading.Thread(target=self._bg_install_service, args=(strat,), daemon=True).start()

    def _bg_install_service(self, strat):
        try:
            strat_path = self.zapret_dir / strat
            success, msg = ServiceManager.install_service(strat_path, self.zapret_dir)
            self.after(0, lambda: self._status(f"{'Успешно:' if success else 'Ошибка:'} {msg}"))
        except Exception as e:
            self.after(0, lambda: self._status(f"Ошибка: {e}"))
        self.after(0, self._refresh_all)

    def _start_service(self):
        if not is_admin():
            if request_admin_restart():
                return
            self._status("Отменено - нужны права администратора")
            return
        
        result = subprocess.run("sc start zapret", shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode == 0:
            self._status("Служба запущена")
        else:
            err = result.stderr.decode('cp866', errors='ignore')
            self._status(f"Ошибка запуска: {err[:50]}")
        self._refresh_all()

    def _stop_service(self):
        if not is_admin():
            if request_admin_restart():
                return
            self._status("Отменено - нужны права администратора")
            return
        
        ServiceManager.stop_service()
        self._status("Служба остановлена")
        self._refresh_all()

    def _remove_service(self):
        if not is_admin():
            if request_admin_restart():
                return
            self._status("Отменено - нужны права администратора")
            return
        
        if mb.askyesno("Подтверждение", "Удалить службу zapret?"):
            ServiceManager.remove_service()
            self._status("Службы удалены")
            self._refresh_all()

    # === OPTIONS PAGE ===
    def _init_options_page(self):
        page = self.pages["options"]
        
        # Game Filter
        gf = ctk.CTkFrame(page, fg_color=self.colors["bg_card"], corner_radius=10)
        gf.pack(fill="x", pady=6, ipady=12)
        
        ctk.CTkLabel(gf, text="Game Filter", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=18, pady=(8, 2))
        ctk.CTkLabel(gf, text="Расширяет диапазон портов для игр (1024-65535 вместо 12)", 
                    text_color=self.colors["text_dim"]).pack(anchor="w", padx=18)
        
        self.gf_switch = ctk.CTkSwitch(gf, text="Включено" if self.app_state.game_filter_enabled else "Отключено",
                                       command=self._toggle_game_filter)
        self.gf_switch.pack(anchor="w", padx=18, pady=8)
        if self.app_state.game_filter_enabled:
            self.gf_switch.select()
        
        # IPset
        ip = ctk.CTkFrame(page, fg_color=self.colors["bg_card"], corner_radius=10)
        ip.pack(fill="x", pady=6, ipady=12)
        
        ctk.CTkLabel(ip, text="IPset", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=18, pady=(8, 2))
        ctk.CTkLabel(ip, text="Режим IP-списка: any (все), none (никакой), loaded (из файла)",
                    text_color=self.colors["text_dim"]).pack(anchor="w", padx=18)
        
        self.ipset_label = ctk.CTkLabel(ip, text=f"Текущий режим: {self.app_state.ipset_status.upper()}", 
                                        font=ctk.CTkFont(size=13))
        self.ipset_label.pack(anchor="w", padx=18, pady=5)
        
        ipbtns = ctk.CTkFrame(ip, fg_color="transparent")
        ipbtns.pack(anchor="w", padx=18, pady=5)
        ctk.CTkButton(ipbtns, text="Переключить", width=120, command=self._toggle_ipset).pack(side="left", padx=(0, 10))
        ctk.CTkButton(ipbtns, text="Обновить список", width=140, command=self._update_ipset).pack(side="left")
        
        # Hosts
        hosts = ctk.CTkFrame(page, fg_color=self.colors["bg_card"], corner_radius=10)
        hosts.pack(fill="x", pady=6, ipady=12)
        
        ctk.CTkLabel(hosts, text="Discord Hosts", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=18, pady=(8, 2))
        ctk.CTkLabel(hosts, text="Обновить hosts файл для голосовых серверов Discord",
                    text_color=self.colors["text_dim"]).pack(anchor="w", padx=18)
        ctk.CTkButton(hosts, text="Обновить hosts", width=140, command=self._update_hosts).pack(anchor="w", padx=18, pady=8)

        # Diagnostics
        diag = ctk.CTkFrame(page, fg_color=self.colors["bg_card"], corner_radius=10)
        diag.pack(fill="x", pady=6, ipady=12)
        
        ctk.CTkLabel(diag, text="🔧 Диагностика", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=18, pady=(8, 2))
        ctk.CTkLabel(diag, text="Проверка системы на конфликты и проблемы",
                    text_color=self.colors["text_dim"]).pack(anchor="w", padx=18)
        ctk.CTkButton(diag, text="Запустить диагностику", width=180, command=self._run_diagnostics).pack(anchor="w", padx=18, pady=8)

    def _toggle_game_filter(self):
        gf_file = self.utils_dir / "game_filter.enabled"
        self.utils_dir.mkdir(exist_ok=True)
        
        if gf_file.exists():
            gf_file.unlink()
            self.app_state.game_filter_enabled = False
            self.gf_switch.configure(text="Отключено")
            self._status("Game Filter отключен. Перезапустите Zapret.")
        else:
            gf_file.write_text("ENABLED")
            self.app_state.game_filter_enabled = True
            self.gf_switch.configure(text="Включено")
            self._status("Game Filter включен. Перезапустите Zapret.")

    def _toggle_ipset(self):
        ipset_file = self.lists_dir / "ipset-all.txt"
        backup_file = self.lists_dir / "ipset-all.txt.backup"
        
        if self.app_state.ipset_status == "loaded":
            # -> none
            if backup_file.exists(): backup_file.unlink()
            if ipset_file.exists():
                ipset_file.rename(backup_file)
            ipset_file.write_text("203.0.113.113/32\n")
            self.app_state.ipset_status = "none"
        elif self.app_state.ipset_status == "none":
            # -> any
            ipset_file.write_text("")
            self.app_state.ipset_status = "any"
        else:  # any -> loaded
            if backup_file.exists():
                if ipset_file.exists(): ipset_file.unlink()
                backup_file.rename(ipset_file)
                self.app_state.ipset_status = "loaded"
            else:
                self._status("Нет бэкапа. Обновите список сначала.")
                return
        
        self.ipset_label.configure(text=f"Текущий режим: {self.app_state.ipset_status.upper()}")
        self._status(f"IPset: {self.app_state.ipset_status}. Перезапустите Zapret.")

    def _update_ipset(self):
        self._status("Обновление IPset...")
        threading.Thread(target=self._bg_update_ipset, daemon=True).start()

    def _bg_update_ipset(self):
        try:
            url = "https://raw.githubusercontent.com/Flowseal/zapret-discord-youtube/refs/heads/main/.service/ipset-service.txt"
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            (self.lists_dir / "ipset-all.txt").write_text(r.text)
            self.app_state.ipset_status = "loaded"
            self.after(0, lambda: self.ipset_label.configure(text=f"Текущий режим: LOADED"))
            self.after(0, lambda: self._status("IPset обновлен"))
        except Exception as e:
            self.after(0, lambda: self._status(f"Ошибка: {e}"))

    def _update_hosts(self):
        self._status("Обновление hosts...")
        threading.Thread(target=self._bg_update_hosts, daemon=True).start()

    def _bg_update_hosts(self):
        try:
            url = "https://raw.githubusercontent.com/Flowseal/zapret-discord-youtube/refs/heads/main/.service/discord-hosts.txt"
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            
            hosts_path = Path(os.environ.get('SystemRoot', 'C:\\Windows')) / "System32" / "drivers" / "etc" / "hosts"
            new_entries = r.text.strip()
            
            if not is_admin():
                self.after(0, lambda: mb.showwarning("Требуются права", "Для редактирования hosts нужны права администратора"))
                return
            
            current = hosts_path.read_text(errors='ignore') if hosts_path.exists() else ""
            if new_entries not in current:
                with open(hosts_path, "a") as f:
                    f.write("\n# Discord Voice (zapret-gui)\n" + new_entries + "\n")
                self.after(0, lambda: self._status("Hosts обновлен"))
            else:
                self.after(0, lambda: self._status("Hosts уже содержит записи"))
        except Exception as e:
            self.after(0, lambda: self._status(f"Ошибка: {e}"))

    def _run_diagnostics(self):
        self._status("Запуск диагностики...")
        threading.Thread(target=self._bg_diagnostics, daemon=True).start()
    
    def _bg_diagnostics(self):
        results = []
        results.append("=== ДИАГНОСТИКА ZAPRET ===\n\n")
        
        # Check winws.exe
        try:
            o = subprocess.check_output('tasklist /FI "IMAGENAME eq winws.exe"', 
                                       creationflags=subprocess.CREATE_NO_WINDOW).decode('cp866', errors='ignore')
            if "winws.exe" in o:
                results.append("[OK] winws.exe запущен\n")
            else:
                results.append("[X] winws.exe НЕ запущен\n")
        except:
            results.append("[?] Не удалось проверить winws.exe\n")
        
        # Check zapret service
        try:
            o = subprocess.check_output("sc query zapret", creationflags=subprocess.CREATE_NO_WINDOW).decode('cp866', errors='ignore')
            if "RUNNING" in o:
                results.append("[OK] Служба zapret запущена\n")
            elif "STOPPED" in o:
                results.append("[X] Служба zapret остановлена\n")
            else:
                results.append("[?] Служба zapret в неизвестном состоянии\n")
        except:
            results.append("[X] Служба zapret не установлена\n")
        
        # Check WinDivert
        try:
            o = subprocess.check_output("sc query WinDivert", creationflags=subprocess.CREATE_NO_WINDOW).decode('cp866', errors='ignore')
            results.append("[OK] WinDivert установлен\n" if "RUNNING" in o else "[X] WinDivert не запущен\n")
        except:
            results.append("[X] WinDivert не найден\n")
        
        # Check DNS
        results.append("\n=== ПРОВЕРКА СЕТИ ===\n\n")
        try:
            import socket
            socket.gethostbyname("discord.com")
            results.append("[OK] DNS работает (discord.com resolves)\n")
        except:
            results.append("[X] DNS не работает\n")
        
        # Check HTTPS
        try:
            r = requests.get("https://discord.com", timeout=3)
            results.append(f"[OK] HTTPS работает (discord.com: {r.status_code})\n")
        except Exception as e:
            results.append(f"[X] HTTPS ошибка: {str(e)[:40]}\n")
        
        # Show results in messagebox
        def show():
            mb.showinfo("Диагностика", "".join(results))
            self._status("Диагностика завершена")
        self.after(0, show)

    # === TEST PAGE ===
    def _init_test_page(self):
        page = self.pages["test"]
        
        inp = ctk.CTkFrame(page, fg_color=self.colors["bg_card"], corner_radius=10)
        inp.pack(fill="x", pady=(0, 12), ipady=8)
        
        self.test_entry = ctk.CTkEntry(inp, placeholder_text="discord.com", height=42, font=ctk.CTkFont(size=14))
        self.test_entry.pack(side="left", fill="x", expand=True, padx=15, pady=8)
        self.test_entry.bind("<Return>", lambda e: self._run_test())
        
        ctk.CTkButton(inp, text="Проверить", width=130, height=42, command=self._run_test).pack(side="right", padx=15)
        
        self.test_results = ctk.CTkTextbox(page, font=("Consolas", 13), corner_radius=10)
        self.test_results.pack(fill="both", expand=True)
        self.test_results.insert("1.0", "Результаты проверки появятся здесь...\n")

    def _run_test(self):
        domain = self.test_entry.get().strip().replace("https://", "").replace("http://", "").split("/")[0]
        if not domain: return
        
        self.test_results.delete("1.0", "end")
        self.test_results.insert("end", f"Проверка {domain}...\n\n")
        threading.Thread(target=self._bg_test, args=(domain,), daemon=True).start()

    def _bg_test(self, domain):
        results = []
        
        try:
            t = time.time()
            ip = socket.gethostbyname(domain)
            results.append(f"+ DNS: {ip} ({int((time.time()-t)*1000)}ms)\n")
        except Exception as e:
            results.append(f"- DNS: {e}\n")
        
        try:
            t = time.time()
            r = requests.get(f"https://{domain}", timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            results.append(f"+ HTTPS: {r.status_code} ({int((time.time()-t)*1000)}ms)\n")
        except Exception as e:
            results.append(f"- HTTPS: {e}\n")
        
        self.after(0, lambda: self.test_results.insert("end", "".join(results)))

    # === STATUS PAGE ===
    def _init_status_page(self):
        page = self.pages["status"]
        
        # Status cards with individual controls
        self.status_cards = {}
        
        # winws.exe
        card1 = ctk.CTkFrame(page, fg_color=self.colors["bg_card"], corner_radius=8)
        card1.pack(fill="x", pady=4)
        left1 = ctk.CTkFrame(card1, fg_color="transparent")
        left1.pack(side="left", padx=15, pady=10)
        ctk.CTkLabel(left1, text="winws.exe", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(left1, text="Процесс обхода DPI", text_color=self.colors["text_dim"], font=ctk.CTkFont(size=11)).pack(anchor="w")
        ctk.CTkButton(card1, text="Остановить", width=90, height=30, fg_color=self.colors["error"],
                     command=self._stop_winws).pack(side="right", padx=10)
        self.status_cards["winws"] = ctk.CTkLabel(card1, text="...", font=ctk.CTkFont(size=12))
        self.status_cards["winws"].pack(side="right", padx=10)
        
        # zapret service
        card2 = ctk.CTkFrame(page, fg_color=self.colors["bg_card"], corner_radius=8)
        card2.pack(fill="x", pady=4)
        left2 = ctk.CTkFrame(card2, fg_color="transparent")
        left2.pack(side="left", padx=15, pady=10)
        ctk.CTkLabel(left2, text="Служба zapret", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(left2, text="Автозапуск Windows", text_color=self.colors["text_dim"], font=ctk.CTkFont(size=11)).pack(anchor="w")
        ctk.CTkButton(card2, text="Удалить", width=80, height=30, fg_color=self.colors["error"],
                     command=self._remove_zapret_service).pack(side="right", padx=5)
        ctk.CTkButton(card2, text="Стоп", width=60, height=30, fg_color=self.colors["warning"], text_color="#000",
                     command=self._stop_service).pack(side="right", padx=5)
        self.status_cards["zapret"] = ctk.CTkLabel(card2, text="...", font=ctk.CTkFont(size=12))
        self.status_cards["zapret"].pack(side="right", padx=10)
        
        # WinDivert
        card3 = ctk.CTkFrame(page, fg_color=self.colors["bg_card"], corner_radius=8)
        card3.pack(fill="x", pady=4)
        left3 = ctk.CTkFrame(card3, fg_color="transparent")
        left3.pack(side="left", padx=15, pady=10)
        ctk.CTkLabel(left3, text="WinDivert", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(left3, text="Сетевой драйвер", text_color=self.colors["text_dim"], font=ctk.CTkFont(size=11)).pack(anchor="w")
        ctk.CTkButton(card3, text="Удалить", width=80, height=30, fg_color=self.colors["error"],
                     command=self._remove_windivert).pack(side="right", padx=10)
        self.status_cards["windivert"] = ctk.CTkLabel(card3, text="...", font=ctk.CTkFont(size=12))
        self.status_cards["windivert"].pack(side="right", padx=10)
        
        # Refresh button and GitHub
        bottom = ctk.CTkFrame(page, fg_color="transparent")
        bottom.pack(fill="x", pady=20)
        
        ctk.CTkButton(bottom, text="Обновить статус", width=140, height=36,
                     command=self._refresh_all).pack(side="left", padx=(0, 10))
        ctk.CTkButton(bottom, text="GitHub: zapret", width=140, height=36,
                     fg_color=self.colors["bg_card"], hover_color=self.colors["accent"],
                     command=lambda: webbrowser.open("https://github.com/Flowseal/zapret-discord-youtube")).pack(side="left")

    def _remove_zapret_service(self):
        if not is_admin():
            if request_admin_restart(): return
        subprocess.run("net stop zapret", shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        subprocess.run("sc delete zapret", shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        self._status("Служба zapret удалена")
        self._refresh_all()
    
    def _remove_windivert(self):
        if not is_admin():
            if request_admin_restart(): return
        subprocess.run("net stop WinDivert", shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        subprocess.run("sc delete WinDivert", shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        subprocess.run("net stop WinDivert14", shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        subprocess.run("sc delete WinDivert14", shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        self._status("WinDivert удален")
        self._refresh_all()

    def _stop_all(self):
        if not is_admin():
            if request_admin_restart(): return
        ServiceManager.stop_service()
        self._status("Всё остановлено")
        self._refresh_all()

    # === SETTINGS PAGE ===
    def _init_settings_page(self):
        page = self.pages["settings"]
        
        # Theme
        theme = ctk.CTkFrame(page, fg_color=self.colors["bg_card"], corner_radius=10)
        theme.pack(fill="x", pady=6, ipady=12)
        
        ctk.CTkLabel(theme, text="Тема", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=18, pady=(8, 5))
        
        self.theme_menu = ctk.CTkOptionMenu(theme, values=["dark", "light"], width=150, 
                                            command=self._change_theme)
        self.theme_menu.set(self.config.get("theme", "dark"))
        self.theme_menu.pack(anchor="w", padx=18, pady=5)
        
        # Check updates
        upd = ctk.CTkFrame(page, fg_color=self.colors["bg_card"], corner_radius=10)
        upd.pack(fill="x", pady=6, ipady=12)
        
        ctk.CTkLabel(upd, text="Проверка обновлений", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=18, pady=(8, 5))
        self.upd_switch = ctk.CTkSwitch(upd, text="При запуске", command=self._toggle_updates)
        if self.config.get("check_updates", True):
            self.upd_switch.select()
        self.upd_switch.pack(anchor="w", padx=18, pady=5)
        
        # Reset
        reset = ctk.CTkFrame(page, fg_color=self.colors["bg_card"], corner_radius=10)
        reset.pack(fill="x", pady=6, ipady=12)
        
        ctk.CTkLabel(reset, text="Сброс настроек", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=18, pady=(8, 2))
        ctk.CTkLabel(reset, text="Удаляет все файлы Zapret и скачивает заново", 
                    text_color=self.colors["text_dim"]).pack(anchor="w", padx=18)
        ctk.CTkButton(reset, text="Сбросить всё", width=140, fg_color=self.colors["error"],
                     command=self._reset_all).pack(anchor="w", padx=18, pady=8)

    def _change_theme(self, theme):
        self.config.set("theme", theme)
        ctk.set_appearance_mode(theme)
        self._setup_colors()
        # Recreate UI for immediate theme application
        self._recreate_ui()

    def _toggle_updates(self):
        self.config.set("check_updates", self.upd_switch.get() == 1)

    def _reset_all(self):
        if mb.askyesno("Подтверждение", "Удалить все файлы Zapret и скачать заново?"):
            ServiceManager.remove_service()
            for w in self.main.winfo_children(): w.destroy()
            for w in self.sidebar.winfo_children(): w.destroy()
            self._show_installation_screen()
            self._start_install(reset=True)

    def _recreate_ui(self):
        """Recreate UI to apply theme changes immediately"""
        # Destroy current UI
        if hasattr(self, 'sidebar'):
            self.sidebar.destroy()
        if hasattr(self, 'main'):
            self.main.destroy()
        
        # Rebuild
        self._init_main_ui()

    # === BACKGROUND ===
    def _refresh_all(self):
        threading.Thread(target=self._bg_load_data, daemon=True).start()

    def _bg_load_data(self):
        # Lists
        if self.lists_dir.exists():
            lists = [f.name for f in self.lists_dir.glob("*.txt")]
            self.app_state.available_lists = sorted(lists)
            self.after(0, lambda: self.list_selector.configure(values=self.app_state.available_lists))
            if self.app_state.current_list_file in self.app_state.available_lists:
                self.after(0, lambda: self._load_list(self.app_state.current_list_file))
        
        # Strategies
        strats = [f.name for f in self.zapret_dir.glob("general*.bat")]
        self.app_state.strategies = sorted(strats)
        self.after(0, self._render_strategies)
        if strats:
            current = self.selected_strategy.get()
            self.after(0, lambda s=strats: self.auto_strat_menu.configure(values=s))
            # Only set first if current is invalid
            if current not in strats:
                self.after(0, lambda s=strats[0]: self.selected_strategy.set(s))
        
        # Status
        status = ServiceManager.get_status()
        def upd():
            for k, (txt, run) in status.items():
                c = self.colors["success"] if run else self.colors["error"]
                self.status_cards[k].configure(text=txt + (" [OK]" if run else " [X]"), text_color=c)
        self.after(0, upd)

    def _background_update_check(self):
        try:
            has_upd, ver = self.installer.check_updates()
            if has_upd:
                self.after(0, lambda: self.update_btn.pack(side="right", padx=10))
        except: pass

    def _status(self, text):
        self.status_lbl.configure(text=text)

if __name__ == "__main__":
    check_and_self_install()  # Самоустановка при первом запуске
    app = ZapretGUI()
    app.mainloop()
