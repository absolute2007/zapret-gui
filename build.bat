@echo off
echo Building Zapret GUI...
echo.

:: Конвертируем иконку если нужно
if not exist "app.ico" (
    echo Converting icon...
    python convert_icon.py
)

:: Билд основного приложения
echo Building ZapretGUI.exe...
pyinstaller --noconfirm --onefile --windowed --icon=app.ico --name=ZapretGUI --add-data="app.ico;." main.py

:: Билд установщика (включаем requests)
echo Building ZapretGUI_Setup.exe...
pyinstaller --noconfirm --onefile --console --icon=app.ico --name=ZapretGUI_Setup --hidden-import=requests installer.py

:: Копируем файлы для релиза
echo.
echo Creating release folder...
if not exist "release" mkdir release
copy dist\ZapretGUI.exe release\
copy dist\ZapretGUI_Setup.exe release\

echo.
echo ========================================
echo Build complete!
echo.
echo Release files in: release\
echo.
echo Для GitHub release загружай:
echo - ZapretGUI.exe (основное приложение)
echo - ZapretGUI_Setup.exe (установщик)
echo.
echo Пользователю достаточно скачать только
echo ZapretGUI_Setup.exe - он сам скачает
echo и установит приложение!
echo ========================================
pause
