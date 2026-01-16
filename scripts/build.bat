@echo off
REM DiffCOT Build Script (Windows)
REM Usage: scripts\build.bat [win|clean|backend|frontend]
REM
REM IMPORTANT: PyInstaller does NOT support cross-platform packaging!
REM - Windows exe must be built on Windows
REM - macOS app must be built on macOS (use build.sh)
REM - Linux must be built on Linux (use build.sh)

setlocal enabledelayedexpansion

echo ========================================
echo   DiffCOT Build Script (Windows)
echo ========================================

set PROJECT_ROOT=%~dp0..
set TARGET=%~1

if "%TARGET%"=="" set TARGET=win

REM Set Electron mirror (for China network)
set ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/
set ELECTRON_BUILDER_BINARIES_MIRROR=https://npmmirror.com/mirrors/electron-builder-binaries/

REM Check dependencies
echo Checking dependencies...

where python >nul 2>nul
if errorlevel 1 (
    echo Error: Python not found
    exit /b 1
)

where node >nul 2>nul
if errorlevel 1 (
    echo Error: Node.js not found
    exit /b 1
)

REM Check PyInstaller
python -c "import PyInstaller" >nul 2>nul
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

echo Dependencies OK

REM Execute based on target
if "%TARGET%"=="clean" goto clean
if "%TARGET%"=="frontend" goto frontend

REM Check if Windows backend already exists
if exist "%PROJECT_ROOT%\frontend\backend-dist\diffcot-backend.exe" (
    echo Found existing Windows backend, skipping backend build
    goto skip_backend
)

REM Check if non-Windows backend exists (built on macOS/Linux)
if exist "%PROJECT_ROOT%\frontend\backend-dist\diffcot-backend" (
    if not exist "%PROJECT_ROOT%\frontend\backend-dist\diffcot-backend.exe" (
        echo ========================================
        echo   WARNING: Non-Windows backend detected!
        echo ========================================
        echo Found diffcot-backend but no diffcot-backend.exe
        echo This backend was built on macOS/Linux and cannot run on Windows
        echo Removing old backend and rebuilding...
        rmdir /s /q "%PROJECT_ROOT%\frontend\backend-dist"
    )
)

:build_backend
echo ========================================
echo   Building Backend with PyInstaller
echo ========================================

cd /d "%PROJECT_ROOT%\backend"

REM Clean old build files
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM Build with PyInstaller
echo Running PyInstaller...
pyinstaller diffcot-backend.spec --clean
if errorlevel 1 (
    echo PyInstaller build failed!
    exit /b 1
)

REM Verify exe was created
if not exist "dist\diffcot-backend\diffcot-backend.exe" (
    echo Error: PyInstaller did not generate diffcot-backend.exe
    echo Please check diffcot-backend.spec configuration
    exit /b 1
)

REM Copy to frontend directory
if not exist "%PROJECT_ROOT%\frontend\backend-dist" mkdir "%PROJECT_ROOT%\frontend\backend-dist"
xcopy /s /e /y dist\diffcot-backend\* "%PROJECT_ROOT%\frontend\backend-dist\"
if errorlevel 1 (
    echo Failed to copy backend files!
    exit /b 1
)

REM Verify copy succeeded
if not exist "%PROJECT_ROOT%\frontend\backend-dist\diffcot-backend.exe" (
    echo Error: Backend file copy failed
    exit /b 1
)

echo ----------------------------------------
echo Backend build complete
echo Output: %PROJECT_ROOT%\frontend\backend-dist\diffcot-backend.exe
echo ----------------------------------------

:skip_backend
if "%TARGET%"=="backend" goto done

:frontend
echo ========================================
echo   Building Frontend with Electron Builder
echo   Target: Windows
echo ========================================

REM Verify backend exists
if not exist "%PROJECT_ROOT%\frontend\backend-dist\diffcot-backend.exe" (
    echo Error: Windows backend executable not found!
    echo Please run: scripts\build.bat backend
    echo Or run: scripts\build.bat win
    exit /b 1
)

cd /d "%PROJECT_ROOT%\frontend"

REM Install dependencies
echo Installing npm dependencies...
call npm install
if errorlevel 1 (
    echo npm install failed
    exit /b 1
)

REM Build frontend
echo Building frontend...
call npx tsc -b
if errorlevel 1 (
    echo TypeScript compilation failed
    exit /b 1
)

call npx vite build
if errorlevel 1 (
    echo Vite build failed
    exit /b 1
)

call npm run electron:build
if errorlevel 1 (
    echo Electron build failed
    exit /b 1
)

REM Package Windows app
echo Packaging Windows application...
call npx electron-builder --config electron-builder.config.cjs --win
if errorlevel 1 (
    echo electron-builder packaging failed
    exit /b 1
)

echo ========================================
echo Frontend build complete
echo Output: %PROJECT_ROOT%\frontend\release
echo ========================================
goto done

:clean
echo Cleaning build files...
if exist "%PROJECT_ROOT%\backend\build" rmdir /s /q "%PROJECT_ROOT%\backend\build"
if exist "%PROJECT_ROOT%\backend\dist" rmdir /s /q "%PROJECT_ROOT%\backend\dist"
if exist "%PROJECT_ROOT%\frontend\dist" rmdir /s /q "%PROJECT_ROOT%\frontend\dist"
if exist "%PROJECT_ROOT%\frontend\dist-electron" rmdir /s /q "%PROJECT_ROOT%\frontend\dist-electron"
if exist "%PROJECT_ROOT%\frontend\release" rmdir /s /q "%PROJECT_ROOT%\frontend\release"
if exist "%PROJECT_ROOT%\frontend\backend-dist" rmdir /s /q "%PROJECT_ROOT%\frontend\backend-dist"
echo Clean complete
goto done

:done
echo.
echo ========================================
echo   Done!
echo ========================================
echo.
echo Usage:
echo   scripts\build.bat win      - Build full Windows app (backend + frontend)
echo   scripts\build.bat backend  - Build backend only
echo   scripts\build.bat frontend - Build frontend only (requires backend first)
echo   scripts\build.bat clean    - Clean all build files
echo.
echo NOTE: PyInstaller does NOT support cross-platform packaging!
echo   - Windows exe must be built on Windows (use build.bat)
echo   - macOS app must be built on macOS (use build.sh)
echo   - Linux must be built on Linux (use build.sh)
echo.
endlocal
