# 打包发布

将 DiffCOT 打包为独立的桌面应用程序：

## 快速打包

```bash
# macOS
./scripts/build.sh mac

# Windows
scripts\build.bat win

# Linux
./scripts/build.sh linux

# 所有平台
./scripts/build.sh all
```

## 手动打包步骤

### 1. 打包后端 (PyInstaller)

```bash
cd backend

# 安装 PyInstaller
pip install pyinstaller

# 使用 spec 文件打包
pyinstaller diffcot-backend.spec --clean

# 复制到前端目录
cp -r dist/diffcot-backend/* ../frontend/backend-dist/
```

### 2. 打包前端 (Electron Builder)

```bash
cd frontend

# 安装依赖
npm install

# 打包 macOS (.dmg)
npm run dist:mac

# 打包 Windows (.exe)
npm run dist:win

# 打包 Linux (.AppImage)
npm run dist:linux
```

### 输出文件

打包完成后，安装包位于 `frontend/release/` 目录：

| 平台    | 文件格式      | 说明          |
| ------- | ------------- | ------------- |
| macOS   | `.dmg`      | 拖拽安装      |
| Windows | `.exe`      | NSIS 安装程序 |
| Linux   | `.AppImage` | 便携式应用    |

### 应用图标

在打包前，需要在 `frontend/build-resources/` 目录放置应用图标：

- macOS: `icon.icns`
- Windows: `icon.ico`
- Linux: `icons/` 目录包含各尺寸 PNG
