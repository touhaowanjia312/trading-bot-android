#!/bin/bash
# 自动化Android应用构建脚本

set -e  # 遇到错误立即退出

echo "🚀 开始构建Android交易应用..."
echo "=================================="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目信息
PROJECT_NAME="交易跟单机器人"
PACKAGE_NAME="tradingbot"
APP_VERSION="1.0"

# 检查系统环境
check_system() {
    echo -e "${BLUE}📋 检查系统环境...${NC}"
    
    # 检查操作系统
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
        echo -e "${GREEN}✅ 检测到Linux系统${NC}"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        echo -e "${GREEN}✅ 检测到macOS系统${NC}"
    else
        echo -e "${RED}❌ 不支持的操作系统: $OSTYPE${NC}"
        echo -e "${YELLOW}建议使用Linux或macOS进行Android开发${NC}"
        exit 1
    fi
    
    # 检查Python版本
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | grep -oP '(?<=Python )\d+\.\d+')
        if (( $(echo "$PYTHON_VERSION >= 3.8" | bc -l) )); then
            echo -e "${GREEN}✅ Python版本检查通过: $PYTHON_VERSION${NC}"
        else
            echo -e "${RED}❌ Python版本过低，需要3.8+，当前版本: $PYTHON_VERSION${NC}"
            exit 1
        fi
    else
        echo -e "${RED}❌ Python3未安装${NC}"
        exit 1
    fi
    
    # 检查磁盘空间
    AVAILABLE_SPACE=$(df . | tail -1 | awk '{print $4}')
    REQUIRED_SPACE=10485760  # 10GB in KB
    if [ $AVAILABLE_SPACE -gt $REQUIRED_SPACE ]; then
        echo -e "${GREEN}✅ 磁盘空间充足${NC}"
    else
        echo -e "${YELLOW}⚠️ 磁盘空间可能不足，建议至少10GB可用空间${NC}"
    fi
}

# 安装系统依赖
install_system_deps() {
    echo -e "${BLUE}📦 安装系统依赖...${NC}"
    
    if [[ "$OS" == "linux" ]]; then
        # 检查包管理器
        if command -v apt &> /dev/null; then
            PKG_MANAGER="apt"
        elif command -v yum &> /dev/null; then
            PKG_MANAGER="yum"
        else
            echo -e "${RED}❌ 不支持的包管理器${NC}"
            exit 1
        fi
        
        echo "使用包管理器: $PKG_MANAGER"
        
        if [[ "$PKG_MANAGER" == "apt" ]]; then
            sudo apt update
            sudo apt install -y \
                git zip unzip openjdk-8-jdk python3-pip \
                autoconf libtool pkg-config zlib1g-dev \
                libncurses5-dev libncursesw5-dev libtinfo5 \
                cmake libffi-dev libssl-dev \
                build-essential libsdl2-dev libsdl2-image-dev \
                libsdl2-mixer-dev libsdl2-ttf-dev libportmidi-dev \
                libswscale-dev libavformat-dev libavcodec-dev \
                zlib1g-dev bc
        fi
        
    elif [[ "$OS" == "macos" ]]; then
        # macOS使用Homebrew
        if ! command -v brew &> /dev/null; then
            echo -e "${YELLOW}⚠️ Homebrew未安装，正在安装...${NC}"
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        fi
        
        brew install python@3.9 git autoconf automake libtool pkg-config
        brew install --cask adoptopenjdk8
    fi
    
    echo -e "${GREEN}✅ 系统依赖安装完成${NC}"
}

# 设置Python环境
setup_python_env() {
    echo -e "${BLUE}🐍 设置Python环境...${NC}"
    
    # 升级pip
    python3 -m pip install --user --upgrade pip
    
    # 安装buildozer和相关工具
    python3 -m pip install --user buildozer cython
    
    # 安装Kivy
    python3 -m pip install --user "kivy[base]==2.1.0"
    python3 -m pip install --user kivymd==1.1.1
    
    # 安装项目依赖
    if [ -f "requirements_mobile.txt" ]; then
        python3 -m pip install --user -r requirements_mobile.txt
    else
        echo -e "${YELLOW}⚠️ requirements_mobile.txt不存在，跳过项目依赖安装${NC}"
    fi
    
    echo -e "${GREEN}✅ Python环境设置完成${NC}"
}

