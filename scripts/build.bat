@echo off
REM DiffCOT 打包脚本 (Windows)
REM 用法: scripts\build.bat [mac|win|linux|all]

setlocal

echo ========================================
echo   DiffCOT 打包脚本
echo ========================================

set PROJECT_ROOT=%~dp0..
set TARGET=%~1

if "%TARGET%"=="" set TARGET=win

REM 设置 Electron 镜像源（解决国内网络问题）
set ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/
set ELECTRON_BUILDER_BINARIES_MIRROR=https://npmmirror.com/mirrors/electron-builder-binaries/

REM 检查依赖
echo 检查依赖...

where python >nul 2>nul
if errorlevel 1 (
    echo 错误: 未找到 Python
    exit /b 1
)

where node >nul 2>nul
if errorlevel 1 (
    echo 错误: 未找到 Node.js
    exit /b 1
)

REM 检查 PyInstaller
python -c "import PyInstaller" >nul 2>nul
if errorlevel 1 (
    echo 安装 PyInstaller...
    pip install pyinstaller
)

echo 依赖检查通过

REM 根据目标执行
if "%TARGET%"=="clean" goto clean
if "%TARGET%"=="frontend" goto frontend

REM 检查是否已经有打包好的后端
if exist "%PROJECT_ROOT%\frontend\backend-dist\diffcot-backend.exe" (
    echo 检测到已打包的后端，跳过后端打包
    goto skip_backend
)

echo ========================================
echo   打包后端 PyInstaller
echo ========================================

cd /d "%PROJECT_ROOT%\backend"

REM 清理旧的构建文件
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM 使用 PyInstaller 打包
pyinstaller diffcot-backend.spec --clean

REM 复制到前端目录
if not exist "%PROJECT_ROOT%\frontend\backend-dist" mkdir "%PROJECT_ROOT%\frontend\backend-dist"
xcopy /s /e /y dist\diffcot-backend\* "%PROJECT_ROOT%\frontend\backend-dist\"

echo 后端打包完成

:skip_backend
if "%TARGET%"=="backend" goto done

:frontend
REM 打包前端
echo ========================================
echo   打包前端 Electron Builder
echo   目标平台: %TARGET%
echo ========================================

cd /d "%PROJECT_ROOT%\frontend"

REM 安装依赖
call npm install

REM 构建前端
echo 构建前端...
call npx tsc -b
if errorlevel 1 (
    echo TypeScript 编译失败
    goto done
)

call npx vite build
if errorlevel 1 (
    echo Vite 构建失败
    goto done
)

call npm run electron:build
if errorlevel 1 (
    echo Electron 构建失败
    goto done
)

REM 根据目标平台打包
echo 打包应用...
if "%TARGET%"=="mac" call npx electron-builder --config electron-builder.config.cjs --mac
if "%TARGET%"=="win" call npx electron-builder --config electron-builder.config.cjs --win
if "%TARGET%"=="linux" call npx electron-builder --config electron-builder.config.cjs --linux
if "%TARGET%"=="all" call npx electron-builder --config electron-builder.config.cjs --win --mac --linux
if "%TARGET%"=="frontend" call npx electron-builder --config electron-builder.config.cjs --win

echo 前端打包完成
echo 输出目录: %PROJECT_ROOT%\frontend\release
goto done

:clean
echo 清理构建文件...
if exist "%PROJECT_ROOT%\backend\build" rmdir /s /q "%PROJECT_ROOT%\backend\build"
if exist "%PROJECT_ROOT%\backend\dist" rmdir /s /q "%PROJECT_ROOT%\backend\dist"
if exist "%PROJECT_ROOT%\frontend\dist" rmdir /s /q "%PROJECT_ROOT%\frontend\dist"
if exist "%PROJECT_ROOT%\frontend\dist-electron" rmdir /s /q "%PROJECT_ROOT%\frontend\dist-electron"
if exist "%PROJECT_ROOT%\frontend\release" rmdir /s /q "%PROJECT_ROOT%\frontend\release"
if exist "%PROJECT_ROOT%\frontend\backend-dist" rmdir /s /q "%PROJECT_ROOT%\frontend\backend-dist"
echo 清理完成
goto done

:done
echo.
echo ========================================
echo   打包完成!
echo ========================================
endlocal
