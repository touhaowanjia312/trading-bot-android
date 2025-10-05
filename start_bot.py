#!/usr/bin/env python3
"""
启动交易机器人 - 简化版
直接搜索频道名称
"""

import os
import sys
import asyncio
import signal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(name)s | %(levelname)s | %(message)s')
logger = logging.getLogger("TradingBot")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class TradingBot:
    def __init__(self):
        self.running = False
        self.telegram_client = None
        self.target_channel = None
        self.trade_count = 0
        
        # 配置
        self.api_id = os.getenv('TELEGRAM_API_ID')
        self.api_hash = os.getenv('TELEGRAM_API_HASH')
        self.trade_amount = float(os.getenv('DEFAULT_TRADE_AMOUNT', '2.0'))
        self.leverage = int(os.getenv('DEFAULT_LEVERAGE', '20'))
    
    async def initialize(self):
        """初始化"""
        try:
            from telethon import TelegramClient
            
            logger.info("🚀 启动交易机器人")
            
            # 连接Telegram
            self.telegram_client = TelegramClient('trading_session', self.api_id, self.api_hash)
            await self.telegram_client.connect()
            
            if not await self.telegram_client.is_user_authorized():
                logger.error("未认证，请先运行认证")
                return False
            
            logger.info("✅ Telegram连接成功")
            
            # 查找目标频道
            logger.info("🔍 查找目标频道...")
            
            async for dialog in self.telegram_client.iter_dialogs():
                if dialog.is_channel and 'Seven' in dialog.title and '司' in dialog.title:
                    self.target_channel = dialog.entity
                    logger.info(f"✅ 找到目标频道: {dialog.title}")
                    logger.info(f"   频道ID: {dialog.id}")
                    logger.info(f"   订阅者: {getattr(dialog.entity, 'participants_count', 'N/A')}")
                    break
            
            if not self.target_channel:
                logger.error("❌ 未找到目标频道")
                return False
            
            logger.info("✅ 机器人初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ 初始化失败: {e}")
            return False
    
    def parse_signal(self, message):
        """解析信号"""
        if not message:
            return None
        
        import re
        
        # 基础市价信号
        match = re.search(r'#(\w+)\s+市[價价]([多空])', message)
        if match:
            symbol = match.group(1).upper()
            direction = match.group(2)
            
            if not symbol.endswith('USDT'):
                symbol = f"{symbol}USDT"
            
            side = 'buy' if direction == '多' else 'sell'
            
            # 查找止盈止损
            stop_loss = None
            take_profit = None
            
            sl_match = re.search(r'止[损損]:\s*(\d+(?:\.\d+)?)', message)
            if sl_match:
                stop_loss = float(sl_match.group(1))
            
            tp_match = re.search(r'第一止[盈贏]:\s*(\d+(?:\.\d+)?)', message)
            if tp_match:
                take_profit = float(tp_match.group(1))
            
            return {
                'symbol': symbol,
                'side': side,
                'amount': self.trade_amount,
                'leverage': self.leverage,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'raw_message': message
            }
        
        return None
    
    async def execute_trade(self, signal):
        """模拟执行交易"""
        try:
            self.trade_count += 1
            
            logger.info("=" * 60)
            logger.info(f"💰 执行交易 #{self.trade_count}")
            logger.info(f"   币种: {signal['symbol']}")
            logger.info(f"   方向: {'🟢 做多' if signal['side'] == 'buy' else '🔴 做空'}")
            logger.info(f"   金额: {signal['amount']}U")
            logger.info(f"   杠杆: {signal['leverage']}x")
            
            if signal['stop_loss']:
                logger.info(f"   止损: {signal['stop_loss']}")
            
            if signal['take_profit']:
                logger.info(f"   止盈: {signal['take_profit']}")
            
            # 这里应该调用Bitget API
            # 现在只是模拟
            logger.info("✅ 模拟交易执行成功")
            logger.info("=" * 60)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 交易执行失败: {e}")
            return False
    
    async def handle_new_message(self, event):
        """处理新消息"""
        try:
            message = event.message
            if not message.text:
                return
            
            sender = await message.get_sender()
            sender_name = getattr(sender, 'first_name', 'Unknown') if sender else 'Unknown'
            
            logger.info(f"📨 [{sender_name}]: {message.text}")
            
            # 解析信号
            signal = self.parse_signal(message.text)
            
            if signal:
                logger.info(f"🎯 检测到交易信号!")
                await self.execute_trade(signal)
            
        except Exception as e:
            logger.error(f"❌ 处理消息失败: {e}")
    
    async def start_monitoring(self):
        """开始监控"""
        try:
            from telethon import events
            
            logger.info("👀 开始监控频道消息...")
            self.running = True
            
            # 注册消息处理器
            @self.telegram_client.on(events.NewMessage(chats=self.target_channel))
            async def message_handler(event):
                await self.handle_new_message(event)
            
            logger.info("✅ 监控已启动")
            await self.telegram_client.run_until_disconnected()
            
        except Exception as e:
            logger.error(f"❌ 监控失败: {e}")
    
    async def stop(self):
        """停止机器人"""
        logger.info("🛑 停止机器人...")
        self.running = False
        
        if self.telegram_client:
            await self.telegram_client.disconnect()
        
        logger.info("✅ 机器人已停止")


async def main():
    bot = TradingBot()
    
    def signal_handler(signum, frame):
        print(f"\n接收到停止信号...")
        asyncio.create_task(bot.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        if not await bot.initialize():
            return
        
        print("\n" + "="*60)
        print("🚀 交易跟单机器人已启动")
        print("="*60)
        print(f"📺 监控频道: {bot.target_channel.title}")
        print(f"💰 交易金额: {bot.trade_amount}U")
        print(f"📈 杠杆倍数: {bot.leverage}x")
        print("="*60)
        print("💡 检测到 #币种 市價多/空 格式将自动执行交易")
        print("按 Ctrl+C 停止")
        print("="*60)
        
        await bot.start_monitoring()
        
    except KeyboardInterrupt:
        print("\n👋 用户停止")
    except Exception as e:
        print(f"❌ 运行错误: {e}")
    finally:
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
