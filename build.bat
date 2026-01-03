@echo off
echo Building Zapret GUI...
echo.

:: Конвертируем иконку если нужно
if not exist "app.ico" (
    echo Converting icon...
    python convert_icon.py
)

:: Билд приложения (с самоустановкой)
echo Building ZapretGUI.exe...
pyinstaller --noconfirm --onefile --windowed --icon=app.ico --name=ZapretGUI --add-data="app.ico;." main.py

:: Копируем в release
echo.
echo Creating release folder...
if not exist "release" mkdir release
copy dist\ZapretGUI.exe release\

echo.
echo ========================================
echo Build complete!
echo.
echo Release file: release\ZapretGUI.exe
echo.
echo Для GitHub Release загружай ТОЛЬКО:
echo   ZapretGUI.exe
echo.
echo При первом запуске приложение само
echo предложит установиться и создаст ярлык!
echo ========================================
pause
