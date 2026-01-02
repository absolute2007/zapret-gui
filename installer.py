"""
Zapret GUI Installer
Скачивает и устанавливает Zapret GUI в %LOCALAPPDATA%\zapret-gui
"""

import os
import sys
import shutil
import subprocess
import ctypes
import requests
from pathlib import Path

# ВАЖНО: Укажи свой репозиторий здесь
GITHUB_REPO = "absolute2007/zapret-gui"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

APP_NAME = "Zapret GUI"
INSTALL_DIR = Path(os.environ.get('LOCALAPPDATA', Path.home())) / "zapret-gui"
APP_DIR = INSTALL_DIR / "app"

def create_shortcut(target_path: Path, shortcut_name: str = "Zapret GUI"):
    """Создание ярлыка на рабочем столе"""
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
    except:
        return False

def get_download_url():
    """Получить URL для скачивания ZapretGUI.exe из последнего релиза"""
    try:
        response = requests.get(GITHUB_API_URL, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        # Ищем ZapretGUI.exe в ассетах
        for asset in data.get("assets", []):
            if asset["name"] == "ZapretGUI.exe":
                return asset["browser_download_url"], data["tag_name"]
        
        return None, None
    except Exception as e:
        print(f"Ошибка: {e}")
        return None, None

def download_file(url, dest_path, desc="Скачивание"):
    """Скачивание файла с прогрессом"""
    try:
        response = requests.get(url, stream=True, timeout=120)
        response.raise_for_status()
        total = int(response.headers.get('content-length', 0))
        
        with open(dest_path, 'wb') as f:
            downloaded = 0
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = int(downloaded * 100 / total)
                    print(f"\r{desc}: {pct}%", end="", flush=True)
        print()
        return True
    except Exception as e:
        print(f"\nОшибка скачивания: {e}")
        return False

def main():
    print("=" * 50)
    print(f"  {APP_NAME} - Установщик")
    print("=" * 50)
    print()
    
    # Получаем URL для скачивания
    print("Проверка обновлений...")
    download_url, version = get_download_url()
    
    if not download_url:
        print("[X] Не удалось получить ссылку для скачивания")
        print("    Проверьте подключение к интернету")
        input("\nНажмите Enter для выхода...")
        return
    
    print(f"[OK] Найдена версия: {version}")
    print(f"Установка в: {INSTALL_DIR}")
    print()
    
    # Создаём директории
    try:
        INSTALL_DIR.mkdir(parents=True, exist_ok=True)
        APP_DIR.mkdir(parents=True, exist_ok=True)
        print("[OK] Директории созданы")
    except Exception as e:
        print(f"[X] Ошибка создания директорий: {e}")
        input("\nНажмите Enter для выхода...")
        return
    
    # Скачиваем exe
    dest_exe = APP_DIR / "ZapretGUI.exe"
    if not download_file(download_url, dest_exe, "Скачивание ZapretGUI.exe"):
        input("\nНажмите Enter для выхода...")
        return
    print("[OK] Приложение скачано")
    
    # Создаём ярлык
    if create_shortcut(dest_exe):
        print("[OK] Ярлык создан на рабочем столе")
    else:
        print("[!] Не удалось создать ярлык")
    
    print()
    print("=" * 50)
    print("  Установка завершена!")
    print("=" * 50)
    print()
    print(f"Приложение: {dest_exe}")
    print()
    
    # Предлагаем запустить
    response = input("Запустить Zapret GUI? (y/n): ").strip().lower()
    if response in ['y', 'yes', 'д', 'да', '']:
        subprocess.Popen([str(dest_exe)], creationflags=subprocess.CREATE_NEW_CONSOLE)
        print("Приложение запущено!")

if __name__ == "__main__":
    main()
