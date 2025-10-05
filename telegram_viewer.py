#!/usr/bin/env python3
"""
Telegram群组消息查看工具
用于查看群组中的真实交易信号格式，以便优化信号解析器
"""

import sys
import asyncio
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from src.telegram.auth import TelegramAuth
from src.utils.logger import telegram_logger


class TelegramViewer:
    """Telegram消息查看器"""
    
    def __init__(self):
        self.auth = TelegramAuth()
        self.target_group = None
    
    async def initialize(self):
        """初始化连接"""
        print("🔗 初始化Telegram连接...")
        
        # 初始化客户端
        if not await self.auth.initialize_client():
            print("❌ 客户端初始化失败")
            return False
        
        # 认证
        print("🔐 开始认证流程...")
        while True:
            # 尝试自动认证
            auth_result = await self.auth.authenticate()
            
            if auth_result['success']:
                print("✅ 认证成功！")
                break
            elif auth_result['need_phone_code']:
                # 需要输入验证码
                phone_code = input("📱 请输入手机验证码: ")
                auth_result = await self.auth.authenticate(phone_code=phone_code)
                
                if auth_result['success']:
                    print("✅ 认证成功！")
                    break
                elif auth_result['need_password']:
                    # 需要两步验证密码
                    password = input("🔒 请输入两步验证密码: ")
                    auth_result = await self.auth.authenticate(phone_code=phone_code, password=password)
                    
                    if auth_result['success']:
                        print("✅ 认证成功！")
                        break
                    else:
                        print(f"❌ 认证失败: {auth_result.get('error', '未知错误')}")
                        return False
                else:
                    print(f"❌ 认证失败: {auth_result.get('error', '未知错误')}")
                    return False
            else:
                print(f"❌ 认证失败: {auth_result.get('error', '未知错误')}")
                return False
        
        # 获取用户信息
        user_info = await self.auth.get_me()
        if user_info:
            print(f"👋 欢迎, {user_info.get('first_name', 'User')}!")
        
        return True
    
    async def list_groups(self):
        """列出所有群组"""
        print("\n📋 您的群组列表:")
        print("-" * 50)
        
        groups = []
        async for dialog in self.auth.client.iter_dialogs():
            if dialog.is_group or dialog.is_channel:
                groups.append({
                    'id': dialog.id,
                    'title': dialog.title,
                    'type': 'Channel' if dialog.is_channel else 'Group',
                    'participants': getattr(dialog.entity, 'participants_count', 'N/A')
                })
        
        if not groups:
            print("❌ 未找到任何群组")
            return []
        
        for i, group in enumerate(groups, 1):
            print(f"{i:2d}. {group['title']}")
            print(f"    ID: {group['id']}")
            print(f"    类型: {group['type']}")
            print(f"    成员: {group['participants']}")
            print()
        
        return groups
    
    async def select_group(self, groups):
        """选择要监控的群组"""
        while True:
            try:
                choice = input("请选择群组编号 (输入数字): ")
                index = int(choice) - 1
                
                if 0 <= index < len(groups):
                    selected = groups[index]
                    self.target_group = await self.auth.client.get_entity(selected['id'])
                    print(f"✅ 已选择群组: {selected['title']}")
                    return selected
                else:
                    print("❌ 无效的选择，请重新输入")
            except ValueError:
                print("❌ 请输入有效的数字")
            except KeyboardInterrupt:
                print("\n👋 退出程序")
                return None
    
    async def view_recent_messages(self, limit=50):
        """查看最近的消息"""
        if not self.target_group:
            print("❌ 未选择群组")
            return
        
        print(f"\n📨 最近 {limit} 条消息:")
        print("=" * 80)
        
        messages = []
        try:
            async for message in self.auth.client.iter_messages(self.target_group, limit=limit):
                if message.text:
                    sender = await message.get_sender()
                    sender_name = self._get_sender_name(sender)
                    
                    msg_data = {
                        'id': message.id,
                        'date': message.date.strftime('%Y-%m-%d %H:%M:%S') if message.date else 'N/A',
                        'sender': sender_name,
                        'text': message.text,
                        'is_signal': self._might_be_signal(message.text)
                    }
                    messages.append(msg_data)
        
        except Exception as e:
            print(f"❌ 获取消息失败: {e}")
            return []
        
        # 按时间正序显示（最早的在上面）
        messages.reverse()
        
        signal_count = 0
        for msg in messages:
            # 标记可能的交易信号
            signal_indicator = "🎯 [信号]" if msg['is_signal'] else ""
            
            print(f"[{msg['date']}] {msg['sender']} {signal_indicator}")
            print(f"💬 {msg['text']}")
            print("-" * 80)
            
            if msg['is_signal']:
                signal_count += 1
        
        print(f"\n📊 统计: 共 {len(messages)} 条消息，其中 {signal_count} 条可能是交易信号")
        
        return messages
    
    def _get_sender_name(self, sender):
        """获取发送者名称"""
        if not sender:
            return "Unknown"
        
        if hasattr(sender, 'username') and sender.username:
            return f"@{sender.username}"
        elif hasattr(sender, 'first_name') and sender.first_name:
            name = sender.first_name
            if hasattr(sender, 'last_name') and sender.last_name:
                name += f" {sender.last_name}"
            return name
        elif hasattr(sender, 'title'):
            return sender.title
        else:
            return f"User_{getattr(sender, 'id', 'Unknown')}"
    
    def _might_be_signal(self, text):
        """简单判断是否可能是交易信号"""
        if not text:
            return False
        
        # 检查常见的信号关键词
        signal_keywords = [
            '#', '市價', '市价', '多', '空', 'long', 'short', 'buy', 'sell',
            '止损', '止損', '目标', '目標', '止盈', '止贏'
        ]
        
        text_lower = text.lower()
        return any(keyword.lower() in text_lower or keyword in text for keyword in signal_keywords)
    
    async def analyze_signals(self, messages):
        """分析信号格式"""
        signals = [msg for msg in messages if msg['is_signal']]
        
        if not signals:
            print("❌ 未找到交易信号")
            return
        
        print(f"\n🔍 信号格式分析 (共 {len(signals)} 条信号):")
        print("=" * 80)
        
        # 按格式分类
        formats = {}
        for signal in signals:
            text = signal['text']
            
            # 简单的格式识别
            if '#' in text and ('市價' in text or '市价' in text):
                if '多' in text:
                    direction = '做多'
                elif '空' in text:
                    direction = '做空'
                else:
                    direction = '未知'
                
                # 检查是否有止损止盈
                has_sl = '止损' in text or '止損' in text
                has_tp = '目标' in text or '目標' in text or '止盈' in text or '止贏' in text
                
                format_key = f"#{direction}"
                if has_sl:
                    format_key += "+止损"
                if has_tp:
                    format_key += "+止盈"
                
                if format_key not in formats:
                    formats[format_key] = []
                formats[format_key].append(text)
        
        # 显示格式分析结果
        for format_type, examples in formats.items():
            print(f"\n📋 {format_type} 格式 ({len(examples)} 条):")
            print("-" * 40)
            for i, example in enumerate(examples[:3], 1):  # 只显示前3个例子
                print(f"{i}. {example}")
            if len(examples) > 3:
                print(f"   ... 还有 {len(examples) - 3} 条类似信号")
        
        print(f"\n💡 建议:")
        print("1. 根据以上真实格式优化信号解析器")
        print("2. 特别注意止损止盈的具体格式")
        print("3. 确认币种符号的写法")
        print("4. 注意金额单位的表示方法")


