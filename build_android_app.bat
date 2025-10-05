@echo off
REM Windows Android应用构建脚本
setlocal enabledelayedexpansion

echo 🚀 开始构建Android交易应用...
echo ==================================

REM 项目信息
set PROJECT_NAME=交易跟单机器人
set PACKAGE_NAME=tradingbot
set APP_VERSION=1.0

REM 检查Python环境
:check_python
echo 📋 检查Python环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python未安装，请先安装Python 3.8+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo ✅ Python版本: %PYTHON_VERSION%

REM 检查pip
pip --version >nul 2>&1
if errorlevel 1 (
    echo ❌ pip未安装
    pause
    exit /b 1
)

REM 安装Python依赖
:install_python_deps
echo 🐍 安装Python依赖...
echo 正在升级pip...
python -m pip install --upgrade pip

echo 正在安装buildozer...
pip install buildozer cython

echo 正在安装Kivy...
pip install "kivy[base]==2.1.0"
pip install kivymd==1.1.1

echo 正在安装项目依赖...
if exist requirements_mobile.txt (
    pip install -r requirements_mobile.txt
) else (
    echo ⚠️ requirements_mobile.txt不存在，跳过项目依赖安装
)

REM 检查Android开发环境
:check_android_env
echo 📱 检查Android开发环境...

REM 检查ANDROID_HOME环境变量
if not defined ANDROID_HOME (
    echo ❌ ANDROID_HOME环境变量未设置
    echo 请先安装Android Studio并设置环境变量
    echo.
    echo 手动设置步骤：
    echo 1. 下载并安装Android Studio
    echo 2. 设置ANDROID_HOME环境变量指向SDK路径
    echo 3. 将SDK的tools和platform-tools添加到PATH
    echo.
    echo 示例路径：
    echo ANDROID_HOME=C:\Users\%USERNAME%\AppData\Local\Android\Sdk
    echo PATH=%ANDROID_HOME%\tools;%ANDROID_HOME%\platform-tools
    echo.
    pause
    exit /b 1
) else (
    echo ✅ ANDROID_HOME: %ANDROID_HOME%
)

REM 检查Java环境
java -version >nul 2>&1
if errorlevel 1 (
    echo ❌ Java未安装，请安装JDK 8
    echo 下载地址: https://www.oracle.com/java/technologies/javase/javase8-archive-downloads.html
    pause
    exit /b 1
) else (
    echo ✅ Java环境已安装
)

REM 验证buildozer配置
:verify_buildozer_config
echo 🔧 验证buildozer配置...

if not exist buildozer.spec (
    echo ⚠️ buildozer.spec不存在，正在创建...
    buildozer init
    
    REM 自定义配置（Windows下需要手动编辑）
    echo ⚠️ 请手动编辑buildozer.spec文件：
    echo 1. 将title改为: %PROJECT_NAME%
    echo 2. 将package.name改为: %PACKAGE_NAME%
    echo 3. 将package.domain改为: com.tradingbot
    echo 4. 将source.main改为: mobile_trading_bot.py
    echo.
    echo 按任意键继续...
    pause >nul
) else (
    echo ✅ buildozer.spec已存在
)

REM 构建APK
:build_apk
echo 🔨 开始构建APK...
echo ⏳ 这可能需要30-90分钟，请耐心等待...
echo.

REM 记录开始时间
set START_TIME=%time%

REM 开始构建
buildozer android debug

if errorlevel 1 (
    echo ❌ APK构建失败
    echo.
    echo 常见问题解决方案：
    echo 1. 检查网络连接是否稳定
    echo 2. 确保有足够的磁盘空间（至少10GB）
    echo 3. 检查防火墙是否阻止了下载
    echo 4. 尝试使用VPN或更换网络
    echo.
    pause
    exit /b 1
) else (
    REM 记录结束时间
    set END_TIME=%time%
    echo ✅ APK构建成功！
    
    REM 显示APK信息
    if exist bin (
        for %%f in (bin\*.apk) do (
            echo 📦 APK文件: %%f
            for %%s in (%%f) do echo 📏 文件大小: %%~zs 字节
        )
    )
)

REM 询问是否安装到设备
:ask_install
echo.
set /p INSTALL_CHOICE=是否要安装APK到设备？(y/n): 
if /i "%INSTALL_CHOICE%"=="y" goto install_apk
if /i "%INSTALL_CHOICE%"=="yes" goto install_apk
goto end

REM 安装APK到设备
:install_apk
echo 📲 安装APK到设备...

REM 检查ADB
adb version >nul 2>&1
if errorlevel 1 (
    echo ❌ ADB未找到，请确保Android SDK已正确安装
    goto end
)

REM 检查设备连接
adb devices | find "device" >nul
if errorlevel 1 (
    echo ⚠️ 没有检测到Android设备
    echo 请确保：
    echo 1. 设备已通过USB连接
    echo 2. 已开启USB调试模式
    echo 3. 已授权此电脑的调试权限
    goto end
)

echo ✅ 检测到Android设备

REM 查找并安装APK
for %%f in (bin\*.apk) do (
    echo 正在安装: %%f
    adb install "%%f"
    if errorlevel 1 (
        echo ❌ APK安装失败
    ) else (
        echo ✅ APK安装成功！
        echo 🎉 您现在可以在设备上运行应用了
    )
    goto end
)

echo ❌ 找不到APK文件

:end
echo.
echo 🎉 构建流程完成！
echo.
echo 📋 后续步骤：
echo 1. 如果构建成功，APK文件在bin目录中
echo 2. 可以手动将APK传输到手机并安装
echo 3. 首次运行时需要授权相关权限
echo 4. 配置API密钥后即可开始使用
echo.

REM 询问是否清理构建文件
set /p CLEAN_CHOICE=是否要清理构建文件以节省空间？(y/n): 
if /i "%CLEAN_CHOICE%"=="y" goto cleanup
if /i "%CLEAN_CHOICE%"=="yes" goto cleanup
goto final_end

:cleanup
echo 🧹 清理构建文件...
if exist .buildozer (
    rmdir /s /q .buildozer
    echo ✅ 清理完成
)

:final_end
echo.
echo 感谢使用Android交易应用构建器！
pause