# 设置Android SDK
setup_android_sdk() {
    echo -e "${BLUE}📱 设置Android SDK...${NC}"
    
    # 设置Android SDK路径
    export ANDROID_HOME="$HOME/Android/Sdk"
    export PATH="$PATH:$ANDROID_HOME/tools:$ANDROID_HOME/platform-tools"
    export PATH="$PATH:$ANDROID_HOME/cmdline-tools/latest/bin"
    
    # 创建SDK目录
    mkdir -p "$ANDROID_HOME"
    cd "$ANDROID_HOME"
    
    # 下载Android SDK命令行工具
    if [ ! -d "cmdline-tools" ]; then
        echo "下载Android SDK命令行工具..."
        if [[ "$OS" == "linux" ]]; then
            wget -q https://dl.google.com/android/repository/commandlinetools-linux-9477386_latest.zip
            unzip -q commandlinetools-linux-9477386_latest.zip
        elif [[ "$OS" == "macos" ]]; then
            curl -s -O https://dl.google.com/android/repository/commandlinetools-mac-9477386_latest.zip
            unzip -q commandlinetools-mac-9477386_latest.zip
        fi
        
        mv cmdline-tools latest
        mkdir cmdline-tools
        mv latest cmdline-tools/
        rm -f commandlinetools-*.zip
    fi
    
    # 安装SDK组件
    echo "安装SDK组件..."
    yes | "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" --licenses > /dev/null 2>&1
    "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" "platforms;android-33" > /dev/null
    "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" "build-tools;33.0.0" > /dev/null
    "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" "ndk;25.2.9519653" > /dev/null
    
    # 添加环境变量到shell配置
    SHELL_RC="$HOME/.bashrc"
    if [[ "$OS" == "macos" ]]; then
        SHELL_RC="$HOME/.zshrc"
    fi
    
    if ! grep -q "ANDROID_HOME" "$SHELL_RC"; then
        echo "" >> "$SHELL_RC"
        echo "# Android SDK" >> "$SHELL_RC"
        echo "export ANDROID_HOME=\$HOME/Android/Sdk" >> "$SHELL_RC"
        echo "export PATH=\$PATH:\$ANDROID_HOME/tools:\$ANDROID_HOME/platform-tools" >> "$SHELL_RC"
        echo "export PATH=\$PATH:\$ANDROID_HOME/cmdline-tools/latest/bin" >> "$SHELL_RC"
    fi
    
    cd - > /dev/null
    echo -e "${GREEN}✅ Android SDK设置完成${NC}"
}

# 验证buildozer配置
verify_buildozer_config() {
    echo -e "${BLUE}🔧 验证buildozer配置...${NC}"
    
    if [ ! -f "buildozer.spec" ]; then
        echo -e "${YELLOW}⚠️ buildozer.spec不存在，正在创建...${NC}"
        buildozer init
        
        # 自定义配置
        sed -i "s/title = My Application/title = $PROJECT_NAME/" buildozer.spec
        sed -i "s/package.name = myapp/package.name = $PACKAGE_NAME/" buildozer.spec
        sed -i "s/package.domain = org.example/package.domain = com.tradingbot/" buildozer.spec
        
        echo -e "${GREEN}✅ buildozer.spec创建完成${NC}"
    else
        echo -e "${GREEN}✅ buildozer.spec已存在${NC}"
    fi
    
    # 检查主要配置项
    if grep -q "mobile_trading_bot.py" buildozer.spec; then
        echo -e "${GREEN}✅ 入口文件配置正确${NC}"
    else
        echo -e "${YELLOW}⚠️ 请检查buildozer.spec中的source.main配置${NC}"
    fi
}

# 构建调试版APK
build_debug_apk() {
    echo -e "${BLUE}🔨 构建调试版APK...${NC}"
    echo -e "${YELLOW}⏳ 这可能需要20-60分钟，请耐心等待...${NC}"
    
    # 设置环境变量
    export ANDROID_HOME="$HOME/Android/Sdk"
    export PATH="$PATH:$ANDROID_HOME/tools:$ANDROID_HOME/platform-tools"
    export PATH="$PATH:$ANDROID_HOME/cmdline-tools/latest/bin"
    
    # 开始构建
    start_time=$(date +%s)
    
    if buildozer android debug; then
        end_time=$(date +%s)
        duration=$((end_time - start_time))
        minutes=$((duration / 60))
        seconds=$((duration % 60))
        
        echo -e "${GREEN}✅ APK构建成功！${NC}"
        echo -e "${GREEN}📱 构建时间: ${minutes}分${seconds}秒${NC}"
        
        # 显示APK信息
        if [ -d "bin" ]; then
            APK_FILE=$(find bin -name "*.apk" -type f | head -1)
            if [ -n "$APK_FILE" ]; then
                APK_SIZE=$(du -h "$APK_FILE" | cut -f1)
                echo -e "${GREEN}📦 APK文件: $APK_FILE${NC}"
                echo -e "${GREEN}📏 文件大小: $APK_SIZE${NC}"
            fi
        fi
        
        return 0
    else
        echo -e "${RED}❌ APK构建失败${NC}"
        return 1
    fi
}

