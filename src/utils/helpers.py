"""
通用辅助函数模块
提供项目中常用的工具函数
"""

import re
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json


def parse_trading_signal(message: str) -> Optional[Dict[str, Any]]:
    """
    解析交易信号消息
    
    支持格式:
    - #PTB 市價多
    - #ESPORTS 市價空
    - #BTC 市價多 100U
    - #ETH 市價空 止損1800 目标2000
    
    Args:
        message: 原始消息文本
        
    Returns:
        解析后的信号字典，如果不是有效信号则返回None
    """
    # 清理消息，去除多余空格和换行
    clean_message = re.sub(r'\s+', ' ', message.strip())
    
    # 基本信号格式匹配: #币种 市價多/空
    basic_pattern = r'#(\w+)\s+市[價价]([多空])'
    match = re.search(basic_pattern, clean_message, re.IGNORECASE)
    
    if not match:
        return None
    
    symbol = match.group(1).upper()
    direction = match.group(2)
    
    # 转换方向
    side = "buy" if direction == "多" else "sell"
    
    # 提取金额信息 (如: 100U, 50USDT)
    amount_pattern = r'(\d+(?:\.\d+)?)\s*[Uu](?:SDT)?'
    amount_match = re.search(amount_pattern, clean_message)
    amount = float(amount_match.group(1)) if amount_match else None
    
    # 提取止损信息
    stop_loss_pattern = r'止[损損]\s*(\d+(?:\.\d+)?)'
    stop_loss_match = re.search(stop_loss_pattern, clean_message, re.IGNORECASE)
    stop_loss = float(stop_loss_match.group(1)) if stop_loss_match else None
    
    # 提取目标/止盈信息
    take_profit_pattern = r'(?:目[标標]|止[盈贏])\s*(\d+(?:\.\d+)?)'
    take_profit_match = re.search(take_profit_pattern, clean_message, re.IGNORECASE)
    take_profit = float(take_profit_match.group(1)) if take_profit_match else None
    
    # 提取杠杆信息
    leverage_pattern = r'(\d+)[xX倍]'
    leverage_match = re.search(leverage_pattern, clean_message)
    leverage = int(leverage_match.group(1)) if leverage_match else 1
    
    return {
        'symbol': symbol,
        'side': side,
        'direction_cn': direction,
        'amount': amount,
        'stop_loss': stop_loss,
        'take_profit': take_profit,
        'leverage': leverage,
        'raw_message': message,
        'parsed_at': datetime.now(timezone.utc).isoformat()
    }


def format_currency(amount: float, currency: str = "USDT", decimals: int = 2) -> str:
    """
    格式化货币显示
    
    Args:
        amount: 金额
        currency: 货币符号
        decimals: 小数位数
        
    Returns:
        格式化后的货币字符串
    """
    if amount is None:
        return "N/A"
    
    # 使用Decimal进行精确计算
    decimal_amount = Decimal(str(amount))
    rounded_amount = decimal_amount.quantize(
        Decimal(f'0.{"0" * decimals}'), 
        rounding=ROUND_HALF_UP
    )
    
    return f"{rounded_amount:,} {currency}"


def format_percentage(value: float, decimals: int = 2) -> str:
    """
    格式化百分比显示
    
    Args:
        value: 百分比值
        decimals: 小数位数
        
    Returns:
        格式化后的百分比字符串
    """
    if value is None:
        return "N/A"
    
    return f"{value:.{decimals}f}%"


def calculate_position_size(
    balance: float, 
    risk_percentage: float, 
    entry_price: float, 
    stop_loss_price: Optional[float] = None
) -> float:
    """
    计算仓位大小
    
    Args:
        balance: 账户余额
        risk_percentage: 风险百分比 (0-100)
        entry_price: 入场价格
        stop_loss_price: 止损价格
        
    Returns:
        建议仓位大小
    """
    if not stop_loss_price:
        # 如果没有止损价格，使用固定风险百分比
        return balance * (risk_percentage / 100)
    
    # 计算风险金额
    risk_amount = balance * (risk_percentage / 100)
    
    # 计算价格风险
    price_risk = abs(entry_price - stop_loss_price) / entry_price
    
    if price_risk == 0:
        return balance * (risk_percentage / 100)
    
    # 计算仓位大小
    position_size = risk_amount / price_risk
    
    # 确保不超过最大风险
    max_position = balance * 0.5  # 最大50%仓位
    return min(position_size, max_position)


