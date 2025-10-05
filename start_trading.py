#!/usr/bin/env python3
"""
交易跟单系统启动器
专门针对市价单交易的简化版本
"""

import sys
import asyncio
import signal
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.logger import get_logger
from src.utils.config import load_config
from src.telegram.monitor import TelegramMonitor
from src.trading.optimized_signal_parser import OptimizedSignalParser
from src.trading.bitget_client import BitgetClient
from src.notifications.notifier import NotificationManager
from src.database.database import DatabaseManager

logger = get_logger("TradingSystem")


class MarketOrderTradingSystem:
    """市价单交易系统"""
    
    def __init__(self):
        self.config = None
        self.telegram_monitor = None
        self.signal_parser = None
        self.bitget_client = None
        self.notification_manager = None
        self.db_manager = None
        self.running = False
    
    async def initialize(self):
        """初始化系统"""
        try:
            logger.info("🚀 启动市价单交易跟单系统")
            
            # 加载配置
            logger.info("📋 加载配置...")
            self.config = load_config()
            
            # 初始化数据库
            logger.info("💾 初始化数据库...")
            self.db_manager = DatabaseManager()
            await self.db_manager.initialize()
            
            # 初始化通知管理器
            logger.info("🔔 初始化通知系统...")
            self.notification_manager = NotificationManager(self.config)
            
            # 初始化信号解析器（使用优化版本）
            logger.info("🧠 初始化信号解析器...")
            self.signal_parser = OptimizedSignalParser()
            
            # 初始化Bitget客户端
            logger.info("💱 初始化Bitget交易客户端...")
            self.bitget_client = BitgetClient(self.config)
            
            # 测试Bitget连接
            logger.info("🔗 测试Bitget连接...")
            account_info = await self.bitget_client.get_account_info()
            if account_info:
                logger.info("✅ Bitget连接成功")
                await self.notification_manager.send_notification(
                    "系统启动", 
                    "✅ Bitget API连接成功，系统准备就绪"
                )
            else:
                raise Exception("Bitget连接失败")
            
            # 初始化Telegram监控器
            logger.info("📱 初始化Telegram监控器...")
            self.telegram_monitor = TelegramMonitor(self.config)
            
            # 设置信号处理回调
            self.telegram_monitor.set_signal_handler(self.handle_signal)
            
            # 初始化Telegram连接
            if not await self.telegram_monitor.initialize():
                raise Exception("Telegram初始化失败")
            
            logger.info("✅ 系统初始化完成")
            await self.notification_manager.send_notification(
                "系统启动", 
                "🚀 交易跟单系统已启动\n"
                f"监控群组: {self.config.telegram.group_id}\n"
                f"交易金额: {self.config.trading.default_trade_amount}U\n"
                f"杠杆倍数: {self.config.trading.default_leverage}x"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 系统初始化失败: {e}")
            await self.notification_manager.send_notification(
                "系统错误", 
                f"❌ 系统初始化失败: {e}"
            )
            return False
    
    async def handle_signal(self, message_text: str, sender_info: dict):
        """处理接收到的信号"""
        try:
            logger.info(f"📨 收到消息: {message_text}")
            
            # 解析信号
            signal = self.signal_parser.parse_signal(message_text)
            
            if not signal:
                logger.debug("消息不是交易信号，忽略")
                return
            
            logger.info(f"🎯 检测到交易信号: {signal.symbol} {signal.side.value}")
            
            # 验证信号
            if not self.signal_parser.validate_signal(signal):
                logger.warning("信号验证失败，跳过执行")
                return
            
            # 发送信号通知
            await self.notification_manager.send_notification(
                "交易信号", 
                f"🎯 检测到信号\n"
                f"币种: {signal.symbol}\n"
                f"方向: {'做多' if signal.side.value == 'buy' else '做空'}\n"
                f"金额: {signal.amount or self.config.trading.default_trade_amount}U\n"
                f"杠杆: {signal.leverage}x"
            )
            
            # 执行交易（市价单）
            logger.info(f"💰 执行市价交易...")
            trade_result = await self.bitget_client.execute_signal(signal)
            
            if trade_result and trade_result.get('success'):
                logger.info(f"✅ 交易执行成功: {trade_result}")
                
                # 保存交易记录
                await self.db_manager.save_trade_record({
                    'signal_id': signal.symbol + str(signal.parsed_at.timestamp()),
                    'symbol': signal.symbol,
                    'side': signal.side.value,
                    'amount': signal.amount or self.config.trading.default_trade_amount,
                    'leverage': signal.leverage,
                    'order_id': trade_result.get('orderId'),
                    'status': 'executed',
                    'raw_message': message_text
                })
                
                # 发送成功通知
                await self.notification_manager.send_notification(
                    "交易成功", 
                    f"✅ 交易执行成功\n"
                    f"订单ID: {trade_result.get('orderId', 'N/A')}\n"
                    f"币种: {signal.symbol}\n"
                    f"方向: {'做多' if signal.side.value == 'buy' else '做空'}\n"
                    f"金额: {signal.amount or self.config.trading.default_trade_amount}U"
                )
                
            else:
                error_msg = trade_result.get('error', '未知错误') if trade_result else '交易失败'
                logger.error(f"❌ 交易执行失败: {error_msg}")
                
                # 发送失败通知
                await self.notification_manager.send_notification(
                    "交易失败", 
                    f"❌ 交易执行失败\n"
                    f"错误: {error_msg}\n"
                    f"信号: {signal.symbol} {signal.side.value}"
                )
                
        except Exception as e:
            logger.error(f"❌ 处理信号时出错: {e}")
            await self.notification_manager.send_notification(
                "系统错误", 
                f"❌ 处理信号时出错: {e}"
            )
    
    async def start_monitoring(self):
        """开始监控"""
        try:
            logger.info("👀 开始监控Telegram群组...")
            self.running = True
            
            # 启动Telegram监控
            await self.telegram_monitor.start_monitoring()
            
        except Exception as e:
            logger.error(f"❌ 监控过程中出错: {e}")
            await self.notification_manager.send_notification(
                "系统错误", 
                f"❌ 监控过程中出错: {e}"
            )
    
    async def stop(self):
        """停止系统"""
        logger.info("🛑 正在停止系统...")
        self.running = False
        
        if self.telegram_monitor:
            await self.telegram_monitor.stop()
        
        if self.db_manager:
            await self.db_manager.close()
        
        await self.notification_manager.send_notification(
            "系统停止", 
            "🛑 交易跟单系统已停止"
        )
        
        logger.info("✅ 系统已停止")


async def main():
    """主函数"""
    system = MarketOrderTradingSystem()
    
    # 设置信号处理
    def signal_handler(signum, frame):
        print(f"\n接收到信号 {signum}，正在停止系统...")
        asyncio.create_task(system.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # 初始化系统
        if not await system.initialize():
            print("❌ 系统初始化失败")
            return
        
        print("\n" + "="*60)
        print("🚀 市价单交易跟单系统已启动")
        print("="*60)
        print("📊 系统状态:")
        print(f"  - 交易模式: 市价单")
        print(f"  - 交易金额: {system.config.trading.default_trade_amount}U")
        print(f"  - 杠杆倍数: {system.config.trading.default_leverage}x")
        print(f"  - 监控群组: {system.config.telegram.group_id}")
        print(f"  - 沙盒模式: {'开启' if system.config.bitget.sandbox else '关闭'}")
        print("="*60)
        print("💡 系统正在监控群组消息，检测到交易信号将自动执行市价单")
        print("按 Ctrl+C 停止系统")
        print("="*60)
        
        # 开始监控
        await system.start_monitoring()
        
    except KeyboardInterrupt:
        print("\n👋 用户中断，正在停止系统...")
    except Exception as e:
        print(f"❌ 系统运行出错: {e}")
    finally:
        await system.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 程序被中断")
    except Exception as e:
        print(f"❌ 程序执行出错: {e}")