# 安装APK到设备
install_apk() {
    echo -e "${BLUE}📲 安装APK到设备...${NC}"
    
    # 检查ADB连接
    if command -v adb &> /dev/null; then
        DEVICES=$(adb devices | grep -v "List of devices" | grep "device$" | wc -l)
        
        if [ $DEVICES -eq 0 ]; then
            echo -e "${YELLOW}⚠️ 没有检测到Android设备${NC}"
            echo -e "${YELLOW}请确保：${NC}"
            echo -e "${YELLOW}1. 设备已通过USB连接${NC}"
            echo -e "${YELLOW}2. 已开启USB调试模式${NC}"
            echo -e "${YELLOW}3. 已授权此电脑的调试权限${NC}"
            return 1
        fi
        
        echo -e "${GREEN}✅ 检测到 $DEVICES 个设备${NC}"
        
        # 查找APK文件
        APK_FILE=$(find bin -name "*.apk" -type f | head -1)
        if [ -n "$APK_FILE" ]; then
            echo "正在安装: $APK_FILE"
            if adb install "$APK_FILE"; then
                echo -e "${GREEN}✅ APK安装成功！${NC}"
                echo -e "${GREEN}🎉 您现在可以在设备上运行应用了${NC}"
                return 0
            else
                echo -e "${RED}❌ APK安装失败${NC}"
                return 1
            fi
        else
            echo -e "${RED}❌ 找不到APK文件${NC}"
            return 1
        fi
    else
        echo -e "${YELLOW}⚠️ ADB未安装，无法自动安装APK${NC}"
        echo -e "${YELLOW}请手动将APK文件传输到设备并安装${NC}"
        return 1
    fi
}

# 清理构建文件
cleanup_build() {
    echo -e "${BLUE}🧹 清理构建文件...${NC}"
    
    if [ -d ".buildozer" ]; then
        echo "清理.buildozer目录..."
        rm -rf .buildozer
    fi
    
    echo -e "${GREEN}✅ 清理完成${NC}"
}

# 显示使用帮助
show_help() {
    echo "Android交易应用构建脚本"
    echo ""
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -h, --help     显示此帮助信息"
    echo "  -c, --clean    清理构建文件"
    echo "  -f, --full     完整构建流程"
    echo "  -q, --quick    快速构建(跳过环境检查)"
    echo "  -i, --install  构建并安装到设备"
    echo ""
    echo "示例:"
    echo "  $0 -f          # 完整构建流程"
    echo "  $0 -q          # 快速构建"
    echo "  $0 -i          # 构建并安装"
    echo "  $0 -c          # 清理构建文件"
}

# 主函数
main() {
    echo -e "${BLUE}🤖 Android交易应用构建器${NC}"
    echo -e "${BLUE}================================${NC}"
    
    # 解析命令行参数
    FULL_BUILD=false
    QUICK_BUILD=false
    INSTALL_APK=false
    CLEAN_BUILD=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -c|--clean)
                CLEAN_BUILD=true
                shift
                ;;
            -f|--full)
                FULL_BUILD=true
                shift
                ;;
            -q|--quick)
                QUICK_BUILD=true
                shift
                ;;
            -i|--install)
                INSTALL_APK=true
                shift
                ;;
            *)
                echo -e "${RED}❌ 未知选项: $1${NC}"
                show_help
                exit 1
                ;;
        esac
    done
    
    # 执行清理
    if [ "$CLEAN_BUILD" = true ]; then
        cleanup_build
        exit 0
    fi
    
    # 执行构建流程
    if [ "$FULL_BUILD" = true ]; then
        check_system
        install_system_deps
        setup_python_env
        setup_android_sdk
        verify_buildozer_config
        
        if build_debug_apk; then
            if [ "$INSTALL_APK" = true ]; then
                install_apk
            fi
        fi
        
    elif [ "$QUICK_BUILD" = true ] || [ "$INSTALL_APK" = true ]; then
        verify_buildozer_config
        
        if build_debug_apk; then
            if [ "$INSTALL_APK" = true ]; then
                install_apk
            fi
        fi
        
    else
        echo -e "${YELLOW}请指定构建选项，使用 -h 查看帮助${NC}"
        show_help
        exit 1
    fi
    
    echo -e "${GREEN}🎉 构建流程完成！${NC}"
}

# 运行主函数
main "$@"
