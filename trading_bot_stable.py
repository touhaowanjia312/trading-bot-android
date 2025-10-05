#!/usr/bin/env python3
"""
稳定版交易机器人
带有状态显示和错误处理
"""

import os
import sys
import asyncio
import signal
from pathlib import Path
from datetime import datetime
import re

sys.path.insert(0, str(Path(__file__).parent))

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("TradingBot")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class StableTradingBot:
    def __init__(self):
        self.running = False
        self.telegram_client = None
        self.target_channel = None
        self.trade_count = 0
        self.last_message_time = None
        
        # 配置
        self.api_id = os.getenv('TELEGRAM_API_ID')
        self.api_hash = os.getenv('TELEGRAM_API_HASH')
        self.trade_amount = float(os.getenv('DEFAULT_TRADE_AMOUNT', '2.0'))
        self.leverage = int(os.getenv('DEFAULT_LEVERAGE', '20'))
        
        # 状态标志
        self.connected = False
        self.monitoring = False
    
    def print_status_header(self):
        """打印状态头部"""
        print("\n" + "="*80)
        print("🚀 Telegram交易跟单机器人")
        print("="*80)
        print(f"⏰ 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"💰 交易金额: {self.trade_amount}U")
        print(f"📈 杠杆倍数: {self.leverage}x")
        print("="*80)
    
    def print_status(self, message, status="INFO"):
        """打印状态信息"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        status_icons = {
            "INFO": "ℹ️",
            "SUCCESS": "✅",
            "ERROR": "❌",
            "WARNING": "⚠️",
            "TRADE": "💰"
        }
        icon = status_icons.get(status, "ℹ️")
        print(f"[{timestamp}] {icon} {message}")
    
    async def initialize(self):
        """初始化机器人"""
        try:
            self.print_status_header()
            self.print_status("正在初始化交易机器人...")
            
            from telethon import TelegramClient
            
            # 创建客户端
            self.print_status("连接Telegram服务器...")
            self.telegram_client = TelegramClient('trading_session', self.api_id, self.api_hash)
            
            # 连接
            await self.telegram_client.connect()
            
            # 检查认证
            if not await self.telegram_client.is_user_authorized():
                self.print_status("需要认证，请先运行认证程序", "ERROR")
                return False
            
            self.connected = True
            self.print_status("Telegram连接成功", "SUCCESS")
            
            # 查找目标频道
            self.print_status("正在查找目标频道...")
            
            found_channels = []
            async for dialog in self.telegram_client.iter_dialogs():
                if dialog.is_channel:
                    title = dialog.title
                    if 'Seven' in title and ('司' in title or 'VIP' in title):
                        found_channels.append({
                            'entity': dialog.entity,
                            'title': title,
                            'id': dialog.id,
                            'subscribers': getattr(dialog.entity, 'participants_count', 'N/A')
                        })
            
            if not found_channels:
                self.print_status("未找到匹配的频道", "ERROR")
                return False
            
            # 使用第一个匹配的频道
            channel_info = found_channels[0]
            self.target_channel = channel_info['entity']
            
            self.print_status(f"找到目标频道: {channel_info['title']}", "SUCCESS")
            self.print_status(f"频道ID: {channel_info['id']}")
            self.print_status(f"订阅者: {channel_info['subscribers']}")
            
            self.print_status("机器人初始化完成", "SUCCESS")
            return True
            
        except Exception as e:
            self.print_status(f"初始化失败: {e}", "ERROR")
            return False
    
    def parse_signal(self, message):
        """解析交易信号"""
        if not message:
            return None
        
        # 基础市价信号: #币种 市價多/空
        match = re.search(r'#(\w+)\s+市[價价]([多空])', message)
        if match:
            symbol = match.group(1).upper()
            direction = match.group(2)
            
            # 标准化币种
            if not symbol.endswith('USDT'):
                symbol = f"{symbol}USDT"
            
            side = 'buy' if direction == '多' else 'sell'
            
            # 提取止盈止损
            stop_loss = None
            take_profit = None
            
            # 查找止损
            sl_match = re.search(r'止[损損]:\s*(\d+(?:\.\d+)?)', message)
            if sl_match:
                stop_loss = float(sl_match.group(1))
            
            # 查找止盈
            tp_match = re.search(r'第一止[盈贏]:\s*(\d+(?:\.\d+)?)', message)
            if tp_match:
                take_profit = float(tp_match.group(1))
            
            return {
                'symbol': symbol,
                'side': side,
                'direction_cn': '做多' if side == 'buy' else '做空',
                'amount': self.trade_amount,
                'leverage': self.leverage,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'raw_message': message
            }
        
        return None
    
    async def execute_trade(self, signal):
        """执行交易"""
        try:
            self.trade_count += 1
            
            # 显示交易信息
            print("\n" + "🎯" + "="*78)
            self.print_status(f"执行交易 #{self.trade_count}", "TRADE")
            print(f"   📊 币种: {signal['symbol']}")
            print(f"   📈 方向: {'🟢 ' + signal['direction_cn'] if signal['side'] == 'buy' else '🔴 ' + signal['direction_cn']}")
            print(f"   💰 金额: {signal['amount']}U")
            print(f"   📊 杠杆: {signal['leverage']}x")
            
            if signal['stop_loss']:
                print(f"   🛡️  止损: {signal['stop_loss']}")
            
            if signal['take_profit']:
                print(f"   🎯 止盈: {signal['take_profit']}")
            
            # 这里应该调用真实的Bitget API
            # 现在显示模拟交易
            self.print_status("模拟交易执行成功", "SUCCESS")
            print("🎯" + "="*78)
            
            return True
            
        except Exception as e:
            self.print_status(f"交易执行失败: {e}", "ERROR")
            return False
    
    async def handle_new_message(self, event):
        """处理新消息"""
        try:
            message = event.message
            if not message.text:
                return
            
            # 更新最后消息时间
            self.last_message_time = datetime.now()
            
            # 获取发送者信息
            sender = await message.get_sender()
            sender_name = getattr(sender, 'first_name', 'Unknown') if sender else 'Unknown'
            
            # 显示收到的消息
            self.print_status(f"收到消息 [{sender_name}]: {message.text}")
            
            # 解析信号
            signal = self.parse_signal(message.text)
            
            if signal:
                self.print_status("检测到交易信号!", "SUCCESS")
                await self.execute_trade(signal)
            
        except Exception as e:
            self.print_status(f"处理消息失败: {e}", "ERROR")
    
    async def start_monitoring(self):
        """开始监控"""
        try:
            from telethon import events
            
            self.print_status("开始监控频道消息...", "SUCCESS")
            self.monitoring = True
            
            # 注册消息处理器
            @self.telegram_client.on(events.NewMessage(chats=self.target_channel))
            async def message_handler(event):
                await self.handle_new_message(event)
            
            # 显示监控状态
            print("\n" + "👀" + "="*78)
            print("🎯 监控状态: 活跃")
            print(f"📺 监控频道: {self.target_channel.title}")
            print("💡 等待交易信号...")
            print("💡 检测格式: #币种 市價多/空")
            print("⚠️  按 Ctrl+C 停止监控")
            print("👀" + "="*78)
            
            # 保持运行
            await self.telegram_client.run_until_disconnected()
            
        except Exception as e:
            self.print_status(f"监控失败: {e}", "ERROR")
    
    async def stop(self):
        """停止机器人"""
        self.print_status("正在停止机器人...", "WARNING")
        self.running = False
        self.monitoring = False
        
        if self.telegram_client and self.connected:
            await self.telegram_client.disconnect()
            self.connected = False
        
        self.print_status("机器人已停止", "SUCCESS")
        print("👋 感谢使用!")


async def main():
    """主函数"""
    bot = StableTradingBot()
    
    # 信号处理
    def signal_handler(signum, frame):
        print(f"\n⚠️  接收到停止信号...")
        asyncio.create_task(bot.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # 初始化
        if not await bot.initialize():
            print("❌ 初始化失败，程序退出")
            return
        
        # 开始监控
        await bot.start_monitoring()
        
    except KeyboardInterrupt:
        print(f"\n⚠️  用户中断程序")
    except Exception as e:
        print(f"❌ 程序异常: {e}")
    finally:
        await bot.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n👋 程序被中断")
    except Exception as e:
        print(f"❌ 程序错误: {e}")
