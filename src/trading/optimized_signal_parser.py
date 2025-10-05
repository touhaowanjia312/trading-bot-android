"""
优化的交易信号解析模块
基于真实Telegram群组信号格式优化
支持多条消息组合解析和复杂止盈止损格式
"""

import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

from ..utils.logger import get_logger
from ..utils.helpers import validate_symbol, safe_float, safe_int

logger = get_logger("OptimizedSignalParser")


class SignalType(Enum):
    """信号类型枚举"""
    MARKET_ORDER = "market"      # 市价单
    LIMIT_ORDER = "limit"        # 限价单
    STOP_ORDER = "stop"          # 止损单
    TAKE_PROFIT = "take_profit"  # 止盈单


class OrderSide(Enum):
    """订单方向枚举"""
    BUY = "buy"    # 买入/做多
    SELL = "sell"  # 卖出/做空


@dataclass
class TradingSignal:
    """交易信号数据类"""
    symbol: str                          # 交易对符号
    side: OrderSide                      # 交易方向
    signal_type: SignalType              # 信号类型
    amount: Optional[float] = None       # 交易金额
    price: Optional[float] = None        # 价格（限价单使用）
    stop_loss: Optional[float] = None    # 止损价格
    take_profit: Optional[float] = None  # 止盈价格（主要止盈）
    take_profit_levels: List[float] = field(default_factory=list)  # 多级止盈
    leverage: int = 1                    # 杠杆倍数
    confidence: float = 0.8              # 信号置信度
    raw_message: str = ""                # 原始消息
    parsed_at: datetime = None           # 解析时间
    metadata: Dict[str, Any] = field(default_factory=dict)  # 额外元数据
    pattern_name: str = ""               # 匹配的模式名称
    
    def __post_init__(self):
        if self.parsed_at is None:
            self.parsed_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'symbol': self.symbol,
            'side': self.side.value,
            'signal_type': self.signal_type.value,
            'amount': self.amount,
            'price': self.price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'take_profit_levels': self.take_profit_levels,
            'leverage': self.leverage,
            'confidence': self.confidence,
            'raw_message': self.raw_message,
            'parsed_at': self.parsed_at.isoformat(),
            'metadata': self.metadata,
            'pattern_name': self.pattern_name
        }


