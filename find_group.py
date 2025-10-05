#!/usr/bin/env python3
"""
查找Telegram群组ID
"""

import os
import sys
import asyncio
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(name)s | %(levelname)s | %(message)s')
logger = logging.getLogger("GroupFinder")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    logger.warning("python-dotenv not installed")


async def find_groups():
    """查找所有群组"""
    try:
        from telethon import TelegramClient
        
        api_id = os.getenv('TELEGRAM_API_ID')
        api_hash = os.getenv('TELEGRAM_API_HASH')
        
        client = TelegramClient('temp_session', api_id, api_hash)
        await client.connect()
        
        if not await client.is_user_authorized():
            logger.error("未认证，请先运行主程序进行认证")
            return
        
        print("\n📋 您的所有群组和频道:")
        print("=" * 70)
        
        groups = []
        async for dialog in client.iter_dialogs():
            if dialog.is_group or dialog.is_channel:
                group_info = {
                    'id': dialog.id,
                    'title': dialog.title,
                    'type': 'Channel' if dialog.is_channel else 'Group',
                    'participants': getattr(dialog.entity, 'participants_count', 'N/A')
                }
                groups.append(group_info)
        
        if not groups:
            print("❌ 未找到任何群组")
            return
        
        for i, group in enumerate(groups, 1):
            print(f"{i:2d}. {group['title']}")
            print(f"    ID: {group['id']}")
            print(f"    类型: {group['type']}")
            print(f"    成员: {group['participants']}")
            print()
        
        print("💡 找到您要监控的群组后，将其ID复制到.env文件的TELEGRAM_GROUP_ID中")
        print("例如: TELEGRAM_GROUP_ID=-1001234567890")
        
        await client.disconnect()
        
    except Exception as e:
        logger.error(f"查找群组失败: {e}")


if __name__ == "__main__":
    asyncio.run(find_groups())
