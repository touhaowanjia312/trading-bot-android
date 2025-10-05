#!/usr/bin/env python3
"""
Telegram群组连接向导
帮助用户连接到Telegram群组并查看真实信号格式
"""

import os
import sys
import asyncio
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

async def connect_wizard():
    """连接向导"""
    print("🚀 Telegram群组连接向导")
    print("=" * 50)
    print("这个工具将帮助您连接到Telegram群组并查看真实的交易信号格式")
    print()
    
    # 检查配置文件
    env_file = Path('.env')
    if not env_file.exists():
        print("❌ 未找到 .env 配置文件")
        print("正在创建配置文件...")
        
        # 复制示例配置
        import shutil
        shutil.copy('config/trading_config_example.env', '.env')
        print("✅ 已创建 .env 配置文件")
    
    print("📝 请按以下步骤配置:")
    print()
    
    # 步骤1: API配置
    print("步骤1: 获取Telegram API信息")
    print("-" * 30)
    print("1. 访问: https://my.telegram.org")
    print("2. 登录您的Telegram账号")
    print("3. 点击 'API development tools'")
    print("4. 创建应用获取 api_id 和 api_hash")
    print()
    
    # 检查是否已配置
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        api_id = os.getenv('TELEGRAM_API_ID')
        api_hash = os.getenv('TELEGRAM_API_HASH')
        phone = os.getenv('TELEGRAM_PHONE_NUMBER')
        
        if api_id and api_id != '你的API_ID':
            print(f"✅ API ID: {api_id}")
        else:
            print("❌ 请在 .env 文件中填入您的 TELEGRAM_API_ID")
            
        if api_hash and api_hash != '你的API_HASH':
            print(f"✅ API Hash: {api_hash[:10]}...")
        else:
            print("❌ 请在 .env 文件中填入您的 TELEGRAM_API_HASH")
            
        if phone and phone != '+86你的手机号':
            print(f"✅ 手机号: {phone}")
        else:
            print("❌ 请在 .env 文件中填入您的 TELEGRAM_PHONE_NUMBER")
            
    except ImportError:
        print("⚠️  建议安装 python-dotenv: pip install python-dotenv")
    
    print()
    print("步骤2: 编辑配置文件")
    print("-" * 30)
    print("请用记事本打开项目文件夹中的 .env 文件，填入:")
    print("- TELEGRAM_API_ID=您的API_ID数字")
    print("- TELEGRAM_API_HASH=您的API_HASH字符串")  
    print("- TELEGRAM_PHONE_NUMBER=+86您的手机号")
    print("- TELEGRAM_GROUP_ID=您的群组ID或@群组用户名")
    print()
    
    # 询问是否继续
    if input("是否已完成配置? (y/n): ").lower() != 'y':
        print("请先完成配置，然后重新运行此工具")
        return
    
    # 重新加载配置
    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
    except ImportError:
        pass
    
    # 步骤3: 测试连接
    print("\n步骤3: 测试连接")
    print("-" * 30)
    
    try:
        from telethon import TelegramClient
        
        api_id = os.getenv('TELEGRAM_API_ID')
        api_hash = os.getenv('TELEGRAM_API_HASH')
        phone = os.getenv('TELEGRAM_PHONE_NUMBER')
        
        if not all([api_id, api_hash, phone]) or api_id == '你的API_ID':
            print("❌ 配置信息不完整，请检查 .env 文件")
            return
        
        print("🔗 正在连接Telegram...")
        client = TelegramClient('temp_session', api_id, api_hash)
        await client.connect()
        
        # 检查认证
        if not await client.is_user_authorized():
            print("📱 需要验证码认证")
            await client.send_code_request(phone)
            
            code = input("请输入收到的验证码: ")
            try:
                await client.sign_in(phone, code)
                print("✅ 认证成功!")
            except Exception as e:
                if 'password' in str(e).lower():
                    password = input("请输入两步验证密码: ")
                    await client.sign_in(password=password)
                    print("✅ 认证成功!")
                else:
                    print(f"❌ 认证失败: {e}")
                    return
        else:
            print("✅ 已认证")
        
        # 步骤4: 选择群组
        print("\n步骤4: 选择群组")
        print("-" * 30)
        
        groups = []
        print("📋 您的群组列表:")
        async for dialog in client.iter_dialogs():
            if dialog.is_group or dialog.is_channel:
                groups.append({
                    'id': dialog.id,
                    'title': dialog.title,
                    'type': 'Channel' if dialog.is_channel else 'Group'
                })
        
        if not groups:
            print("❌ 未找到任何群组")
            return
        
        for i, group in enumerate(groups, 1):
            print(f"{i:2d}. {group['title']} ({group['type']})")
        
        # 选择群组
        while True:
            try:
                choice = input(f"\n请选择群组编号 (1-{len(groups)}): ")
                index = int(choice) - 1
                if 0 <= index < len(groups):
                    selected = groups[index]
                    break
                else:
                    print("请输入有效的编号")
            except ValueError:
                print("请输入数字")
        
        # 步骤5: 查看消息
        print(f"\n步骤5: 查看 {selected['title']} 的消息")
        print("-" * 30)
        
        group_entity = await client.get_entity(selected['id'])
        
        print("📨 最近10条消息:")
        signals_found = []
        
        count = 0
        async for message in client.iter_messages(group_entity, limit=20):
            if message.text and count < 10:
                sender = await message.get_sender()
                sender_name = getattr(sender, 'first_name', 'Unknown') if sender else 'Unknown'
                
                # 检查是否可能是交易信号
                is_signal = any(keyword in message.text for keyword in ['#', '市價', '市价', '多', '空', '止损', '止盈', '目标'])
                
                if is_signal:
                    signals_found.append(message.text)
                    print(f"\n🎯 [{message.date.strftime('%m-%d %H:%M')}] {sender_name}:")
                    print(f"    {message.text}")
                else:
                    print(f"\n💬 [{message.date.strftime('%m-%d %H:%M')}] {sender_name}:")
                    print(f"    {message.text[:50]}{'...' if len(message.text) > 50 else ''}")
                
                count += 1
        
        # 分析信号格式
        if signals_found:
            print(f"\n🔍 发现 {len(signals_found)} 条可能的交易信号:")
            print("=" * 50)
            for i, signal in enumerate(signals_found, 1):
                print(f"{i}. {signal}")
            
            print(f"\n💡 请将这些真实的信号格式告诉开发者，以便优化解析器!")
            print("常见格式分析:")
            
            # 简单分析
            formats = set()
            for signal in signals_found:
                if '#' in signal:
                    if '市價多' in signal or '市价多' in signal:
                        formats.add("做多格式")
                    if '市價空' in signal or '市价空' in signal:
                        formats.add("做空格式")
                    if '止损' in signal:
                        formats.add("带止损")
                    if '目标' in signal or '止盈' in signal:
                        formats.add("带止盈")
            
            print(f"发现的格式类型: {', '.join(formats)}")
        else:
            print("❌ 未发现交易信号，可能需要:")
            print("1. 检查群组是否有交易信号")
            print("2. 确认信号格式是否包含关键词")
            print("3. 尝试查看更多历史消息")
        
        await client.disconnect()
        
        print(f"\n✅ 连接测试完成!")
        print("下一步:")
        print("1. 将发现的信号格式告诉开发者")
        print("2. 开发者会根据真实格式优化解析器")
        print("3. 配置Bitget API后即可开始跟单")
        
    except ImportError:
        print("❌ 缺少telethon库，请安装: pip install telethon")
    except Exception as e:
        print(f"❌ 连接失败: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(connect_wizard())
    except KeyboardInterrupt:
        print("\n👋 用户中断")
    except Exception as e:
        print(f"❌ 程序出错: {e}")
