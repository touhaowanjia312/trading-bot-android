"""
交易信号解析模块
负责解析和验证从Telegram群组接收到的交易信号
"""

import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum

from ..utils.logger import get_logger
from ..utils.helpers import validate_symbol, safe_float, safe_int

logger = get_logger("SignalParser")


class SignalType(Enum):
    """信号类型枚举"""
    MARKET_ORDER = "market"      # 市价单
    LIMIT_ORDER = "limit"        # 限价单
    STOP_ORDER = "stop"          # 止损单
    TAKE_PROFIT = "take_profit"  # 止盈单
    FIRST_TAKE_PROFIT = "first_take_profit"  # 第一止盈信号


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
    take_profit: Optional[float] = None  # 止盈价格
    leverage: int = 1                    # 杠杆倍数
    confidence: float = 0.8              # 信号置信度
    raw_message: str = ""                # 原始消息
    parsed_at: datetime = None           # 解析时间
    metadata: Dict[str, Any] = None      # 额外元数据
    
    def __post_init__(self):
        if self.parsed_at is None:
            self.parsed_at = datetime.now(timezone.utc)
        if self.metadata is None:
            self.metadata = {}
    
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
            'leverage': self.leverage,
            'confidence': self.confidence,
            'raw_message': self.raw_message,
            'parsed_at': self.parsed_at.isoformat(),
            'metadata': self.metadata
        }


