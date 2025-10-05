#!/usr/bin/env python3
"""
简化的交易跟单机器人
专门针对市价单交易，绕过复杂的数据库模型
"""

import os
import sys
import asyncio
import signal
from pathlib import Path
from datetime import datetime
from typing import Optional

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

# 基本的日志设置
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger("SimpleTradingBot")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    logger.warning("python-dotenv not installed, loading .env manually")
    env_file = Path('.env')
    if env_file.exists():
        with open(env_file, encoding='utf-8') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value


class SimpleTradingBot:
    """简化的交易机器人"""
    
    def __init__(self):
        self.running = False
        self.telegram_client = None
        self.trade_count = 0
        
        # 从环境变量加载配置
        self.api_id = os.getenv('TELEGRAM_API_ID')
        self.api_hash = os.getenv('TELEGRAM_API_HASH')
        self.phone = os.getenv('TELEGRAM_PHONE_NUMBER')
        self.group_id = os.getenv('TELEGRAM_GROUP_ID')
        
        self.bitget_api_key = os.getenv('BITGET_API_KEY')
        self.bitget_secret = os.getenv('BITGET_SECRET_KEY')
        self.bitget_passphrase = os.getenv('BITGET_PASSPHRASE')
        self.bitget_sandbox = os.getenv('BITGET_SANDBOX', 'false').lower() == 'true'
        
        self.trade_amount = float(os.getenv('DEFAULT_TRADE_AMOUNT', '2.0'))
        self.leverage = int(os.getenv('DEFAULT_LEVERAGE', '20'))
    
    async def initialize(self):
        """初始化机器人"""
        try:
            logger.info("🚀 启动简化交易机器人")
            
            # 检查配置
            if not all([self.api_id, self.api_hash, self.phone, self.group_id]):
                raise Exception("Telegram配置不完整")
            
            if not all([self.bitget_api_key, self.bitget_secret, self.bitget_passphrase]):
                raise Exception("Bitget配置不完整")
            
            # 初始化Telegram客户端
            from telethon import TelegramClient
            self.telegram_client = TelegramClient('trading_session', self.api_id, self.api_hash)
            
            await self.telegram_client.connect()
            
            # 检查认证
            if not await self.telegram_client.is_user_authorized():
                logger.info("需要认证...")
                await self.telegram_client.send_code_request(self.phone)
                code = input("请输入验证码: ")
                try:
                    await self.telegram_client.sign_in(self.phone, code)
                except Exception as e:
                    if 'password' in str(e).lower():
                        password = input("请输入两步验证密码: ")
                        await self.telegram_client.sign_in(password=password)
            
            logger.info("✅ Telegram连接成功")
            
            # 获取群组/频道
            try:
                # 尝试不同的方式获取实体
                if self.group_id.startswith('@'):
                    # 用户名格式
                    self.group_entity = await self.telegram_client.get_entity(self.group_id)
                else:
                    # 数字ID格式，尝试转换为整数
                    group_id_int = int(self.group_id)
                    self.group_entity = await self.telegram_client.get_entity(group_id_int)
                
                logger.info(f"✅ 找到目标: {self.group_entity.title}")
                logger.info(f"   类型: {'频道' if hasattr(self.group_entity, 'broadcast') and self.group_entity.broadcast else '群组'}")
                
            except Exception as e:
                logger.error(f"无法找到群组/频道 {self.group_id}: {e}")
                
                # 尝试从对话列表中查找
                logger.info("尝试从对话列表中查找...")
                found = False
                async for dialog in self.telegram_client.iter_dialogs():
                    if (dialog.is_group or dialog.is_channel) and str(dialog.id) == str(self.group_id):
                        self.group_entity = dialog.entity
                        logger.info(f"✅ 从对话列表找到: {dialog.title}")
                        found = True
                        break
                    elif hasattr(dialog.entity, 'title') and 'Seven' in dialog.entity.title and '司' in dialog.entity.title:
                        logger.info(f"发现可能的目标: {dialog.entity.title} (ID: {dialog.id})")
                        if input(f"是否使用此频道? (y/n): ").lower() == 'y':
                            self.group_entity = dialog.entity
                            found = True
                            break
                
                if not found:
                    raise Exception(f"无法找到群组/频道 {self.group_id}")
            
            # 测试Bitget连接（简化版本）
            logger.info("✅ Bitget配置已加载")
            
            logger.info("✅ 机器人初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ 初始化失败: {e}")
            return False
    
    def parse_signal(self, message: str) -> Optional[dict]:
        """简化的信号解析"""
        if not message:
            return None
        
        message = message.strip()
        
        # 检查是否是交易信号
        import re
        
        # 基础市价信号: #币种 市價多/空
        basic_pattern = r'#(\w+)\s+市[價价]([多空])'
        match = re.search(basic_pattern, message)
        
        if match:
            symbol = match.group(1).upper()
            direction = match.group(2)
            
            # 添加USDT后缀
            if not symbol.endswith('USDT'):
                symbol = f"{symbol}USDT"
            
            side = 'buy' if direction == '多' else 'sell'
            
            # 提取止盈止损（如果有）
            stop_loss = None
            take_profit = None
            
            # 提取止损
            sl_match = re.search(r'止[损損]:\s*(\d+(?:\.\d+)?)', message)
            if sl_match:
                stop_loss = float(sl_match.group(1))
            
            # 提取止盈
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
    
    async def execute_trade(self, signal: dict):
        """模拟交易执行"""
        try:
            logger.info(f"💰 模拟执行交易:")
            logger.info(f"   币种: {signal['symbol']}")
            logger.info(f"   方向: {'做多' if signal['side'] == 'buy' else '做空'}")
            logger.info(f"   金额: {signal['amount']}U")
            logger.info(f"   杠杆: {signal['leverage']}x")
            
            if signal['stop_loss']:
                logger.info(f"   止损: {signal['stop_loss']}")
            
            if signal['take_profit']:
                logger.info(f"   止盈: {signal['take_profit']}")
            
            # 这里应该是真实的Bitget API调用
            # 现在只是模拟
            self.trade_count += 1
            
            logger.info(f"✅ 模拟交易执行成功 (第{self.trade_count}笔)")
            
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
                logger.info(f"🎯 检测到交易信号: {signal['symbol']} {signal['side']}")
                
                # 执行交易
                success = await self.execute_trade(signal)
                
                if success:
                    logger.info("✅ 交易处理完成")
                else:
                    logger.error("❌ 交易处理失败")
            
        except Exception as e:
            logger.error(f"❌ 处理消息时出错: {e}")
    
    async def start_monitoring(self):
        """开始监控"""
        try:
            logger.info("👀 开始监控群组消息...")
            self.running = True
            
            # 注册新消息处理器
            from telethon import events
            
            @self.telegram_client.on(events.NewMessage(chats=self.group_entity))
            async def message_handler(event):
                await self.handle_new_message(event)
            
            # 保持运行
            logger.info("✅ 监控已启动，等待信号...")
            await self.telegram_client.run_until_disconnected()
            
        except Exception as e:
            logger.error(f"❌ 监控过程中出错: {e}")
    
    async def stop(self):
        """停止机器人"""
        logger.info("🛑 正在停止机器人...")
        self.running = False
        
        if self.telegram_client:
            await self.telegram_client.disconnect()
        
        logger.info("✅ 机器人已停止")


