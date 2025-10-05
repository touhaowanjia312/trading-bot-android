#!/usr/bin/env python3
"""
配置测试脚本
"""

import sys
import os
sys.path.insert(0, '.')

from src.utils.config import config

def main():
    print("=" * 60)
    print("    Telegram交易信号跟单系统 - 配置测试")
    print("=" * 60)
    print()
    
    print("📊 当前配置摘要:")
    print(f"  - Telegram API ID: {'✅ 已配置' if config.telegram.api_id != 'your_api_id' else '❌ 未配置'}")
    print(f"  - Telegram 群组: {'✅ 已配置' if config.telegram.group_id != 'your_group_id' else '❌ 未配置'}")
    print(f"  - Bitget API: {'✅ 已配置' if config.bitget.api_key != 'your_bitget_api_key' else '❌ 未配置'}")
    print(f"  - 默认交易金额: {config.trading.default_trade_amount} USDT")
    print(f"  - 默认杠杆: {config.trading.default_leverage}x")
    print(f"  - 使用交易员止盈止损: {'✅ 是' if config.trading.use_trader_signals_for_tp_sl else '❌ 否'}")
    print(f"  - 风险百分比: {config.trading.risk_percentage}%")
    print(f"  - 数据库URL: {config.database.url}")
    print(f"  - Bitget 沙盒模式: {'✅ 开启' if config.bitget.sandbox else '❌ 关闭'}")
    
    # 验证配置逻辑
    is_valid, errors = config.validate_config(skip_required=True)
    
    print(f"\n🔍 配置逻辑验证:")
    if is_valid:
        print("✅ 所有配置参数格式正确")
    else:
        print("❌ 发现配置问题:")
        for error in errors:
            print(f"  - {error}")
    
    # 检查API配置状态
    print(f"\n🔑 API配置状态:")
    api_configured = (
        config.telegram.api_id != 'your_api_id' and
        config.bitget.api_key != 'your_bitget_api_key'
    )
    
    if api_configured:
        print("✅ API配置已完成，可以开始使用")
        print("\n🚀 下一步:")
        print("   1. 运行GUI模式: python main.py")
        print("   2. 运行控制台模式: python main.py --console")
        return True
    else:
        print("⚠️  API配置未完成，请按以下步骤配置:")
        print("   1. 复制 config/trading_config_example.env 为 .env")
        print("   2. 填入您的Telegram和Bitget API信息")
        print("   3. 重新运行测试: python test_config.py")
        print("\n📝 配置说明:")
        print("   - Telegram API: 访问 https://my.telegram.org 获取")
        print("   - Bitget API: 在Bitget交易所API管理页面创建")
        return False

if __name__ == "__main__":
    main()
