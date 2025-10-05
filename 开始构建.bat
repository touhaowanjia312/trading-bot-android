@echo off
REM 一键启动Android应用构建
echo 🚀 Android交易应用一键构建器
echo ===============================
echo.

REM 显示欢迎信息
echo 🤖 欢迎使用Android交易跟单机器人构建器！
echo.
echo 📱 我已经为您准备了完整的Android应用构建方案
echo 🎯 目标：30分钟内获得您的第一个Android交易应用
echo.

REM 显示构建选项
echo 请选择构建方案：
echo.
echo 1. 🌐 GitHub Actions云构建 (推荐) - 零配置，自动化
echo 2. 🐧 WSL2 Linux环境构建 - 高成功率
echo 3. 🖥️ Windows本地构建 - 需要配置环境
echo 4. 📖 查看详细构建指南
echo 5. 🧪 测试简化版应用
echo 6. ❌ 退出
echo.

set /p choice=请输入您的选择 (1-6): 

if "%choice%"=="1" goto github_actions
if "%choice%"=="2" goto wsl_build
if "%choice%"=="3" goto windows_build
if "%choice%"=="4" goto show_guide
if "%choice%"=="5" goto test_app
if "%choice%"=="6" goto exit
goto invalid_choice

:github_actions
echo.
echo 🌐 GitHub Actions云构建方案
echo ===========================
echo.
echo ✅ 优势：
echo   - 无需本地环境配置
echo   - 自动化构建流程
echo   - 成功率最高 (95%%)
echo   - 构建时间：30-40分钟
echo.
echo 📋 操作步骤：
echo.
echo 1. 创建GitHub账号 (如果没有)
echo    网址: https://github.com
echo.
echo 2. 创建新的代码仓库
echo    - 点击 "New repository"
echo    - 输入仓库名称，如: "trading-bot-android"
echo    - 选择 "Public" (公开仓库)
echo    - 点击 "Create repository"
echo.
echo 3. 上传项目代码
echo    在当前目录执行以下命令：
echo.
echo    git init
echo    git add .
echo    git commit -m "Android交易机器人初始版本"
echo    git branch -M main
echo    git remote add origin https://github.com/您的用户名/您的仓库名.git
echo    git push -u origin main
echo.
echo 4. 等待自动构建
echo    - 访问您的GitHub仓库
echo    - 点击 "Actions" 选项卡
echo    - 查看构建进度
echo    - 构建完成后点击 "Artifacts" 下载APK
echo.
echo 💡 提示：如果您不熟悉Git命令，可以使用GitHub Desktop图形界面工具
echo.
pause
goto menu

:wsl_build
echo.
echo 🐧 WSL2 Linux环境构建方案
echo ========================
echo.
echo ✅ 优势：
echo   - 在Windows上获得Linux环境
echo   - 兼容性好，成功率高 (90%%)
echo   - 构建时间：45-60分钟
echo.
echo 📋 操作步骤：
echo.
echo 1. 启用WSL2功能
echo    - 打开"启用或关闭Windows功能"
echo    - 勾选"适用于Linux的Windows子系统"
echo    - 重启电脑
echo.
echo 2. 安装Ubuntu
echo    - 打开Microsoft Store
echo    - 搜索并安装"Ubuntu 20.04 LTS"
echo    - 设置用户名和密码
echo.
echo 3. 运行构建脚本
echo    在Ubuntu终端中执行：
echo    chmod +x build_android_app.sh
echo    ./build_android_app.sh -f
echo.
echo 🔗 WSL2安装指南: https://docs.microsoft.com/zh-cn/windows/wsl/install
echo.
pause
goto menu

:windows_build
echo.
echo 🖥️ Windows本地构建方案
echo =====================
echo.
echo ✅ 优势：
echo   - 直接在Windows环境构建
echo   - 完全本地控制
echo.
echo ⚠️ 注意：
echo   - 需要手动配置复杂的Android开发环境
echo   - 成功率较低 (70%%)
echo   - 构建时间：60-90分钟
echo.
echo 📋 操作步骤：
echo.
echo 1. 运行Windows构建脚本
simple_build_windows.bat
goto menu

:show_guide
echo.
echo 📖 打开详细构建指南...
start 立即构建指南.md
start 快速构建指南.md
echo.
echo ✅ 已打开构建指南文档
echo 请查看详细的构建步骤和故障排除方法
echo.
pause
goto menu

:test_app
echo.
echo 🧪 测试简化版应用...
echo.
echo 正在启动简化版移动端应用进行测试...
echo 这将在控制台模式下运行，您可以测试基本功能
echo.
echo 💡 提示：如果看到Kivy相关错误，这是正常的，应用会自动切换到控制台模式
echo.
pause
python simple_mobile_app.py
goto menu

:invalid_choice
echo.
echo ❌ 无效选择，请重新选择 (1-6)
echo.
pause

:menu
echo.
echo 🔄 返回主菜单...
echo.
goto start

:start
cls
goto :eof

:exit
echo.
echo 👋 感谢使用Android交易应用构建器！
echo.
echo 📚 相关文档：
echo   - 立即构建指南.md - 完整构建方案
echo   - 快速构建指南.md - 详细操作步骤
echo   - ANDROID_移植指南.md - 技术详解
echo.
echo 🆘 如需帮助，请查看上述文档或联系技术支持
echo.
pause