async def main():
    """主函数"""
    print("=" * 60)
    print("    Telegram群组消息查看工具")
    print("    用于分析真实的交易信号格式")
    print("=" * 60)
    print()
    
    # 提示用户配置
    print("📝 使用前请确保:")
    print("1. 已在 .env 文件中配置了Telegram API信息")
    print("2. 手机能够接收Telegram验证码")
    print("3. 已加入要分析的交易群组")
    print()
    
    if input("是否继续? (y/n): ").lower() != 'y':
        print("👋 退出程序")
        return
    
    viewer = TelegramViewer()
    
    # 初始化连接
    if not await viewer.initialize():
        print("❌ 初始化失败")
        return
    
    try:
        # 列出群组
        groups = await viewer.list_groups()
        if not groups:
            return
        
        # 选择群组
        selected_group = await viewer.select_group(groups)
        if not selected_group:
            return
        
        # 查看消息
        print(f"\n🔍 正在获取 {selected_group['title']} 的消息...")
        messages = await viewer.view_recent_messages(limit=100)
        
        if messages:
            # 分析信号格式
            await viewer.analyze_signals(messages)
            
            print(f"\n✅ 分析完成！")
            print("现在您可以根据真实的信号格式来优化解析器了。")
        
    except KeyboardInterrupt:
        print("\n👋 程序被用户中断")
    except Exception as e:
        print(f"❌ 程序执行出错: {e}")
    finally:
        # 清理资源
        await viewer.auth.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
