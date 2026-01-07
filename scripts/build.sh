#!/bin/bash
# DiffCOT 打包脚本 (macOS/Linux)
# 用法: ./scripts/build.sh [mac|win|linux|all]

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  DiffCOT 打包脚本${NC}"
echo -e "${GREEN}========================================${NC}"

# 检查依赖
check_dependencies() {
    echo -e "${YELLOW}检查依赖...${NC}"

    # 检查 Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}错误: 未找到 Python3${NC}"
        exit 1
    fi

    # 检查 Node.js
    if ! command -v node &> /dev/null; then
        echo -e "${RED}错误: 未找到 Node.js${NC}"
        exit 1
    fi

    # 检查 PyInstaller
    if ! python3 -c "import PyInstaller" &> /dev/null; then
        echo -e "${YELLOW}安装 PyInstaller...${NC}"
        pip3 install pyinstaller
    fi

    echo -e "${GREEN}依赖检查通过${NC}"
}

# 打包后端
build_backend() {
    # 检查是否已经有打包好的后端
    if [ -d "$PROJECT_ROOT/frontend/backend-dist" ] && [ -f "$PROJECT_ROOT/frontend/backend-dist/diffcot-backend" ]; then
        echo -e "${GREEN}检测到已打包的后端，跳过后端打包${NC}"
        return 0
    fi

    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}  打包后端 (PyInstaller)${NC}"
    echo -e "${YELLOW}========================================${NC}"

    cd "$PROJECT_ROOT/backend"

    # 清理旧的构建文件
    rm -rf build dist

    # 使用 PyInstaller 打包
    pyinstaller diffcot-backend.spec --clean

    # 复制到前端目录
    mkdir -p "$PROJECT_ROOT/frontend/backend-dist"
    cp -r dist/diffcot-backend/* "$PROJECT_ROOT/frontend/backend-dist/"

    echo -e "${GREEN}后端打包完成${NC}"
}

# 打包前端
build_frontend() {
    local target=$1
    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}  打包前端 (Electron Builder)${NC}"
    echo -e "${YELLOW}  目标平台: $target${NC}"
    echo -e "${YELLOW}========================================${NC}"

    cd "$PROJECT_ROOT/frontend"

    # 安装依赖
    npm install

    # 根据目标平台打包
    case $target in
        mac)
            npm run dist:mac
            ;;
        win)
            npm run dist:win
            ;;
        linux)
            npm run dist:linux
            ;;
        all)
            npm run dist
            ;;
        *)
            echo -e "${RED}未知目标平台: $target${NC}"
            exit 1
            ;;
    esac

    echo -e "${GREEN}前端打包完成${NC}"
    echo -e "${GREEN}输出目录: $PROJECT_ROOT/frontend/release${NC}"
}

# 清理构建文件
clean() {
    echo -e "${YELLOW}清理构建文件...${NC}"
    rm -rf "$PROJECT_ROOT/backend/build"
    rm -rf "$PROJECT_ROOT/backend/dist"
    rm -rf "$PROJECT_ROOT/frontend/dist"
    rm -rf "$PROJECT_ROOT/frontend/dist-electron"
    rm -rf "$PROJECT_ROOT/frontend/release"
    rm -rf "$PROJECT_ROOT/frontend/backend-dist"
    echo -e "${GREEN}清理完成${NC}"
}

# 主函数
main() {
    local target=${1:-mac}

    case $target in
        clean)
            clean
            ;;
        backend)
            check_dependencies
            build_backend
            ;;
        frontend)
            check_dependencies
            build_frontend "${2:-mac}"
            ;;
        mac|win|linux|all)
            check_dependencies
            build_backend
            build_frontend "$target"
            ;;
        *)
            echo "用法: $0 [mac|win|linux|all|clean|backend|frontend]"
            echo ""
            echo "选项:"
            echo "  mac      - 打包 macOS 应用 (.dmg)"
            echo "  win      - 打包 Windows 应用 (.exe)"
            echo "  linux    - 打包 Linux 应用 (.AppImage)"
            echo "  all      - 打包所有平台"
            echo "  clean    - 清理构建文件"
            echo "  backend  - 仅打包后端"
            echo "  frontend - 仅打包前端 (需要指定平台)"
            exit 1
            ;;
    esac
}

main "$@"
