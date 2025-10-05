#!/bin/bash
# Android开发环境安装脚本

echo "🚀 开始安装Android开发环境..."

# 检查Python版本
python_version=$(python3 --version 2>&1 | grep -oP '(?<=Python )\d+\.\d+')
if [[ $(echo "$python_version >= 3.8" | bc -l) -eq 1 ]]; then
    echo "✅ Python版本检查通过: $python_version"
else
    echo "❌ Python版本过低，需要3.8+，当前版本: $python_version"
    exit 1
fi

# 安装系统依赖 (Ubuntu/Debian)
echo "📦 安装系统依赖..."
sudo apt update
sudo apt install -y \
    git zip unzip openjdk-8-jdk python3-pip \
    autoconf libtool pkg-config zlib1g-dev \
    libncurses5-dev libncursesw5-dev libtinfo5 \
    cmake libffi-dev libssl-dev \
    build-essential libsdl2-dev libsdl2-image-dev \
    libsdl2-mixer-dev libsdl2-ttf-dev libportmidi-dev \
    libswscale-dev libavformat-dev libavcodec-dev \
    zlib1g-dev

# 安装Python依赖
echo "🐍 安装Python依赖..."
pip3 install --user --upgrade pip
pip3 install --user buildozer cython

# 安装Kivy和相关包
echo "🎨 安装Kivy框架..."
pip3 install --user kivy[base]==2.1.0
pip3 install --user kivymd==1.1.1

# 安装项目依赖
echo "📱 安装项目依赖..."
pip3 install --user -r requirements_mobile.txt

# 设置Android SDK环境变量
echo "🔧 配置Android SDK..."
export ANDROID_HOME=$HOME/Android/Sdk
export PATH=$PATH:$ANDROID_HOME/tools:$ANDROID_HOME/platform-tools

# 创建Android SDK目录
mkdir -p $ANDROID_HOME

# 下载Android SDK命令行工具
echo "📥 下载Android SDK..."
cd $ANDROID_HOME
wget https://dl.google.com/android/repository/commandlinetools-linux-9477386_latest.zip
unzip commandlinetools-linux-9477386_latest.zip
mv cmdline-tools latest
mkdir cmdline-tools
mv latest cmdline-tools/

# 安装SDK组件
echo "📦 安装SDK组件..."
yes | $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager --licenses
$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager "platforms;android-33"
$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager "build-tools;33.0.0"
$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager "ndk;25.2.9519653"

# 添加环境变量到shell配置
echo "🔧 配置环境变量..."
cat >> ~/.bashrc << EOF

# Android SDK
export ANDROID_HOME=\$HOME/Android/Sdk
export PATH=\$PATH:\$ANDROID_HOME/tools:\$ANDROID_HOME/platform-tools
export PATH=\$PATH:\$ANDROID_HOME/cmdline-tools/latest/bin
EOF

echo "✅ Android开发环境安装完成！"
echo ""
echo "📋 下一步操作："
echo "1. 重新加载shell配置: source ~/.bashrc"
echo "2. 验证安装: buildozer --version"
echo "3. 初始化项目: buildozer init"
echo "4. 构建APK: buildozer android debug"
echo ""
echo "⚠️  注意事项："
echo "- 首次构建可能需要1-2小时下载依赖"
echo "- 确保有足够的磁盘空间(至少10GB)"
echo "- 构建过程中保持网络连接稳定"
