@echo off
chcp 65001 >nul
cls
echo.
echo ========================================
echo    Android交易应用构建器
echo ========================================
echo.
echo 我推荐使用GitHub Actions云构建，这是最简单的方案：
echo.
echo 【方案1：GitHub Actions云构建】（推荐）
echo   优势：无需配置环境，成功率95%%，30-40分钟完成
echo.
echo 【方案2：本地构建】
echo   需要配置复杂的Android开发环境
echo.
echo ========================================
echo.
set /p choice=请选择 (1=云构建, 2=本地构建): 

if "%choice%"=="1" goto cloud_build
if "%choice%"=="2" goto local_build
goto invalid

:cloud_build
cls
echo.
echo ========================================
echo    GitHub Actions云构建指南
echo ========================================
echo.
echo 步骤1：创建GitHub账号
echo   访问 https://github.com 注册账号
echo.
echo 步骤2：创建代码仓库
echo   - 点击右上角 "+" 选择 "New repository"
echo   - 仓库名：trading-bot-android
echo   - 选择 "Public"（公开）
echo   - 点击 "Create repository"
echo.
echo 步骤3：上传代码
echo   方法A：使用GitHub Desktop（推荐新手）
echo   - 下载安装 GitHub Desktop
echo   - 登录账号后选择 "Add an Existing Repository"
echo   - 选择当前文件夹并发布
echo.
echo   方法B：使用Git命令
echo   git init
echo   git add .
echo   git commit -m "初始版本"
echo   git branch -M main
echo   git remote add origin https://github.com/用户名/仓库名.git
echo   git push -u origin main
echo.
echo 步骤4：等待自动构建
echo   - 代码上传后，访问GitHub仓库
echo   - 点击 "Actions" 查看构建进度
echo   - 30-40分钟后下载APK文件
echo.
echo ========================================
pause
goto end

:local_build
cls
echo.
echo ========================================
echo    本地构建方案
echo ========================================
echo.
echo 注意：本地构建比较复杂，建议使用云构建
echo.
echo 如果您坚持本地构建，需要：
echo 1. 安装Android Studio
echo 2. 配置Android SDK
echo 3. 安装Java JDK 8
echo 4. 安装Python依赖包
echo.
set /p confirm=确定要本地构建吗？(y/n): 
if /i "%confirm%"=="y" goto start_local
goto cloud_build

:start_local
echo.
echo 开始本地构建...
simple_build_windows.bat
goto end

:invalid
echo 无效选择，请重新运行
pause
goto end

:end
echo.
echo 构建器已退出
pause
