#!/usr/bin/env python3
"""
列出所有Telegram群组
"""

import os
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(name)s | %(levelname)s | %(message)s')
logger = logging.getLogger("GroupLister")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


async def list_all_groups():
    """列出所有群组"""
    try:
        from telethon import TelegramClient
        
        api_id = os.getenv('TELEGRAM_API_ID')
        api_hash = os.getenv('TELEGRAM_API_HASH')
        
        # 使用已有的session
        client = TelegramClient('trading_session', api_id, api_hash)
        await client.connect()
        
        if not await client.is_user_authorized():
            logger.error("未认证，请先运行交易机器人进行认证")
            return
        
        print("\n📋 您的所有对话（群组、频道、私聊）:")
        print("=" * 80)
        
        groups = []
        channels = []
        users = []
        
        async for dialog in client.iter_dialogs():
            if dialog.is_group:
                groups.append({
                    'id': dialog.id,
                    'title': dialog.title,
                    'participants': getattr(dialog.entity, 'participants_count', 'N/A')
                })
            elif dialog.is_channel:
                channels.append({
                    'id': dialog.id,
                    'title': dialog.title,
                    'participants': getattr(dialog.entity, 'participants_count', 'N/A')
                })
            elif dialog.is_user:
                users.append({
                    'id': dialog.id,
                    'title': dialog.title
                })
        
        # 显示群组
        if groups:
            print(f"\n🏘️  群组 ({len(groups)} 个):")
            print("-" * 50)
            for i, group in enumerate(groups, 1):
                print(f"{i:2d}. {group['title']}")
                print(f"    ID: {group['id']}")
                print(f"    成员: {group['participants']}")
                
                # 检查是否包含"Seven"和"司"等关键词
                if any(keyword in group['title'] for keyword in ['Seven', '司', 'VIP', '手工']):
                    print(f"    ⭐ 可能是目标群组!")
                print()
        
        # 显示频道
        if channels:
            print(f"\n📺 频道 ({len(channels)} 个):")
            print("-" * 50)
            for i, channel in enumerate(channels, 1):
                print(f"{i:2d}. {channel['title']}")
                print(f"    ID: {channel['id']}")
                print(f"    订阅: {channel['participants']}")
                
                # 检查是否包含关键词
                if any(keyword in channel['title'] for keyword in ['Seven', '司', 'VIP', '手工']):
                    print(f"    ⭐ 可能是目标频道!")
                print()
        
        print("\n💡 找到目标群组后:")
        print("1. 复制对应的ID（负数）")
        print("2. 更新.env文件中的TELEGRAM_GROUP_ID")
        print("3. 重新启动交易机器人")
        
        await client.disconnect()
        
    except Exception as e:
        logger.error(f"列出群组失败: {e}")


if __name__ == "__main__":
    asyncio.run(list_all_groups())
