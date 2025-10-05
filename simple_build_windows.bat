@echo off
REM 简化版Windows Android构建脚本
setlocal enabledelayedexpansion

echo 🚀 简化版Android应用构建器
echo ==============================

REM 检查是否安装了必要的工具
echo 📋 检查构建环境...

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python未安装
    echo 请从 https://www.python.org/downloads/ 下载安装Python 3.8+
    pause
    exit /b 1
)
echo ✅ Python已安装

REM 检查pip
pip --version >nul 2>&1
if errorlevel 1 (
    echo ❌ pip未安装
    pause
    exit /b 1
)
echo ✅ pip已安装

REM 安装必要的Python包
echo 🐍 安装必要的Python包...
echo 正在安装buildozer...
pip install buildozer

echo 正在安装Kivy...
pip install kivy[base]==2.1.0

echo 正在安装Cython...
pip install cython

REM 检查buildozer是否可用
buildozer --version >nul 2>&1
if errorlevel 1 (
    echo ❌ buildozer安装失败
    echo 请检查网络连接并重试
    pause
    exit /b 1
)
echo ✅ buildozer安装成功

REM 显示Android环境要求
echo.
echo 📱 Android开发环境要求:
echo ================================
echo 由于Windows环境的复杂性，建议使用以下方案之一：
echo.
echo 方案1: WSL2 + Linux环境 (推荐)
echo   1. 启用WSL2功能
echo   2. 安装Ubuntu 20.04
echo   3. 在WSL2中运行Linux构建脚本
echo.
echo 方案2: 使用Docker
echo   1. 安装Docker Desktop
echo   2. 使用预配置的Android构建镜像
echo.
echo 方案3: 云构建服务
echo   1. 使用GitHub Actions
echo   2. 使用Travis CI或其他CI/CD服务
echo.
echo 方案4: 手动配置 (复杂)
echo   1. 安装Android Studio
echo   2. 配置Android SDK
echo   3. 安装JDK 8
echo   4. 配置环境变量
echo.

REM 询问用户选择
echo 请选择您要使用的方案:
echo 1. 尝试在当前Windows环境构建 (可能失败)
echo 2. 生成WSL2构建脚本
echo 3. 生成Docker构建脚本
echo 4. 显示手动配置指南
echo 5. 退出
echo.
set /p choice=请输入选择 (1-5): 

if "%choice%"=="1" goto windows_build
if "%choice%"=="2" goto wsl_script
if "%choice%"=="3" goto docker_script
if "%choice%"=="4" goto manual_guide
if "%choice%"=="5" goto end
goto invalid_choice

:windows_build
echo.
echo 🔨 尝试在Windows环境构建...
echo ⚠️ 注意: 这可能会失败，因为Android构建在Windows上比较复杂
echo.

REM 检查Android环境
if not defined ANDROID_HOME (
    echo ❌ ANDROID_HOME环境变量未设置
    echo 请先安装Android Studio并配置环境变量
    goto manual_guide
)

echo 📱 检测到Android环境: %ANDROID_HOME%

REM 初始化buildozer
if not exist buildozer.spec (
    echo 🔧 初始化buildozer配置...
    buildozer init
)

echo 🔨 开始构建APK...
echo ⏳ 这可能需要很长时间，请耐心等待...
echo.

buildozer android debug

if errorlevel 1 (
    echo ❌ 构建失败
    echo.
    echo 建议尝试其他方案：
    echo 1. 使用WSL2 + Linux环境
    echo 2. 使用Docker构建
    echo 3. 使用云构建服务
    goto end
) else (
    echo ✅ 构建成功！
    if exist bin (
        for %%f in (bin\*.apk) do (
            echo 📦 APK文件: %%f
        )
    )
)
goto end

:wsl_script
echo.
echo 📝 生成WSL2构建脚本...

