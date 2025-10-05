"""
日志配置模块
提供统一的日志管理功能
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional
from datetime import datetime

from .config import config


class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器"""
    
    # ANSI颜色代码
    COLORS = {
        'DEBUG': '\033[36m',     # 青色
        'INFO': '\033[32m',      # 绿色
        'WARNING': '\033[33m',   # 黄色
        'ERROR': '\033[31m',     # 红色
        'CRITICAL': '\033[35m',  # 紫色
    }
    RESET = '\033[0m'
    
    def format(self, record):
        # 获取颜色
        color = self.COLORS.get(record.levelname, self.RESET)
        
        # 格式化消息
        formatted = super().format(record)
        
        # 只在终端输出时添加颜色
        if hasattr(sys.stderr, 'isatty') and sys.stderr.isatty():
            return f"{color}{formatted}{self.RESET}"
        
        return formatted


class TradingBotLogger:
    """交易机器人日志管理器"""
    
    def __init__(self, name: str = "TradingBot"):
        self.logger = logging.getLogger(name)
        self._setup_logger()
    
    def _setup_logger(self):
        """设置日志配置"""
        # 防止重复添加处理器
        if self.logger.handlers:
            return
        
        # 设置日志级别
        level = getattr(logging, config.log.level.upper(), logging.INFO)
        self.logger.setLevel(level)
        
        # 创建日志格式
        log_format = "%(asctime)s | %(name)s | %(levelname)s | %(filename)s:%(lineno)d | %(message)s"
        date_format = "%Y-%m-%d %H:%M:%S"
        
        # 控制台处理器（带颜色）
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_formatter = ColoredFormatter(log_format, date_format)
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # 文件处理器
        self._setup_file_handler(log_format, date_format)
        
        # 防止日志传播到根日志器
        self.logger.propagate = False
    
    def _setup_file_handler(self, log_format: str, date_format: str):
        """设置文件日志处理器"""
        try:
            # 确保日志目录存在
            log_file = Path(config.log.file_path)
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 创建轮转文件处理器，减小文件大小避免频繁轮转
            file_handler = RotatingFileHandler(
                filename=str(log_file),
                maxBytes=5 * 1024 * 1024,  # 减小到5MB
                backupCount=3,  # 减少备份文件数量
                encoding='utf-8',
                delay=True  # 延迟创建文件，避免权限问题
            )
            
            file_handler.setLevel(logging.DEBUG)  # 文件记录所有级别
            file_formatter = logging.Formatter(log_format, date_format)
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
            
        except Exception as e:
            # 如果文件日志设置失败，只输出到控制台
            print(f"警告: 文件日志设置失败: {e}")
            print("将只使用控制台日志输出")
    
    def debug(self, message: str, **kwargs):
        """调试日志"""
        self.logger.debug(message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """信息日志"""
        self.logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """警告日志"""
        self.logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """错误日志"""
        self.logger.error(message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """严重错误日志"""
        self.logger.critical(message, **kwargs)
    
    def exception(self, message: str, **kwargs):
        """异常日志（自动包含异常堆栈）"""
        self.logger.exception(message, **kwargs)
    
    def log_trade_signal(self, signal_data: dict):
        """记录交易信号"""
        self.info(f"交易信号: {signal_data}")
    
    def log_trade_execution(self, trade_data: dict):
        """记录交易执行"""
        self.info(f"交易执行: {trade_data}")
    
    def log_error_with_context(self, error: Exception, context: dict):
        """记录带上下文的错误"""
        self.error(f"错误: {error}, 上下文: {context}")
        self.exception("详细错误信息:")


class TelegramLogger(TradingBotLogger):
    """Telegram模块专用日志器"""
    
    def __init__(self):
        super().__init__("Telegram")
    
    def log_message_received(self, message: str, sender: str):
        """记录收到的消息"""
        self.debug(f"收到消息 - 发送者: {sender}, 内容: {message[:100]}...")
    
    def log_signal_detected(self, signal: str):
        """记录检测到的交易信号"""
        self.info(f"检测到交易信号: {signal}")
    
    def log_connection_status(self, status: str):
        """记录连接状态"""
        self.info(f"Telegram连接状态: {status}")


class BitgetLogger(TradingBotLogger):
    """Bitget模块专用日志器"""
    
    def __init__(self):
        super().__init__("Bitget")
    
    def log_api_call(self, endpoint: str, params: dict):
        """记录API调用"""
        self.debug(f"API调用 - 端点: {endpoint}, 参数: {params}")
    
    def log_order_placed(self, order_id: str, symbol: str, side: str, amount: float):
        """记录订单下达"""
        self.info(f"订单已下达 - ID: {order_id}, 币种: {symbol}, 方向: {side}, 数量: {amount}")
    
    def log_order_error(self, error: str, order_data: dict):
        """记录订单错误"""
        self.error(f"订单错误: {error}, 订单数据: {order_data}")


class DatabaseLogger(TradingBotLogger):
    """数据库模块专用日志器"""
    
    def __init__(self):
        super().__init__("Database")
    
    def log_query(self, query: str, params: Optional[dict] = None):
        """记录数据库查询"""
        self.debug(f"数据库查询: {query}, 参数: {params}")
    
    def log_data_saved(self, table: str, record_id: str):
        """记录数据保存"""
        self.info(f"数据已保存 - 表: {table}, ID: {record_id}")


# 创建全局日志实例
logger = TradingBotLogger()
telegram_logger = TelegramLogger()
bitget_logger = BitgetLogger()
database_logger = DatabaseLogger()


def get_logger(name: str) -> TradingBotLogger:
    """
    获取指定名称的日志器
    
    Args:
        name: 日志器名称
        
    Returns:
        日志器实例
    """
    return TradingBotLogger(name)
