@echo off
REM Windows Android开发环境安装脚本

echo 🚀 开始安装Android开发环境...

REM 检查Python版本
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python未安装，请先安装Python 3.8+
    pause
    exit /b 1
)

REM 安装Python依赖
echo 🐍 安装Python依赖...
pip install --upgrade pip
pip install buildozer cython

REM 安装Kivy (Windows版本)
echo 🎨 安装Kivy框架...
pip install kivy[base]==2.1.0
pip install kivymd==1.1.1

REM 安装项目依赖
echo 📱 安装项目依赖...
pip install -r requirements_mobile.txt

REM 创建Android开发目录
echo 🔧 创建Android开发目录...
if not exist "%USERPROFILE%\Android\Sdk" mkdir "%USERPROFILE%\Android\Sdk"

REM 设置环境变量
echo 🔧 配置环境变量...
setx ANDROID_HOME "%USERPROFILE%\Android\Sdk"
setx PATH "%PATH%;%USERPROFILE%\Android\Sdk\tools;%USERPROFILE%\Android\Sdk\platform-tools"

echo ✅ 基础环境安装完成！
echo.
echo 📋 手动完成以下步骤：
echo.
echo 1. 下载并安装Android Studio:
echo    https://developer.android.com/studio
echo.
echo 2. 在Android Studio中安装：
echo    - Android SDK Platform 33
echo    - Android SDK Build-Tools 33.0.0
echo    - Android NDK 25.2.9519653
echo.
echo 3. 安装Java JDK 8:
echo    https://www.oracle.com/java/technologies/javase/javase8-archive-downloads.html
echo.
echo 4. 重启命令提示符以加载新的环境变量
echo.
echo 5. 验证安装: buildozer --version
echo.
echo ⚠️  Windows用户建议使用WSL2进行Android开发
echo    或者考虑使用GitHub Actions进行云构建

pause
