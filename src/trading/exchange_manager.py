"""
交易所管理模块
支持多个交易所的统一接口管理
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass

from .signal_parser import TradingSignal
from ..utils.logger import get_logger

logger = get_logger("ExchangeManager")


class ExchangeType(Enum):
    """交易所类型枚举"""
    BITGET = "bitget"
    BINANCE = "binance"
    BYBIT = "bybit"
    OKEX = "okex"
    WEEX = "weex"


@dataclass
class ExchangeConfig:
    """交易所配置"""
    exchange_type: ExchangeType
    api_key: str
    secret_key: str
    passphrase: Optional[str] = None  # 某些交易所需要
    sandbox: bool = False
    enabled: bool = True
    name: str = ""  # 用户自定义名称
    
    def __post_init__(self):
        if not self.name:
            self.name = self.exchange_type.value.title()


class BaseExchangeClient(ABC):
    """交易所客户端抽象基类"""
    
    def __init__(self, config: ExchangeConfig):
        self.config = config
        self.exchange_type = config.exchange_type
        self.name = config.name
        self.enabled = config.enabled
    
    @abstractmethod
    async def initialize(self) -> bool:
        """初始化客户端"""
        pass
    
    @abstractmethod
    async def get_balance(self, currency: str = "USDT") -> float:
        """获取余额"""
        pass
    
    @abstractmethod
    async def execute_signal(self, signal: TradingSignal) -> Optional[Dict[str, Any]]:
        """执行交易信号"""
        pass
    
    @abstractmethod
    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取持仓信息"""
        pass
    
    @abstractmethod
    async def close_position_partial(self, symbol: str, percentage: float = 50.0) -> Optional[Dict[str, Any]]:
        """部分平仓"""
        pass
    
    @abstractmethod
    async def set_break_even_stop_loss(self, symbol: str, entry_price: float) -> Optional[Dict[str, Any]]:
        """设置保本止损"""
        pass
    
    @abstractmethod
    async def handle_first_take_profit(self, signal: TradingSignal, recent_trades: List[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """处理第一止盈"""
        pass
    
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """获取客户端状态"""
        pass


class ExchangeManager:
    """交易所管理器"""
    
    def __init__(self):
        self.exchanges: Dict[str, BaseExchangeClient] = {}
        self.active_exchange: Optional[BaseExchangeClient] = None
        self.configs: List[ExchangeConfig] = []
    
    def add_exchange(self, config: ExchangeConfig) -> bool:
        """添加交易所"""
        try:
            if config.exchange_type == ExchangeType.BITGET:
                from .bitget_client import BitgetClient
                client = BitgetClientWrapper(config)
            elif config.exchange_type == ExchangeType.BINANCE:
                client = BinanceClientWrapper(config)
            elif config.exchange_type == ExchangeType.BYBIT:
                client = BybitClientWrapper(config)
            elif config.exchange_type == ExchangeType.OKEX:
                client = OkexClientWrapper(config)
            elif config.exchange_type == ExchangeType.WEEX:
                client = WeexClientWrapper(config)
            else:
                logger.error(f"不支持的交易所类型: {config.exchange_type}")
                return False
            
            self.exchanges[config.name] = client
            self.configs.append(config)
            
            # 如果是第一个启用的交易所，设为活跃交易所
            if config.enabled and not self.active_exchange:
                self.active_exchange = client
            
            logger.info(f"已添加交易所: {config.name} ({config.exchange_type.value})")
            return True
            
        except Exception as e:
            logger.error(f"添加交易所失败: {e}")
            return False
    
    def set_active_exchange(self, name: str) -> bool:
        """设置活跃交易所"""
        if name in self.exchanges and self.exchanges[name].enabled:
            self.active_exchange = self.exchanges[name]
            logger.info(f"已切换到交易所: {name}")
            return True
        return False
    
    def get_active_exchange(self) -> Optional[BaseExchangeClient]:
        """获取当前活跃交易所"""
        return self.active_exchange
    
    def get_exchange_list(self) -> List[Dict[str, Any]]:
        """获取交易所列表"""
        return [
            {
                'name': config.name,
                'type': config.exchange_type.value,
                'enabled': config.enabled,
                'active': self.active_exchange and self.active_exchange.name == config.name
            }
            for config in self.configs
        ]
    
    async def initialize_all(self) -> Dict[str, bool]:
        """初始化所有交易所"""
        results = {}
        for name, client in self.exchanges.items():
            if client.enabled:
                try:
                    results[name] = await client.initialize()
                except Exception as e:
                    logger.error(f"初始化交易所 {name} 失败: {e}")
                    results[name] = False
            else:
                results[name] = False
        return results


# Bitget客户端包装器
class BitgetClientWrapper(BaseExchangeClient):
    """Bitget客户端包装器"""
    
    def __init__(self, config: ExchangeConfig):
        super().__init__(config)
        self.client = None
    
    async def initialize(self) -> bool:
        try:
            from .bitget_client import BitgetClient
            self.client = BitgetClient(
                api_key=self.config.api_key,
                secret_key=self.config.secret_key,
                passphrase=self.config.passphrase,
                sandbox=self.config.sandbox
            )
            # 测试连接
            await self.client.get_balance()
            return True
        except Exception as e:
            logger.error(f"Bitget客户端初始化失败: {e}")
            return False
    
    async def get_balance(self, currency: str = "USDT") -> float:
        if self.client:
            return await self.client.get_balance(currency)
        return 0.0
    
    async def execute_signal(self, signal: TradingSignal) -> Optional[Dict[str, Any]]:
        if self.client:
            return await self.client.execute_signal(signal)
        return None
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        if self.client:
            return await self.client.get_positions(symbol)
        return []
    
    async def close_position_partial(self, symbol: str, percentage: float = 50.0) -> Optional[Dict[str, Any]]:
        if self.client:
            return await self.client.close_position_partial(symbol, percentage)
        return None
    
    async def set_break_even_stop_loss(self, symbol: str, entry_price: float) -> Optional[Dict[str, Any]]:
        if self.client:
            return await self.client.set_break_even_stop_loss(symbol, entry_price)
        return None
    
    async def handle_first_take_profit(self, signal: TradingSignal, recent_trades: List[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        if self.client:
            return await self.client.handle_first_take_profit(signal, recent_trades)
        return None
    
    def get_status(self) -> Dict[str, Any]:
        if self.client:
            return self.client.get_status()
        return {'initialized': False, 'error': 'Client not initialized'}


# 其他交易所的占位符实现
class BinanceClientWrapper(BaseExchangeClient):
    """Binance客户端包装器 (占位符)"""
    
    async def initialize(self) -> bool:
        logger.warning("Binance交易所暂未实现")
        return False
    
    async def get_balance(self, currency: str = "USDT") -> float:
        return 0.0
    
    async def execute_signal(self, signal: TradingSignal) -> Optional[Dict[str, Any]]:
        return None
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        return []
    
    async def close_position_partial(self, symbol: str, percentage: float = 50.0) -> Optional[Dict[str, Any]]:
        return None
    
    async def set_break_even_stop_loss(self, symbol: str, entry_price: float) -> Optional[Dict[str, Any]]:
        return None
    
    async def handle_first_take_profit(self, signal: TradingSignal, recent_trades: List[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        return None
    
    def get_status(self) -> Dict[str, Any]:
        return {'initialized': False, 'error': 'Not implemented'}


class BybitClientWrapper(BaseExchangeClient):
    """Bybit客户端包装器 (占位符)"""
    
    async def initialize(self) -> bool:
        logger.warning("Bybit交易所暂未实现")
        return False
    
    async def get_balance(self, currency: str = "USDT") -> float:
        return 0.0
    
    async def execute_signal(self, signal: TradingSignal) -> Optional[Dict[str, Any]]:
        return None
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        return []
    
    async def close_position_partial(self, symbol: str, percentage: float = 50.0) -> Optional[Dict[str, Any]]:
        return None
    
    async def set_break_even_stop_loss(self, symbol: str, entry_price: float) -> Optional[Dict[str, Any]]:
        return None
    
    async def handle_first_take_profit(self, signal: TradingSignal, recent_trades: List[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        return None
    
    def get_status(self) -> Dict[str, Any]:
        return {'initialized': False, 'error': 'Not implemented'}


class OkexClientWrapper(BaseExchangeClient):
    """OKEx客户端包装器 (占位符)"""
    
    async def initialize(self) -> bool:
        logger.warning("OKEx交易所暂未实现")
        return False
    
    async def get_balance(self, currency: str = "USDT") -> float:
        return 0.0
    
    async def execute_signal(self, signal: TradingSignal) -> Optional[Dict[str, Any]]:
        return None
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        return []
    
    async def close_position_partial(self, symbol: str, percentage: float = 50.0) -> Optional[Dict[str, Any]]:
        return None
    
    async def set_break_even_stop_loss(self, symbol: str, entry_price: float) -> Optional[Dict[str, Any]]:
        return None
    
    async def handle_first_take_profit(self, signal: TradingSignal, recent_trades: List[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        return None
    
    def get_status(self) -> Dict[str, Any]:
        return {'initialized': False, 'error': 'Not implemented'}


class WeexClientWrapper(BaseExchangeClient):
    """Weex客户端包装器"""
    
    def __init__(self, config: ExchangeConfig):
        super().__init__(config)
        self.client = None
    
    async def initialize(self) -> bool:
        try:
            # 这里将来可以实现Weex客户端初始化
            logger.info("Weex交易所客户端初始化...")
            # 暂时返回True，表示配置已就绪
            return True
        except Exception as e:
            logger.error(f"Weex客户端初始化失败: {e}")
            return False
    
    async def get_balance(self, currency: str = "USDT") -> float:
        logger.warning("Weex get_balance 功能开发中")
        return 0.0
    
    async def execute_signal(self, signal: TradingSignal) -> Optional[Dict[str, Any]]:
        logger.warning("Weex execute_signal 功能开发中")
        return None
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        logger.warning("Weex get_positions 功能开发中")
        return []
    
    async def close_position_partial(self, symbol: str, percentage: float = 50.0) -> Optional[Dict[str, Any]]:
        logger.warning("Weex close_position_partial 功能开发中")
        return None
    
    async def set_break_even_stop_loss(self, symbol: str, entry_price: float) -> Optional[Dict[str, Any]]:
        logger.warning("Weex set_break_even_stop_loss 功能开发中")
        return None
    
    async def handle_first_take_profit(self, signal: TradingSignal, recent_trades: List[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        logger.warning("Weex handle_first_take_profit 功能开发中")
        return None
    
    def get_status(self) -> Dict[str, Any]:
        return {
            'initialized': True,
            'api_key_configured': bool(self.config.api_key),
            'ready_for_development': True,
            'note': 'Weex API integration ready for implementation'
        }