async def main():
    """主函数"""
    bot = SimpleTradingBot()
    
    # 设置信号处理
    def signal_handler(signum, frame):
        print(f"\n接收到信号 {signum}，正在停止...")
        asyncio.create_task(bot.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # 初始化
        if not await bot.initialize():
            print("❌ 初始化失败")
            return
        
        print("\n" + "="*60)
        print("🚀 简化交易跟单机器人已启动")
        print("="*60)
        print("📊 配置信息:")
        print(f"  - 交易金额: {bot.trade_amount}U")
        print(f"  - 杠杆倍数: {bot.leverage}x")
        print(f"  - 监控群组: {bot.group_id}")
        print(f"  - 沙盒模式: {'开启' if bot.bitget_sandbox else '关闭'}")
        print("="*60)
        print("💡 系统正在监控群组消息...")
        print("检测到 #币种 市價多/空 格式的消息将自动执行交易")
        print("按 Ctrl+C 停止系统")
        print("="*60)
        
        # 开始监控
        await bot.start_monitoring()
        
    except KeyboardInterrupt:
        print("\n👋 用户中断")
    except Exception as e:
        print(f"❌ 运行出错: {e}")
    finally:
        await bot.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 程序被中断")
    except Exception as e:
        print(f"❌ 程序出错: {e}")
