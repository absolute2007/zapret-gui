@echo off
setlocal
echo ========================================
echo   Auto-Builder for Zapret GUI
echo ========================================
echo.

:: 1. Cleanup
echo [1/5] Cleaning up old builds...
if exist "build" rd /s /q "build"
if exist "dist" rd /s /q "dist"
if exist "release" rd /s /q "release"
if exist "app.zip" del "app.zip"

:: 2. Build Main Application (Onedir)
echo.
echo [2/5] Building Main Application...
pyinstaller --noconfirm ZapretGUI.spec
if errorlevel 1 goto error

:: 3. Zip the application
echo.
echo [3/5] Compressing Application...
powershell -Command "Compress-Archive -Path 'dist\ZapretGUI\*' -DestinationPath 'app.zip' -Force"
if errorlevel 1 goto error

:: 4. Build Installer
echo.
echo [4/5] Building Installer...
pyinstaller --noconfirm ZapretGUI_Setup.spec
if errorlevel 1 goto error

:: 5. Copy to release
echo.
echo [5/5] Finalizing...
mkdir release
copy "dist\ZapretGUI_Setup.exe" "release\"
copy "dist\ZapretGUI_Setup.exe" "ZapretGUI_Setup.exe"

echo.
echo ========================================
echo   BUILD SUCCESSFUL!
echo ========================================
echo.
echo Installer location:
echo   release\ZapretGUI_Setup.exe
echo.
pause
exit /b 0

:error
echo.
echo ========================================
echo   BUILD FAILED!
echo ========================================
echo.
pause
exit /b 1