REM 创建WSL2构建脚本
echo #!/bin/bash > build_in_wsl.sh
echo # WSL2中的Android构建脚本 >> build_in_wsl.sh
echo echo "🚀 在WSL2中构建Android应用..." >> build_in_wsl.sh
echo. >> build_in_wsl.sh
echo # 更新系统 >> build_in_wsl.sh
echo sudo apt update >> build_in_wsl.sh
echo. >> build_in_wsl.sh
echo # 安装依赖 >> build_in_wsl.sh
echo sudo apt install -y python3 python3-pip git zip unzip openjdk-8-jdk >> build_in_wsl.sh
echo sudo apt install -y build-essential libsdl2-dev libsdl2-image-dev >> build_in_wsl.sh
echo sudo apt install -y libsdl2-mixer-dev libsdl2-ttf-dev libportmidi-dev >> build_in_wsl.sh
echo. >> build_in_wsl.sh
echo # 安装Python包 >> build_in_wsl.sh
echo pip3 install --user buildozer cython "kivy[base]==2.1.0" >> build_in_wsl.sh
echo. >> build_in_wsl.sh
echo # 设置Android SDK >> build_in_wsl.sh
echo export ANDROID_HOME=$HOME/Android/Sdk >> build_in_wsl.sh
echo mkdir -p $ANDROID_HOME >> build_in_wsl.sh
echo cd $ANDROID_HOME >> build_in_wsl.sh
echo wget https://dl.google.com/android/repository/commandlinetools-linux-9477386_latest.zip >> build_in_wsl.sh
echo unzip commandlinetools-linux-9477386_latest.zip >> build_in_wsl.sh
echo mv cmdline-tools latest ^&^& mkdir cmdline-tools ^&^& mv latest cmdline-tools/ >> build_in_wsl.sh
echo yes ^| $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager --licenses >> build_in_wsl.sh
echo $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager "platforms;android-33" >> build_in_wsl.sh
echo $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager "build-tools;33.0.0" >> build_in_wsl.sh
echo $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager "ndk;25.2.9519653" >> build_in_wsl.sh
echo. >> build_in_wsl.sh
echo # 返回项目目录并构建 >> build_in_wsl.sh
echo cd /mnt/c/project/project1 >> build_in_wsl.sh
echo buildozer android debug >> build_in_wsl.sh

echo ✅ WSL2构建脚本已生成: build_in_wsl.sh
echo.
echo 📋 使用步骤:
echo 1. 启用WSL2功能
echo 2. 安装Ubuntu 20.04
echo 3. 在WSL2中运行: bash build_in_wsl.sh
goto end

:docker_script
echo.
echo 📝 生成Docker构建脚本...

REM 创建Dockerfile
echo FROM ubuntu:20.04 > Dockerfile
echo. >> Dockerfile
echo ENV DEBIAN_FRONTEND=noninteractive >> Dockerfile
echo. >> Dockerfile
echo RUN apt-get update ^&^& apt-get install -y \ >> Dockerfile
echo     python3 python3-pip git zip unzip openjdk-8-jdk \ >> Dockerfile
echo     build-essential libsdl2-dev libsdl2-image-dev \ >> Dockerfile
echo     libsdl2-mixer-dev libsdl2-ttf-dev libportmidi-dev \ >> Dockerfile
echo     wget curl >> Dockerfile
echo. >> Dockerfile
echo RUN pip3 install buildozer cython "kivy[base]==2.1.0" >> Dockerfile
echo. >> Dockerfile
echo WORKDIR /app >> Dockerfile
echo COPY . /app >> Dockerfile
echo. >> Dockerfile
echo CMD ["buildozer", "android", "debug"] >> Dockerfile

REM 创建docker-compose.yml
echo version: '3.8' > docker-compose.yml
echo services: >> docker-compose.yml
echo   android-builder: >> docker-compose.yml
echo     build: . >> docker-compose.yml
echo     volumes: >> docker-compose.yml
echo       - .:/app >> docker-compose.yml
echo       - android-sdk:/root/Android >> docker-compose.yml
echo     environment: >> docker-compose.yml
echo       - ANDROID_HOME=/root/Android/Sdk >> docker-compose.yml
echo volumes: >> docker-compose.yml
echo   android-sdk: >> docker-compose.yml

echo ✅ Docker构建文件已生成
echo.
echo 📋 使用步骤:
echo 1. 安装Docker Desktop
echo 2. 运行: docker-compose up
goto end

:manual_guide
echo.
echo 📋 手动配置Android开发环境指南
echo ================================
echo.
echo 1. 安装Android Studio
echo    下载地址: https://developer.android.com/studio
echo    安装完成后启动Android Studio
echo.
echo 2. 配置Android SDK
echo    - 打开Android Studio
echo    - 进入 Tools ^> SDK Manager
echo    - 安装 Android SDK Platform 33
echo    - 安装 Android SDK Build-Tools 33.0.0
echo    - 安装 Android NDK 25.2.9519653
echo.
echo 3. 安装Java JDK 8
echo    下载地址: https://www.oracle.com/java/technologies/javase/javase8-archive-downloads.html
echo.
echo 4. 设置环境变量
echo    ANDROID_HOME = C:\Users\%USERNAME%\AppData\Local\Android\Sdk
echo    JAVA_HOME = C:\Program Files\Java\jdk1.8.0_XXX
echo    PATH 添加: %%ANDROID_HOME%%\tools;%%ANDROID_HOME%%\platform-tools
echo.
echo 5. 重启命令提示符并运行
echo    buildozer android debug
echo.
goto end

:invalid_choice
echo ❌ 无效选择，请重新运行脚本
goto end

:end
echo.
echo 🎉 脚本执行完成！
echo.
echo 💡 提示:
echo - 如果Windows构建失败，强烈推荐使用WSL2方案
echo - WSL2提供了接近Linux的构建环境，成功率更高
echo - Docker方案适合有Docker经验的用户
echo.
pause