class SignalParser:
    """交易信号解析器"""
    
    def __init__(self):
        self.signal_patterns = self._initialize_patterns()
        self.symbol_aliases = self._initialize_symbol_aliases()
    
    def _initialize_patterns(self) -> List[Dict[str, Any]]:
        """初始化信号匹配模式"""
        return [
            {
                'name': 'basic_market_signal',
                'pattern': r'#(\w+)\s+市[價价]([多空])',
                'description': '基本市价信号: #币种 市價多/空',
                'confidence': 0.9
            },
            {
                'name': 'market_signal_with_amount',
                'pattern': r'#(\w+)\s+市[價价]([多空])\s+(\d+(?:\.\d+)?)\s*[Uu](?:SDT)?',
                'description': '带金额的市价信号: #币种 市價多/空 100U',
                'confidence': 0.95
            },
            {
                'name': 'limit_signal',
                'pattern': r'#(\w+)\s+([多空])\s+(\d+(?:\.\d+)?)',
                'description': '限价信号: #币种 多/空 价格',
                'confidence': 0.85
            },
            {
                'name': 'full_signal',
                'pattern': r'#(\w+)\s+市[價价]([多空])(?:\s+(\d+(?:\.\d+)?)\s*[Uu](?:SDT)?)?(?:.*?止[损損][:：]?\s*(\d+(?:\.\d+)?))?(?:.*?目[标標][:：]?\s*(\d+(?:\.\d+)?))?',
                'description': '完整信号: #币种 市價多/空 金额 止损价格 目标价格',
                'confidence': 0.98
            },
            {
                'name': 'english_signal',
                'pattern': r'#(\w+)\s+(long|short|buy|sell)\s*(?:@\s*(\d+(?:\.\d+)?))?',
                'description': '英文信号: #币种 long/short/buy/sell @价格',
                'confidence': 0.8
            },
            {
                'name': 'first_take_profit',
                'pattern': r'第一止[盈贏][:：]?\s*(\d+(?:\.\d+)?)',
                'description': '第一止盈信号: 第一止盈: 0.31041',
                'confidence': 0.95
            }
        ]
    
    def _initialize_symbol_aliases(self) -> Dict[str, str]:
        """初始化币种别名映射"""
        return {
            'BTC': 'BTCUSDT',
            'ETH': 'ETHUSDT',
            'BNB': 'BNBUSDT',
            'ADA': 'ADAUSDT',
            'XRP': 'XRPUSDT',
            'SOL': 'SOLUSDT',
            'DOT': 'DOTUSDT',
            'DOGE': 'DOGEUSDT',
            'MATIC': 'MATICUSDT',
            'AVAX': 'AVAXUSDT',
            'LINK': 'LINKUSDT',
            'UNI': 'UNIUSDT',
            'LTC': 'LTCUSDT',
            'BCH': 'BCHUSDT',
            'PTB': 'PTBUSDT',
            'ESPORTS': 'ESPORTSUSDT'
        }
    
    def parse_signal(self, message: str, metadata: Optional[Dict[str, Any]] = None) -> Optional[TradingSignal]:
        """
        解析交易信号
        
        Args:
            message: 原始消息文本
            metadata: 额外元数据
            
        Returns:
            解析后的交易信号，如果解析失败返回None
        """
        if not message or not isinstance(message, str):
            return None
        
        # 清理消息
        clean_message = self._clean_message(message)
        
        # 尝试各种模式匹配
        for pattern_config in self.signal_patterns:
            signal = self._try_parse_with_pattern(clean_message, pattern_config, metadata)
            if signal:
                logger.info(f"成功解析信号: {signal.symbol} {signal.side.value}")
                return signal
        
        logger.debug(f"未能解析信号: {clean_message}")
        return None
    
    def _clean_message(self, message: str) -> str:
        """清理消息文本"""
        # 移除多余的空白字符
        clean_message = re.sub(r'\s+', ' ', message.strip())
        
        # 移除表情符号和特殊字符（保留必要的符号）
        clean_message = re.sub(r'[^\w\s#@\.\-\+多空價价损損标標盈贏目]', ' ', clean_message)
        
        # 再次清理空格
        clean_message = re.sub(r'\s+', ' ', clean_message).strip()
        
        return clean_message
    
    def _try_parse_with_pattern(
        self, 
        message: str, 
        pattern_config: Dict[str, Any], 
        metadata: Optional[Dict[str, Any]]
    ) -> Optional[TradingSignal]:
        """尝试使用指定模式解析信号"""
        try:
            pattern = pattern_config['pattern']
            match = re.search(pattern, message, re.IGNORECASE)
            
            if not match:
                return None
            
            # 根据不同模式解析
            if pattern_config['name'] == 'basic_market_signal':
                return self._parse_basic_market_signal(match, message, pattern_config, metadata)
            elif pattern_config['name'] == 'market_signal_with_amount':
                return self._parse_market_signal_with_amount(match, message, pattern_config, metadata)
            elif pattern_config['name'] == 'limit_signal':
                return self._parse_limit_signal(match, message, pattern_config, metadata)
            elif pattern_config['name'] == 'full_signal':
                return self._parse_full_signal(match, message, pattern_config, metadata)
            elif pattern_config['name'] == 'english_signal':
                return self._parse_english_signal(match, message, pattern_config, metadata)
            elif pattern_config['name'] == 'first_take_profit':
                return self._parse_first_take_profit_signal(match, message, pattern_config, metadata)
            
            return None
            
        except Exception as e:
            logger.error(f"解析模式 {pattern_config['name']} 时出错: {e}")
            return None
    
    def _parse_basic_market_signal(
        self, 
        match, 
        message: str, 
        pattern_config: Dict[str, Any], 
        metadata: Optional[Dict[str, Any]]
    ) -> Optional[TradingSignal]:
        """解析基本市价信号"""
        symbol = self._normalize_symbol(match.group(1))
        direction = match.group(2)
        
        if not validate_symbol(symbol.replace('USDT', '')):
            return None
        
        side = OrderSide.BUY if direction == '多' else OrderSide.SELL
        
        # 设置默认杠杆
        from ..utils.config import config
        leverage = config.trading.default_leverage
        
        return TradingSignal(
            symbol=symbol,
            side=side,
            signal_type=SignalType.MARKET_ORDER,
            leverage=leverage,
            confidence=pattern_config['confidence'],
            raw_message=message,
            metadata=metadata or {}
        )
    
    def _parse_market_signal_with_amount(
        self, 
        match, 
        message: str, 
        pattern_config: Dict[str, Any], 
        metadata: Optional[Dict[str, Any]]
    ) -> Optional[TradingSignal]:
        """解析带金额的市价信号"""
        symbol = self._normalize_symbol(match.group(1))
        direction = match.group(2)
        amount = safe_float(match.group(3))
        
        if not validate_symbol(symbol.replace('USDT', '')) or amount <= 0:
            return None
        
        side = OrderSide.BUY if direction == '多' else OrderSide.SELL
        
        # 设置默认杠杆
        from ..utils.config import config
        leverage = config.trading.default_leverage
        
        return TradingSignal(
            symbol=symbol,
            side=side,
            signal_type=SignalType.MARKET_ORDER,
            amount=amount,
            leverage=leverage,
            confidence=pattern_config['confidence'],
            raw_message=message,
            metadata=metadata or {}
        )
    
    def _parse_limit_signal(
        self, 
        match, 
        message: str, 
        pattern_config: Dict[str, Any], 
        metadata: Optional[Dict[str, Any]]
    ) -> Optional[TradingSignal]:
        """解析限价信号"""
        symbol = self._normalize_symbol(match.group(1))
        direction = match.group(2)
        price = safe_float(match.group(3))
        
        if not validate_symbol(symbol.replace('USDT', '')) or price <= 0:
            return None
        
        side = OrderSide.BUY if direction == '多' else OrderSide.SELL
        
        # 设置默认杠杆
        from ..utils.config import config
        leverage = config.trading.default_leverage
        
        return TradingSignal(
            symbol=symbol,
            side=side,
            signal_type=SignalType.LIMIT_ORDER,
            price=price,
            leverage=leverage,
            confidence=pattern_config['confidence'],
            raw_message=message,
            metadata=metadata or {}
        )
    
    def _parse_full_signal(
        self, 
        match, 
        message: str, 
        pattern_config: Dict[str, Any], 
        metadata: Optional[Dict[str, Any]]
    ) -> Optional[TradingSignal]:
        """解析完整信号"""
        symbol = self._normalize_symbol(match.group(1))
        direction = match.group(2)
        amount = safe_float(match.group(3)) if match.group(3) else None
        stop_loss = safe_float(match.group(4)) if match.group(4) else None
        take_profit = safe_float(match.group(5)) if match.group(5) else None
        
        if not validate_symbol(symbol.replace('USDT', '')):
            return None
        
        side = OrderSide.BUY if direction == '多' else OrderSide.SELL
        
        # 提取杠杆信息，如果消息中没有杠杆信息则使用默认值
        leverage = self._extract_leverage(message)
        if leverage == 1:  # 如果没有检测到杠杆信息
            from ..utils.config import config
            leverage = config.trading.default_leverage
        
        return TradingSignal(
            symbol=symbol,
            side=side,
            signal_type=SignalType.MARKET_ORDER,
            amount=amount,
            stop_loss=stop_loss,
            take_profit=take_profit,
            leverage=leverage,
            confidence=pattern_config['confidence'],
            raw_message=message,
            metadata=metadata or {}
        )
    
    def _parse_english_signal(
        self, 
        match, 
        message: str, 
        pattern_config: Dict[str, Any], 
        metadata: Optional[Dict[str, Any]]
    ) -> Optional[TradingSignal]:
        """解析英文信号"""
        symbol = self._normalize_symbol(match.group(1))
        direction = match.group(2).lower()
        price = safe_float(match.group(3)) if match.group(3) else None
        
        if not validate_symbol(symbol.replace('USDT', '')):
            return None
        
        side = OrderSide.BUY if direction in ['long', 'buy'] else OrderSide.SELL
        signal_type = SignalType.LIMIT_ORDER if price else SignalType.MARKET_ORDER
        
        # 设置默认杠杆
        from ..utils.config import config
        leverage = config.trading.default_leverage
        
        return TradingSignal(
            symbol=symbol,
            side=side,
            signal_type=signal_type,
            price=price,
            leverage=leverage,
            confidence=pattern_config['confidence'],
            raw_message=message,
            metadata=metadata or {}
        )
    
    def _normalize_symbol(self, symbol: str) -> str:
        """规范化交易对符号"""
        symbol = symbol.upper().strip()
        
        # 使用别名映射
        if symbol in self.symbol_aliases:
            return self.symbol_aliases[symbol]
        
        # 如果不以USDT结尾，添加USDT
        if not symbol.endswith('USDT'):
            symbol += 'USDT'
        
        return symbol
    
    def _extract_leverage(self, message: str) -> int:
        """提取杠杆信息"""
        leverage_pattern = r'(\d+)[xX倍]'
        match = re.search(leverage_pattern, message)
        if match:
            leverage = safe_int(match.group(1))
            # 限制杠杆范围
            return max(1, min(leverage, 125))
        return 1
    
    def _parse_first_take_profit_signal(
        self, 
        match, 
        message: str, 
        pattern_config: Dict[str, Any], 
        metadata: Optional[Dict[str, Any]]
    ) -> Optional[TradingSignal]:
        """解析第一止盈信号"""
        take_profit_price = safe_float(match.group(1))
        
        if not take_profit_price or take_profit_price <= 0:
            logger.warning(f"无效的第一止盈价格: {take_profit_price}")
            return None
        
        logger.info(f"检测到第一止盈信号: {take_profit_price}")
        
        # 尝试从消息中推断币种
        inferred_symbol = self._infer_symbol_from_message(message)
        if inferred_symbol:
            logger.info(f"从消息中推断币种: {inferred_symbol}")
        
        return TradingSignal(
            symbol=inferred_symbol or "",  # 尝试推断币种，如果失败则为空
            side=OrderSide.BUY,  # 占位符，实际方向需要从当前持仓推断
            signal_type=SignalType.FIRST_TAKE_PROFIT,
            take_profit=take_profit_price,
            confidence=pattern_config['confidence'],
            raw_message=message,
            metadata=metadata or {}
        )
    
    def _infer_symbol_from_message(self, message: str) -> Optional[str]:
        """从消息中推断币种符号"""
        try:
            # 常见的币种模式
            symbol_patterns = [
                r'#(\w+)',  # #BTC, #ETH 等
                r'(\w+)USDT',  # BTCUSDT, ETHUSDT 等
                r'([A-Z]{2,10})(?:\s|$)',  # 大写字母币种名
            ]
            
            for pattern in symbol_patterns:
                matches = re.findall(pattern, message.upper())
                for match in matches:
                    # 验证是否是有效的币种符号
                    if len(match) >= 2 and len(match) <= 10 and match.isalpha():
                        # 标准化为USDT交易对
                        if not match.endswith('USDT'):
                            return f"{match}USDT"
                        return match
            
            return None
        except Exception as e:
            logger.warning(f"推断币种时出错: {e}")
            return None
    
    def validate_signal(self, signal: TradingSignal) -> Tuple[bool, List[str]]:
        """
        验证信号的有效性
        
        Args:
            signal: 要验证的信号
            
        Returns:
            (是否有效, 错误信息列表)
        """
        errors = []
        
        # 验证必要字段（第一止盈信号除外，它的symbol从上下文推断）
        if not signal.symbol and signal.signal_type != SignalType.FIRST_TAKE_PROFIT:
            errors.append("缺少交易对符号")
        elif signal.symbol and not validate_symbol(signal.symbol.replace('USDT', '')):
            errors.append(f"无效的交易对符号: {signal.symbol}")
        
        # 验证价格信息
        if signal.signal_type == SignalType.LIMIT_ORDER and not signal.price:
            errors.append("限价单缺少价格信息")
        
        if signal.price and signal.price <= 0:
            errors.append("价格必须大于0")
        
        if signal.amount and signal.amount <= 0:
            errors.append("交易金额必须大于0")
        
        # 验证止损止盈逻辑
        if signal.stop_loss and signal.take_profit:
            if signal.side == OrderSide.BUY:
                # 做多：止损价格应该低于止盈价格
                if signal.stop_loss >= signal.take_profit:
                    errors.append("做多时止损价格应低于止盈价格")
            else:
                # 做空：止损价格应该高于止盈价格
                if signal.stop_loss <= signal.take_profit:
                    errors.append("做空时止损价格应高于止盈价格")
        
        # 验证杠杆
        if signal.leverage < 1 or signal.leverage > 125:
            errors.append("杠杆倍数应在1-125之间")
        
        # 验证置信度
        if not 0 <= signal.confidence <= 1:
            errors.append("置信度应在0-1之间")
        
        return len(errors) == 0, errors
    
    def batch_parse_signals(self, messages: List[str]) -> List[TradingSignal]:
        """
        批量解析信号
        
        Args:
            messages: 消息列表
            
        Returns:
            解析成功的信号列表
        """
        signals = []
        
        for i, message in enumerate(messages):
            signal = self.parse_signal(message, {'batch_index': i})
            if signal:
                is_valid, errors = self.validate_signal(signal)
                if is_valid:
                    signals.append(signal)
                else:
                    logger.warning(f"信号验证失败: {errors}")
        
        logger.info(f"批量解析完成: {len(signals)}/{len(messages)} 个信号有效")
        return signals
    
    def get_signal_statistics(self, signals: List[TradingSignal]) -> Dict[str, Any]:
        """
        获取信号统计信息
        
        Args:
            signals: 信号列表
            
        Returns:
            统计信息字典
        """
        if not signals:
            return {}
        
        total_signals = len(signals)
        buy_signals = sum(1 for s in signals if s.side == OrderSide.BUY)
        sell_signals = total_signals - buy_signals
        
        symbols = [s.symbol for s in signals]
        symbol_counts = {symbol: symbols.count(symbol) for symbol in set(symbols)}
        
        avg_confidence = sum(s.confidence for s in signals) / total_signals
        
        signal_types = [s.signal_type.value for s in signals]
        type_counts = {signal_type: signal_types.count(signal_type) for signal_type in set(signal_types)}
        
        return {
            'total_signals': total_signals,
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
            'buy_percentage': (buy_signals / total_signals) * 100,
            'sell_percentage': (sell_signals / total_signals) * 100,
            'symbol_distribution': symbol_counts,
            'signal_type_distribution': type_counts,
            'average_confidence': round(avg_confidence, 3),
            'most_common_symbol': max(symbol_counts.items(), key=lambda x: x[1])[0] if symbol_counts else None
        }
