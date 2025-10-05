#!/usr/bin/env python3
"""
API配置助手
帮助用户设置.env文件中的API信息
"""

import os
from pathlib import Path


def setup_env_file():
    """设置.env文件"""
    print("🔧 API配置助手")
    print("=" * 50)
    print("请按照提示输入您的API信息")
    print()
    
    # 当前的.env文件内容
    env_content = """# ==============================================
# Telegram交易信号跟单系统 - 配置文件
# ==============================================

# Telegram API配置 (必填)
TELEGRAM_API_ID={api_id}
TELEGRAM_API_HASH={api_hash}
TELEGRAM_PHONE_NUMBER={phone}
TELEGRAM_SESSION_NAME=trading_bot

# 监控的Telegram群组 (必填)
TELEGRAM_GROUP_ID={group_id}

# Bitget API配置 (必填)
BITGET_API_KEY={bitget_key}
BITGET_SECRET_KEY={bitget_secret}
BITGET_PASSPHRASE={bitget_passphrase}
BITGET_SANDBOX=false

# ============ 核心交易配置 ============
# 每单固定交易金额（USDT）
DEFAULT_TRADE_AMOUNT=2.0

# 默认杠杆倍数
DEFAULT_LEVERAGE=20

# 是否使用交易员信号中的止盈止损
USE_TRADER_SIGNALS_FOR_TP_SL=true

# ============ 风险管理配置 ============
# 最大持仓金额限制
MAX_POSITION_SIZE=1000.0

# 单笔交易风险百分比
RISK_PERCENTAGE=2.0

# 默认止损百分比（当交易员未提供时使用）
STOP_LOSS_PERCENTAGE=5.0

# 默认止盈百分比（当交易员未提供时使用）
TAKE_PROFIT_PERCENTAGE=10.0

# ============ 系统配置 ============
# 数据库配置
DATABASE_URL=sqlite:///data/trading.db

# 日志配置
LOG_LEVEL=INFO
LOG_FILE_PATH=data/logs/trading_bot.log

# 通知配置
ENABLE_DESKTOP_NOTIFICATIONS=true
ENABLE_SOUND_NOTIFICATIONS=true
"""
    
    print("1. Telegram API配置")
    print("-" * 30)
    print("访问 https://my.telegram.org 获取API信息")
    
    api_id = input("请输入 API ID (数字): ").strip()
    api_hash = input("请输入 API Hash: ").strip()
    phone = input("请输入手机号 (如 +8613800138000): ").strip()
    group_id = input("请输入群组ID (如 @your_group 或 -1001234567890): ").strip()
    
    print("\n2. Bitget API配置")
    print("-" * 30)
    print("在Bitget交易所API管理页面创建API")
    
    bitget_key = input("请输入 Bitget API Key: ").strip()
    bitget_secret = input("请输入 Bitget Secret Key: ").strip()
    bitget_passphrase = input("请输入 Bitget Passphrase: ").strip()
    
    # 填充模板
    filled_content = env_content.format(
        api_id=api_id,
        api_hash=api_hash,
        phone=phone,
        group_id=group_id,
        bitget_key=bitget_key,
        bitget_secret=bitget_secret,
        bitget_passphrase=bitget_passphrase
    )
    
    # 写入文件
    with open('.env', 'w', encoding='utf-8') as f:
        f.write(filled_content)
    
    print("\n✅ .env文件已更新！")
    print("现在可以启动交易机器人了")
    
    return True


def check_current_config():
    """检查当前配置"""
    if not os.path.exists('.env'):
        print("❌ .env文件不存在")
        return False
    
    print("📋 当前配置检查:")
    print("-" * 30)
    
    try:
        with open('.env', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查关键配置
        checks = [
            ('TELEGRAM_API_ID', '你的API_ID'),
            ('TELEGRAM_API_HASH', '你的API_HASH'),
            ('TELEGRAM_PHONE_NUMBER', '+86你的手机号'),
            ('TELEGRAM_GROUP_ID', '你的群组ID'),
            ('BITGET_API_KEY', '你的Bitget_API_Key'),
            ('BITGET_SECRET_KEY', '你的Bitget_Secret_Key'),
            ('BITGET_PASSPHRASE', '你的Bitget_Passphrase')
        ]
        
        all_configured = True
        
        for key, placeholder in checks:
            if placeholder in content or key not in content:
                print(f"❌ {key}: 未配置")
                all_configured = False
            else:
                print(f"✅ {key}: 已配置")
        
        return all_configured
        
    except Exception as e:
        print(f"❌ 读取配置文件失败: {e}")
        return False


def main():
    """主函数"""
    print("🚀 交易机器人配置助手")
    print("=" * 50)
    
    # 检查当前配置
    if check_current_config():
        print("\n✅ 配置已完成，可以启动机器人了！")
        print("运行: python simple_trading_bot.py")
        return
    
    print("\n需要配置API信息")
    
    if input("\n是否现在配置? (y/n): ").lower() == 'y':
        if setup_env_file():
            print("\n🎉 配置完成！")
            print("现在可以运行: python simple_trading_bot.py")
    else:
        print("请手动编辑 .env 文件填入API信息")


if __name__ == "__main__":
    main()
