# 应用图标

当前已有 `icon.png` 源文件，需要生成各平台专用格式。

## 生成图标命令

### 方法 1: 使用 electron-icon-builder (推荐)

```bash
# 安装工具
npm install -g electron-icon-builder

# 生成所有平台图标
electron-icon-builder --input=icon.png --output=./

# 这会生成:
# - icons/  (Linux 各尺寸 PNG)
# - icon.icns (macOS)
# - icon.ico (Windows)
```

### 方法 2: 使用 png2icons

```bash
npm install -g png2icons
png2icons icon.png icon -allp
```

### 方法 3: macOS 原生工具 (仅 macOS)

```bash
# 创建 iconset 文件夹
mkdir icon.iconset

# 生成各尺寸图片 (需要 sips 命令)
sips -z 16 16     icon.png --out icon.iconset/icon_16x16.png
sips -z 32 32     icon.png --out icon.iconset/icon_16x16@2x.png
sips -z 32 32     icon.png --out icon.iconset/icon_32x32.png
sips -z 64 64     icon.png --out icon.iconset/icon_32x32@2x.png
sips -z 128 128   icon.png --out icon.iconset/icon_128x128.png
sips -z 256 256   icon.png --out icon.iconset/icon_128x128@2x.png
sips -z 256 256   icon.png --out icon.iconset/icon_256x256.png
sips -z 512 512   icon.png --out icon.iconset/icon_256x256@2x.png
sips -z 512 512   icon.png --out icon.iconset/icon_512x512.png
sips -z 1024 1024 icon.png --out icon.iconset/icon_512x512@2x.png

# 转换为 icns
iconutil -c icns icon.iconset
```

### 方法 4: 在线工具

- macOS (.icns): https://cloudconvert.com/png-to-icns
- Windows (.ico): https://icoconvert.com/

## 所需文件清单

| 文件 | 平台 | 说明 |
|------|------|------|
| `icon.png` | 源文件 | 建议 1024x1024 |
| `icon.icns` | macOS | 包含多尺寸 |
| `icon.ico` | Windows | 包含多尺寸 |
| `icons/` | Linux | 各尺寸 PNG |

## Linux icons 目录结构

```
icons/
├── 16x16.png
├── 32x32.png
├── 48x48.png
├── 64x64.png
├── 128x128.png
├── 256x256.png
└── 512x512.png
```
