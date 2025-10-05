#!/usr/bin/env python3
"""
快速Telegram群组检查工具
快速连接并查看群组消息格式
"""

import os
import sys
import asyncio
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

async def quick_check():
    """快速检查Telegram群组"""
    print("🚀 快速Telegram群组检查")
    print("=" * 40)
    
    # 先尝试加载环境变量
    try:
        from dotenv import load_dotenv
        if load_dotenv():
            print("✅ 已加载 .env 文件")
        else:
            print("⚠️  未找到 .env 文件")
    except ImportError:
        print("⚠️  python-dotenv 未安装，尝试手动读取 .env")
        # 手动读取.env文件
        env_file = Path('.env')
        if env_file.exists():
            with open(env_file, encoding='utf-8') as f:
                for line in f:
                    if '=' in line and not line.strip().startswith('#'):
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value
            print("✅ 手动加载了 .env 文件")
        else:
            print("❌ 未找到 .env 文件")
    
    # 检查配置
    print("\n📋 检查配置...")
    
    api_id = os.getenv('TELEGRAM_API_ID')
    api_hash = os.getenv('TELEGRAM_API_HASH')
    phone = os.getenv('TELEGRAM_PHONE_NUMBER')
    group_id = os.getenv('TELEGRAM_GROUP_ID')
    
    missing_configs = []
    if not api_id or api_id == 'your_api_id':
        missing_configs.append('TELEGRAM_API_ID')
    if not api_hash or api_hash == 'your_api_hash':
        missing_configs.append('TELEGRAM_API_HASH')
    if not phone or phone == '+86your_phone_number':
        missing_configs.append('TELEGRAM_PHONE_NUMBER')
    if not group_id or group_id == 'your_group_id':
        missing_configs.append('TELEGRAM_GROUP_ID')
    
    if missing_configs:
        print("❌ 缺少以下配置:")
        for config in missing_configs:
            print(f"   - {config}")
        print("\n📝 请按以下步骤配置:")
        print("1. 复制 config/trading_config_example.env 为 .env")
        print("2. 填入您的Telegram API信息:")
        print("   - API ID 和 API Hash: 从 https://my.telegram.org 获取")
        print("   - 手机号: 格式如 +8613800138000")
        print("   - 群组ID: 可以是 @群组用户名 或 -1001234567890")
        print("3. 重新运行: python quick_telegram_check.py")
        return
    
    print("✅ 配置检查完成")
    print(f"   - API ID: {api_id}")
    print(f"   - 手机号: {phone}")
    print(f"   - 群组: {group_id}")
    
    # 尝试连接
    try:
        from telethon import TelegramClient
        
        print(f"\n🔗 连接Telegram...")
        client = TelegramClient('temp_session', api_id, api_hash)
        await client.connect()
        
        # 检查认证状态
        if not await client.is_user_authorized():
            print("📱 需要手机验证码，请运行完整版工具:")
            print("   python telegram_viewer.py")
            await client.disconnect()
            return
        
        print("✅ 已连接并认证")
        
        # 获取群组
        try:
            group = await client.get_entity(group_id)
            print(f"✅ 找到群组: {group.title}")
            
            # 获取最近几条消息
            print(f"\n📨 最近5条消息:")
            print("-" * 50)
            
            count = 0
            async for message in client.iter_messages(group, limit=10):
                if message.text and count < 5:
                    sender = await message.get_sender()
                    sender_name = getattr(sender, 'first_name', 'Unknown') if sender else 'Unknown'
                    
                    # 检查是否可能是交易信号
                    is_signal = any(keyword in message.text for keyword in ['#', '市價', '市价', '多', '空'])
                    signal_mark = "🎯 " if is_signal else ""
                    
                    print(f"{signal_mark}[{message.date.strftime('%H:%M')}] {sender_name}:")
                    print(f"   {message.text[:100]}{'...' if len(message.text) > 100 else ''}")
                    print()
                    count += 1
            
            print("✅ 连接测试成功！")
            print("\n💡 下一步:")
            print("1. 如果看到交易信号，请运行完整分析: python telegram_viewer.py")
            print("2. 根据真实信号格式优化解析器")
            print("3. 配置完成后可以开始跟单: python main.py")
            
        except Exception as e:
            print(f"❌ 获取群组失败: {e}")
            print("💡 可能的原因:")
            print("   - 群组ID不正确")
            print("   - 未加入该群组")
            print("   - 群组是私有的")
        
        await client.disconnect()
        
    except ImportError:
        print("❌ 缺少依赖库，请先安装:")
        print("   pip install telethon")
    except Exception as e:
        print(f"❌ 连接失败: {e}")


if __name__ == "__main__":
    asyncio.run(quick_check())