class OptimizedSignalParser:
    """优化的交易信号解析器"""
    
    def __init__(self):
        # 加载配置
        try:
            from ..utils.config import load_config
            config = load_config()
            self.default_leverage = config.trading.default_leverage
            self.default_amount = config.trading.default_trade_amount
        except Exception as e:
            logger.warning(f"无法加载配置，使用默认值: {e}")
            self.default_leverage = 20
            self.default_amount = 2.0
        
        self.signal_patterns = self._initialize_patterns()
        self.symbol_aliases = self._initialize_symbol_aliases()
        self.chinese_numbers = self._initialize_chinese_numbers()
    
    def _initialize_patterns(self) -> List[Dict[str, Any]]:
        """初始化基于真实格式的信号匹配模式"""
        return [
            # 1. 基础市价信号 - 匹配 "#WLFI 市價空"
            {
                'name': 'basic_market_signal',
                'pattern': r'#(\w+)\s+市[價价]([多空])',
                'description': '基本市价信号: #币种 市價多/空',
                'confidence': 0.9,
                'parser': self._parse_basic_market_signal
            },
            
            # 2. 单级止盈信号 - 匹配 "第一止盈: 0.179"
            {
                'name': 'single_take_profit',
                'pattern': r'第([一二三四五六七八九十])止[盈贏]:\s*(\d+(?:\.\d+)?)',
                'description': '单级止盈: 第一止盈: 0.179',
                'confidence': 0.88,
                'parser': self._parse_take_profit_signal
            },
            
            # 3. 止损信号 - 匹配 "止损: 0.398"
            {
                'name': 'stop_loss_signal',
                'pattern': r'止[损損]:\s*(\d+(?:\.\d+)?)',
                'description': '止损信号: 止损: 0.398',
                'confidence': 0.88,
                'parser': self._parse_stop_loss_signal
            },
            
            # 4. 多级止盈信号 - 匹配复杂的多级止盈
            {
                'name': 'multi_take_profit',
                'pattern': r'(?:第([一二三四五六七八九十])止[盈贏]:\s*(\d+(?:\.\d+)?)[\s\n]*){2,}',
                'description': '多级止盈信号',
                'confidence': 0.92,
                'parser': self._parse_multi_take_profit
            },
            
            # 5. 完整信号（一条消息包含所有信息）
            {
                'name': 'complete_signal',
                'pattern': r'#(\w+)\s+市[價价]([多空]).*?(?:第([一二三四五六七八九十])止[盈贏]:\s*(\d+(?:\.\d+)?))?.*?(?:止[损損]:\s*(\d+(?:\.\d+)?))?',
                'description': '完整信号',
                'confidence': 0.95,
                'parser': self._parse_complete_signal
            },
            
            # 6. 带金额的市价信号
            {
                'name': 'market_with_amount',
                'pattern': r'#(\w+)\s+市[價价]([多空])\s+(\d+(?:\.\d+)?)\s*[Uu](?:SDT)?',
                'description': '带金额市价信号: #币种 市價多/空 100U',
                'confidence': 0.93,
                'parser': self._parse_market_with_amount
            },
        ]
    
    def _initialize_symbol_aliases(self) -> Dict[str, str]:
        """初始化币种别名映射"""
        return {
            # 主流币种
            'BTC': 'BTCUSDT',
            'ETH': 'ETHUSDT',
            'BNB': 'BNBUSDT',
            'ADA': 'ADAUSDT',
            'XRP': 'XRPUSDT',
            'SOL': 'SOLUSDT',
            'DOGE': 'DOGEUSDT',
            'MATIC': 'MATICUSDT',
            'AVAX': 'AVAXUSDT',
            
            # 从截图中发现的币种
            'WLFI': 'WLFIUSDT',
            'TREE': 'TREEUSDT',
            'TA': 'TAUSDT',
            'BAKE': 'BAKEUSDT',
            
            # 常见的其他币种
            'LINK': 'LINKUSDT',
            'UNI': 'UNIUSDT',
            'DOT': 'DOTUSDT',
            'ATOM': 'ATOMUSDT',
            'FTM': 'FTMUSDT',
            'ALGO': 'ALGOUSDT',
            'NEAR': 'NEARUSDT',
            'SAND': 'SANDUSDT',
            'MANA': 'MANAUSDT',
            'CRV': 'CRVUSDT',
            'COMP': 'COMPUSDT',
            'SUSHI': 'SUSHIUSDT',
            'YFI': 'YFIUSDT',
            'AAVE': 'AAVEUSDT',
            'MKR': 'MKRUSDT',
            'SNX': 'SNXUSDT',
            '1INCH': '1INCHUSDT',
            'BAT': 'BATUSDT',
            'ENJ': 'ENJUSDT',
            'ZRX': 'ZRXUSDT',
            'OMG': 'OMGUSDT',
            'LRC': 'LRCUSDT',
            'KNC': 'KNCUSDT',
            'REN': 'RENUSDT',
            'STORJ': 'STORJUSDT',
            'GRT': 'GRTUSDT',
            'NKN': 'NKNUSDT',
            'OGN': 'OGNUSDT',
            'NMR': 'NMRUSDT',
            'RSR': 'RSRUSDT',
            'FET': 'FETUSDT',
            'CTSI': 'CTSIUSDT',
            'HBAR': 'HBARUSDT',
            'ONE': 'ONEUSDT',
            'FTT': 'FTTUSDT',
            'HOT': 'HOTUSDT',
            'WIN': 'WINUSDT',
            'BTT': 'BTTUSDT',
            'CHZ': 'CHZUSDT',
            'VET': 'VETUSDT',
            'THETA': 'THETAUSDT',
            'TFUEL': 'TFUELUSDT',
            'RUNE': 'RUNEUSDT'
        }
    
    def _initialize_chinese_numbers(self) -> Dict[str, int]:
        """初始化中文数字映射"""
        return {
            '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
            '六': 6, '七': 7, '八': 8, '九': 9, '十': 10
        }
    
    def parse_signal(self, message: str) -> Optional[TradingSignal]:
        """解析单条信号消息"""
        if not message or not isinstance(message, str):
            return None
        
        message = message.strip()
        if not message:
            return None
        
        logger.debug(f"解析消息: {message}")
        
        # 按置信度从高到低尝试匹配
        for pattern_info in sorted(self.signal_patterns, key=lambda x: x['confidence'], reverse=True):
            try:
                match = re.search(pattern_info['pattern'], message, re.MULTILINE | re.DOTALL)
                if match:
                    logger.debug(f"匹配到模式: {pattern_info['name']}")
                    signal = pattern_info['parser'](match, message, pattern_info)
                    if signal:
                        signal.pattern_name = pattern_info['name']
                        logger.info(f"成功解析信号: {signal.symbol} {signal.side.value}")
                        return signal
            except Exception as e:
                logger.error(f"解析模式 {pattern_info['name']} 时出错: {e}")
                continue
        
        logger.warning(f"未能解析信号: {message}")
        return None
    
    def parse_multi_message_signal(self, messages: List[str]) -> Optional[TradingSignal]:
        """解析多条消息组合的信号"""
        if not messages:
            return None
        
        # 合并所有消息
        combined_message = '\n'.join(messages)
        
        # 首先尝试解析基础信号
        base_signal = None
        take_profit_levels = []
        stop_loss = None
        
        for message in messages:
            # 查找基础信号（#币种 市價多/空）
            if not base_signal:
                base_match = re.search(r'#(\w+)\s+市[價价]([多空])', message)
                if base_match:
                    symbol = base_match.group(1)
                    side = OrderSide.BUY if base_match.group(2) == '多' else OrderSide.SELL
                    
                    base_signal = TradingSignal(
                        symbol=self._normalize_symbol(symbol),
                        side=side,
                        signal_type=SignalType.MARKET_ORDER,
                        leverage=self.default_leverage,
                        amount=self.default_amount,
                        raw_message=combined_message,
                        confidence=0.9
                    )
            
            # 提取止盈信息
            tp_matches = re.findall(r'第([一二三四五六七八九十])止[盈贏]:\s*(\d+(?:\.\d+)?)', message)
            for level_chinese, price_str in tp_matches:
                level = self.chinese_numbers.get(level_chinese, 1)
                price = safe_float(price_str)
                if price:
                    take_profit_levels.append((level, price))
            
            # 提取止损信息
            sl_match = re.search(r'止[损損]:\s*(\d+(?:\.\d+)?)', message)
            if sl_match and not stop_loss:
                stop_loss = safe_float(sl_match.group(1))
        
        if base_signal:
            # 设置止盈止损
            if take_profit_levels:
                # 按级别排序
                take_profit_levels.sort(key=lambda x: x[0])
                base_signal.take_profit_levels = [price for _, price in take_profit_levels]
                # 设置主要止盈为第一级
                base_signal.take_profit = take_profit_levels[0][1]
            
            if stop_loss:
                base_signal.stop_loss = stop_loss
            
            # 更新置信度
            if take_profit_levels and stop_loss:
                base_signal.confidence = 0.98
            elif take_profit_levels or stop_loss:
                base_signal.confidence = 0.95
            
            base_signal.pattern_name = 'multi_message_signal'
            logger.info(f"成功解析多消息信号: {base_signal.symbol} {base_signal.side.value}")
            return base_signal
        
        return None
    
    def _parse_basic_market_signal(self, match, message: str, pattern_info: Dict) -> Optional[TradingSignal]:
        """解析基础市价信号"""
        symbol = match.group(1)
        direction = match.group(2)
        
        side = OrderSide.BUY if direction == '多' else OrderSide.SELL
        
        return TradingSignal(
            symbol=self._normalize_symbol(symbol),
            side=side,
            signal_type=SignalType.MARKET_ORDER,
            leverage=self.default_leverage,
            amount=self.default_amount,
            raw_message=message,
            confidence=pattern_info['confidence']
        )
    
    def _parse_take_profit_signal(self, match, message: str, pattern_info: Dict) -> Optional[TradingSignal]:
        """解析止盈信号（通常需要与基础信号配合）"""
        # 这种信号通常不是独立的，返回None
        # 在多消息解析中会被处理
        return None
    
    def _parse_stop_loss_signal(self, match, message: str, pattern_info: Dict) -> Optional[TradingSignal]:
        """解析止损信号（通常需要与基础信号配合）"""
        # 这种信号通常不是独立的，返回None
        # 在多消息解析中会被处理
        return None
    
    def _parse_multi_take_profit(self, match, message: str, pattern_info: Dict) -> Optional[TradingSignal]:
        """解析多级止盈信号"""
        # 提取所有止盈级别
        tp_matches = re.findall(r'第([一二三四五六七八九十])止[盈贏]:\s*(\d+(?:\.\d+)?)', message)
        
        if not tp_matches:
            return None
        
        take_profit_levels = []
        for level_chinese, price_str in tp_matches:
            level = self.chinese_numbers.get(level_chinese, 1)
            price = safe_float(price_str)
            if price:
                take_profit_levels.append((level, price))
        
        # 通常需要与基础信号配合，这里返回None
        return None
    
    def _parse_complete_signal(self, match, message: str, pattern_info: Dict) -> Optional[TradingSignal]:
        """解析完整信号"""
        symbol = match.group(1)
        direction = match.group(2)
        
        side = OrderSide.BUY if direction == '多' else OrderSide.SELL
        
        signal = TradingSignal(
            symbol=self._normalize_symbol(symbol),
            side=side,
            signal_type=SignalType.MARKET_ORDER,
            leverage=self.default_leverage,
            amount=self.default_amount,
            raw_message=message,
            confidence=pattern_info['confidence']
        )
        
        # 提取止盈信息
        if len(match.groups()) >= 4 and match.group(4):
            signal.take_profit = safe_float(match.group(4))
        
        # 提取止损信息
        if len(match.groups()) >= 5 and match.group(5):
            signal.stop_loss = safe_float(match.group(5))
        
        # 提取所有止盈级别
        tp_matches = re.findall(r'第([一二三四五六七八九十])止[盈贏]:\s*(\d+(?:\.\d+)?)', message)
        if tp_matches:
            take_profit_levels = []
            for level_chinese, price_str in tp_matches:
                level = self.chinese_numbers.get(level_chinese, 1)
                price = safe_float(price_str)
                if price:
                    take_profit_levels.append((level, price))
            
            if take_profit_levels:
                take_profit_levels.sort(key=lambda x: x[0])
                signal.take_profit_levels = [price for _, price in take_profit_levels]
                if not signal.take_profit and take_profit_levels:
                    signal.take_profit = take_profit_levels[0][1]
        
        return signal
    
    def _parse_market_with_amount(self, match, message: str, pattern_info: Dict) -> Optional[TradingSignal]:
        """解析带金额的市价信号"""
        symbol = match.group(1)
        direction = match.group(2)
        amount = safe_float(match.group(3))
        
        side = OrderSide.BUY if direction == '多' else OrderSide.SELL
        
        return TradingSignal(
            symbol=self._normalize_symbol(symbol),
            side=side,
            signal_type=SignalType.MARKET_ORDER,
            amount=amount,
            leverage=self.default_leverage,
            raw_message=message,
            confidence=pattern_info['confidence']
        )
    
    def _normalize_symbol(self, symbol: str) -> str:
        """标准化交易对符号"""
        symbol = symbol.upper().strip()
        
        # 检查别名映射
        if symbol in self.symbol_aliases:
            return self.symbol_aliases[symbol]
        
        # 如果已经是USDT对，直接返回
        if symbol.endswith('USDT'):
            return symbol
        
        # 默认添加USDT后缀
        return f"{symbol}USDT"
    
    def get_supported_symbols(self) -> List[str]:
        """获取支持的交易对列表"""
        return list(self.symbol_aliases.values())
    
    def validate_signal(self, signal: TradingSignal) -> bool:
        """验证信号的有效性"""
        try:
            # 检查必需字段
            if not signal.symbol or not signal.side:
                return False
            
            # 检查价格的合理性
            if signal.price is not None and signal.price <= 0:
                return False
            
            if signal.stop_loss is not None and signal.stop_loss <= 0:
                return False
            
            if signal.take_profit is not None and signal.take_profit <= 0:
                return False
            
            # 检查杠杆倍数
            if signal.leverage <= 0 or signal.leverage > 125:
                return False
            
            # 检查止盈止损的逻辑合理性
            if signal.stop_loss and signal.take_profit:
                if signal.side == OrderSide.BUY:
                    # 做多：止盈应该高于止损
                    if signal.take_profit <= signal.stop_loss:
                        logger.warning(f"做多信号止盈({signal.take_profit})应高于止损({signal.stop_loss})")
                        return False
                else:
                    # 做空：止盈应该低于止损
                    if signal.take_profit >= signal.stop_loss:
                        logger.warning(f"做空信号止盈({signal.take_profit})应低于止损({signal.stop_loss})")
                        return False
            
            return True
        
        except Exception as e:
            logger.error(f"验证信号时出错: {e}")
            return False
