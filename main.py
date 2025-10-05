"""
Telegram交易信号监控跟单系统 - 主程序入口
"""

import sys
import asyncio
import argparse
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.logger import logger
from src.utils.config import config


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="Telegram交易信号监控跟单系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python main.py                    # 启动GUI界面
  python main.py --console          # 控制台模式运行
  python main.py --test-config      # 测试配置
  python main.py --version          # 显示版本信息
        """
    )
    
    parser.add_argument(
        '--console', 
        action='store_true', 
        help='在控制台模式下运行（无GUI）'
    )
    
    parser.add_argument(
        '--test-config', 
        action='store_true', 
        help='测试配置文件的有效性'
    )
    
    parser.add_argument(
        '--version', 
        action='version', 
        version='Telegram Trading Bot v1.0.0'
    )
    
    parser.add_argument(
        '--log-level', 
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
        default='INFO',
        help='设置日志级别'
    )
    
    return parser.parse_args()


def test_configuration():
    """测试配置文件"""
    print("正在测试配置...")
    
    try:
        # 显示配置摘要
        print("\n📊 当前配置摘要:")
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
            return True
        else:
            print("⚠️  API配置未完成，请按以下步骤配置:")
            print("   1. 复制 config/trading_config_example.env 为 .env")
            print("   2. 填入您的Telegram和Bitget API信息")
            print("   3. 重新运行测试: python main.py --test-config")
            return False
            
    except Exception as e:
        print(f"❌ 配置测试失败: {e}")
        return False


async def run_console_mode():
    """控制台模式运行"""
    from src.telegram.monitor import TelegramMonitor
    from src.trading.bitget_client import BitgetClient
    from src.trading.signal_parser import SignalParser
    from src.trading.risk_manager import RiskManager
    from src.database.database import db_manager
    from src.notifications.notifier import notifier, NotificationType
    
    logger.info("启动控制台模式")
    
    try:
        # 初始化组件
        telegram_monitor = TelegramMonitor()
        bitget_client = BitgetClient()
        signal_parser = SignalParser()
        risk_manager = RiskManager()
        
        # 初始化数据库
        db_manager.initialize()
        logger.info("数据库初始化完成")
        
        # 初始化Telegram监控
        if not await telegram_monitor.initialize():
            logger.error("Telegram监控初始化失败")
            return
        
        # 初始化Bitget客户端
        async with bitget_client:
            # 测试连接
            test_result = await bitget_client.test_connection()
            if not test_result['success']:
                logger.error(f"Bitget连接测试失败: {test_result.get('error')}")
                return
            
            logger.info("Bitget连接测试成功")
            
            # 定义信号处理函数
            async def handle_trading_signal(signal_dict):
                try:
                    logger.info(f"收到交易信号: {signal_dict['raw_message']}")
                    
                    # 解析信号
                    signal = signal_parser.parse_signal(
                        signal_dict['raw_message'], 
                        signal_dict
                    )
                    
                    if not signal:
                        logger.warning("信号解析失败")
                        return
                    
                    # 保存信号到数据库
                    signal_id = db_manager.save_trading_signal(signal, signal_dict)
                    logger.info(f"信号已保存，ID: {signal_id}")
                    
                    # 发送通知
                    await notifier.notify_trade_signal(signal)
                    
                    # 风险检查
                    balance = await bitget_client.get_balance()
                    risk_ok, risk_msg, risk_details = risk_manager.check_signal_risk(signal, balance)
                    
                    if not risk_ok:
                        logger.warning(f"信号被风险管理器拒绝: {risk_msg}")
                        db_manager.update_signal_status(signal_id, 'ignored', risk_msg)
                        await notifier.notify_risk_alert(f"信号被拒绝: {risk_msg}")
                        return
                    
                    logger.info("风险检查通过，执行交易...")
                    
                    # 执行交易
                    execution_result = await bitget_client.execute_signal(signal)
                    
                    if execution_result and execution_result.get('success'):
                        logger.info("交易执行成功")
                        db_manager.update_signal_status(signal_id, 'processed')
                        await notifier.notify_trade_execution(execution_result)
                        
                        # 更新风险管理器
                        order_info = execution_result.get('order', {})
                        entry_price = float(order_info.get('price', 0))
                        trade_amount = execution_result.get('trade_amount', 0)
                        
                        if entry_price > 0:
                            risk_manager.add_position(signal, entry_price, trade_amount)
                    else:
                        error_msg = execution_result.get('error', '执行失败') if execution_result else '执行失败'
                        logger.error(f"交易执行失败: {error_msg}")
                        db_manager.update_signal_status(signal_id, 'error', error_msg)
                        await notifier.notify(f"交易执行失败: {error_msg}", NotificationType.ERROR)
                
                except Exception as e:
                    logger.error(f"处理交易信号失败: {e}")
            
            # 添加信号回调
            telegram_monitor.add_signal_callback(handle_trading_signal)
            
            # 启动监控
            if await telegram_monitor.start_monitoring():
                logger.info("监控已启动，按 Ctrl+C 停止")
                
                try:
                    # 保持运行
                    while True:
                        await asyncio.sleep(1)
                        
                except KeyboardInterrupt:
                    logger.info("收到停止信号")
                
                finally:
                    # 清理资源
                    await telegram_monitor.stop_monitoring()
                    await telegram_monitor.cleanup()
                    logger.info("监控已停止")
            else:
                logger.error("监控启动失败")
    
    except Exception as e:
        logger.error(f"控制台模式运行失败: {e}")


def main():
    """主函数"""
    # 解析命令行参数
    args = parse_arguments()
    
    # 设置日志级别
    if hasattr(config.log, 'level'):
        import logging
        logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # 显示启动信息
    print("=" * 60)
    print("    Telegram交易信号监控跟单系统 v1.0.0")
    print("=" * 60)
    print()
    
    # 测试配置
    if args.test_config:
        success = test_configuration()
        sys.exit(0 if success else 1)
    
    # 验证配置
    is_valid, errors = config.validate_config()
    if not is_valid:
        print("❌ 配置验证失败:")
        for error in errors:
            print(f"  - {error}")
        print("\n请检查配置文件或环境变量设置。")
        print("参考配置模板: config/env_template.txt")
        sys.exit(1)
    
    print("✅ 配置验证通过")
    
    try:
        if args.console:
            # 控制台模式
            print("启动控制台模式...")
            asyncio.run(run_console_mode())
        else:
            # GUI模式
            print("启动图形界面...")
            try:
                from src.gui.main_window import run_gui
                run_gui()
            except ImportError as e:
                print(f"❌ GUI依赖未安装: {e}")
                print("请安装GUI依赖: pip install PyQt6")
                print("或使用控制台模式: python main.py --console")
                sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n程序被用户中断")
        sys.exit(0)
    except Exception as e:
        logger.error(f"程序运行失败: {e}")
        print(f"\n❌ 程序运行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