def validate_symbol(symbol: str) -> bool:
    """
    验证交易对符号的有效性
    
    Args:
        symbol: 交易对符号
        
    Returns:
        是否为有效符号
    """
    if not symbol:
        return False
    
    # 基本格式检查
    if not re.match(r'^[A-Z0-9]{2,10}$', symbol.upper()):
        return False
    
    # 常见币种白名单（可扩展）
    common_symbols = {
        'BTC', 'ETH', 'BNB', 'ADA', 'XRP', 'SOL', 'DOT', 'DOGE', 
        'MATIC', 'AVAX', 'LINK', 'UNI', 'LTC', 'BCH', 'XLM',
        'ATOM', 'FTT', 'NEAR', 'ALGO', 'VET', 'ICP', 'FIL',
        'TRX', 'ETC', 'HBAR', 'APE', 'SAND', 'MANA', 'CRO',
        'PTB', 'ESPORTS'  # 添加示例中的币种
    }
    
    return symbol.upper() in common_symbols


def generate_order_id(symbol: str, side: str, timestamp: Optional[datetime] = None) -> str:
    """
    生成唯一的订单ID
    
    Args:
        symbol: 交易对
        side: 交易方向
        timestamp: 时间戳
        
    Returns:
        唯一订单ID
    """
    if not timestamp:
        timestamp = datetime.now(timezone.utc)
    
    # 创建唯一字符串
    unique_string = f"{symbol}_{side}_{timestamp.isoformat()}"
    
    # 生成哈希
    hash_object = hashlib.md5(unique_string.encode())
    hash_hex = hash_object.hexdigest()
    
    # 返回前12位作为订单ID
    return f"TG_{hash_hex[:12].upper()}"


def safe_float(value: Any, default: float = 0.0) -> float:
    """
    安全转换为浮点数
    
    Args:
        value: 要转换的值
        default: 默认值
        
    Returns:
        转换后的浮点数
    """
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """
    安全转换为整数
    
    Args:
        value: 要转换的值
        default: 默认值
        
    Returns:
        转换后的整数
    """
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (ValueError, TypeError):
        return default


def format_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    格式化日期时间
    
    Args:
        dt: 日期时间对象
        format_str: 格式字符串
        
    Returns:
        格式化后的日期时间字符串
    """
    if not dt:
        return "N/A"
    
    # 确保使用本地时区
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    return dt.strftime(format_str)


def sanitize_filename(filename: str) -> str:
    """
    清理文件名，移除非法字符
    
    Args:
        filename: 原始文件名
        
    Returns:
        清理后的文件名
    """
    # 移除或替换非法字符
    illegal_chars = '<>:"/\\|?*'
    for char in illegal_chars:
        filename = filename.replace(char, '_')
    
    # 移除前后空格和点
    filename = filename.strip(' .')
    
    # 确保不为空
    if not filename:
        filename = "untitled"
    
    return filename


def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """
    将列表分块
    
    Args:
        lst: 原始列表
        chunk_size: 块大小
        
    Returns:
        分块后的列表
    """
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def retry_async(max_retries: int = 3, delay: float = 1.0):
    """
    异步重试装饰器
    
    Args:
        max_retries: 最大重试次数
        delay: 重试延迟（秒）
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        await asyncio.sleep(delay * (attempt + 1))
                    else:
                        raise last_exception
            
            raise last_exception
        return wrapper
    return decorator


def mask_sensitive_data(data: str, mask_char: str = "*", visible_chars: int = 4) -> str:
    """
    掩码敏感数据
    
    Args:
        data: 敏感数据
        mask_char: 掩码字符
        visible_chars: 可见字符数
        
    Returns:
        掩码后的数据
    """
    if not data or len(data) <= visible_chars:
        return mask_char * len(data) if data else ""
    
    visible_part = data[:visible_chars]
    masked_part = mask_char * (len(data) - visible_chars)
    
    return visible_part + masked_part
