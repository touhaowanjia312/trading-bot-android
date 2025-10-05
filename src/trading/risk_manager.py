"""
风险管理模块
负责交易风险控制，包括仓位管理、止损止盈、资金管理等
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from .signal_parser import TradingSignal, OrderSide
from ..utils.config import config
from ..utils.logger import get_logger
from ..utils.helpers import safe_float, calculate_position_size

logger = get_logger("RiskManager")


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskMetrics:
    """风险指标"""
    total_balance: float = 0.0
    used_margin: float = 0.0
    available_balance: float = 0.0
    total_pnl: float = 0.0
    daily_pnl: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW
    position_count: int = 0
    max_position_size: float = 0.0


@dataclass
class PositionInfo:
    """持仓信息"""
    symbol: str
    side: str
    size: float
    entry_price: float
    current_price: float
    pnl: float
    pnl_percentage: float
    created_at: datetime
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


class RiskManager:
    """风险管理器"""
    
    def __init__(self):
        self.max_daily_loss = config.trading.max_position_size * 0.05  # 日最大亏损5%
        self.max_position_size = config.trading.max_position_size
        self.risk_percentage = config.trading.risk_percentage
        self.stop_loss_percentage = config.trading.stop_loss_percentage
        self.take_profit_percentage = config.trading.take_profit_percentage
        
        # 风险控制状态
        self.daily_pnl = 0.0
        self.trade_count_today = 0
        self.consecutive_losses = 0
        self.last_reset_date = datetime.now(timezone.utc).date()
        
        # 持仓记录
        self.positions: Dict[str, PositionInfo] = {}
        self.trade_history: List[Dict[str, Any]] = []
        
        # 风险限制
        self.max_trades_per_day = 50
        self.max_consecutive_losses = 5
        self.cooldown_period = timedelta(minutes=30)
        self.last_trade_time: Optional[datetime] = None
    
    def check_signal_risk(self, signal: TradingSignal, current_balance: float) -> Tuple[bool, str, Dict[str, Any]]:
        """
        检查信号风险
        
        Args:
            signal: 交易信号
            current_balance: 当前余额
            
        Returns:
            (是否允许交易, 风险说明, 风险详情)
        """
        risk_details = {}
        
        # 重置日计数器
        self._reset_daily_counters()
        
        # 1. 检查余额
        if current_balance <= 0:
            return False, "账户余额不足", risk_details
        
        # 2. 检查日交易次数
        if self.trade_count_today >= self.max_trades_per_day:
            return False, f"已达到日交易次数限制({self.max_trades_per_day})", risk_details
        
        # 3. 检查日亏损限制
        if self.daily_pnl < -self.max_daily_loss:
            return False, f"已达到日最大亏损限制({self.max_daily_loss})", risk_details
        
        # 4. 检查连续亏损
        if self.consecutive_losses >= self.max_consecutive_losses:
            return False, f"连续亏损次数过多({self.consecutive_losses})", risk_details
        
        # 5. 检查冷却期
        if self._in_cooldown():
            return False, "处于交易冷却期", risk_details
        
        # 6. 检查仓位大小
        suggested_amount = signal.amount or self._calculate_suggested_amount(current_balance, signal)
        if suggested_amount > self.max_position_size:
            return False, f"交易金额超过最大限制({self.max_position_size})", risk_details
        
        # 7. 检查同币种持仓
        existing_position = self.positions.get(signal.symbol)
        if existing_position:
            if existing_position.side == signal.side.value:
                return False, f"已存在相同方向的{signal.symbol}持仓", risk_details
        
        # 8. 计算风险指标
        risk_metrics = self._calculate_risk_metrics(current_balance)
        risk_details.update({
            'suggested_amount': suggested_amount,
            'risk_percentage': self.risk_percentage,
            'current_positions': len(self.positions),
            'daily_pnl': self.daily_pnl,
            'consecutive_losses': self.consecutive_losses,
            'risk_level': risk_metrics.risk_level.value
        })
        
        # 9. 根据风险等级决定
        if risk_metrics.risk_level == RiskLevel.CRITICAL:
            return False, "当前风险等级过高，暂停交易", risk_details
        
        logger.info(f"信号风险检查通过: {signal.symbol} {signal.side.value}")
        return True, "风险检查通过", risk_details
    
    def _reset_daily_counters(self):
        """重置日计数器"""
        current_date = datetime.now(timezone.utc).date()
        if current_date != self.last_reset_date:
            self.daily_pnl = 0.0
            self.trade_count_today = 0
            self.last_reset_date = current_date
            logger.info("日交易计数器已重置")
    
    def _in_cooldown(self) -> bool:
        """检查是否在冷却期"""
        if not self.last_trade_time:
            return False
        
        return datetime.now(timezone.utc) - self.last_trade_time < self.cooldown_period
    
    def _calculate_suggested_amount(self, balance: float, signal: TradingSignal) -> float:
        """计算建议交易金额"""
        # 基于风险百分比计算
        risk_amount = balance * (self.risk_percentage / 100)
        
        # 考虑止损价格
        if signal.stop_loss and signal.price:
            position_size = calculate_position_size(
                balance, 
                self.risk_percentage, 
                signal.price, 
                signal.stop_loss
            )
            return min(position_size, risk_amount)
        
        return risk_amount
    
    def _calculate_risk_metrics(self, current_balance: float) -> RiskMetrics:
        """计算当前风险指标"""
        # 计算总盈亏
        total_pnl = sum(pos.pnl for pos in self.positions.values())
        
        # 计算已用保证金
        used_margin = sum(pos.size for pos in self.positions.values())
        
        # 计算胜率
        if self.trade_history:
            winning_trades = sum(1 for trade in self.trade_history if trade.get('pnl', 0) > 0)
            win_rate = winning_trades / len(self.trade_history) * 100
        else:
            win_rate = 0.0
        
        # 计算最大回撤
        max_drawdown = self._calculate_max_drawdown()
        
        # 确定风险等级
        risk_level = self._determine_risk_level(current_balance, total_pnl, used_margin)
        
        return RiskMetrics(
            total_balance=current_balance,
            used_margin=used_margin,
            available_balance=current_balance - used_margin,
            total_pnl=total_pnl,
            daily_pnl=self.daily_pnl,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            risk_level=risk_level,
            position_count=len(self.positions),
            max_position_size=max(pos.size for pos in self.positions.values()) if self.positions else 0.0
        )
    
    def _calculate_max_drawdown(self) -> float:
        """计算最大回撤"""
        if not self.trade_history:
            return 0.0
        
        cumulative_pnl = 0.0
        peak = 0.0
        max_drawdown = 0.0
        
        for trade in self.trade_history:
            cumulative_pnl += trade.get('pnl', 0)
            if cumulative_pnl > peak:
                peak = cumulative_pnl
            
            drawdown = peak - cumulative_pnl
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        return max_drawdown
    
    def _determine_risk_level(self, balance: float, total_pnl: float, used_margin: float) -> RiskLevel:
        """确定风险等级"""
        # 计算保证金使用率
        margin_ratio = used_margin / balance if balance > 0 else 0
        
        # 计算盈亏比例
        pnl_ratio = abs(total_pnl) / balance if balance > 0 else 0
        
        # 综合评估风险等级
        if margin_ratio > 0.8 or pnl_ratio > 0.2 or self.consecutive_losses >= 4:
            return RiskLevel.CRITICAL
        elif margin_ratio > 0.6 or pnl_ratio > 0.15 or self.consecutive_losses >= 3:
            return RiskLevel.HIGH
        elif margin_ratio > 0.4 or pnl_ratio > 0.1 or self.consecutive_losses >= 2:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def add_position(self, signal: TradingSignal, entry_price: float, size: float):
        """添加持仓记录"""
        position = PositionInfo(
            symbol=signal.symbol,
            side=signal.side.value,
            size=size,
            entry_price=entry_price,
            current_price=entry_price,
            pnl=0.0,
            pnl_percentage=0.0,
            created_at=datetime.now(timezone.utc),
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit
        )
        
        self.positions[signal.symbol] = position
        self.trade_count_today += 1
        self.last_trade_time = datetime.now(timezone.utc)
        
        logger.info(f"添加持仓: {signal.symbol} {signal.side.value} {size}")
    
    def update_position(self, symbol: str, current_price: float):
        """更新持仓信息"""
        if symbol not in self.positions:
            return
        
        position = self.positions[symbol]
        position.current_price = current_price
        
        # 计算盈亏
        if position.side == "buy":
            position.pnl = (current_price - position.entry_price) * position.size / position.entry_price
        else:
            position.pnl = (position.entry_price - current_price) * position.size / position.entry_price
        
        position.pnl_percentage = (position.pnl / position.size) * 100
        
        # 检查止损止盈
        self._check_stop_conditions(position)
    
    def _check_stop_conditions(self, position: PositionInfo) -> Optional[str]:
        """检查止损止盈条件"""
        if position.side == "buy":
            # 做多检查
            if position.stop_loss and position.current_price <= position.stop_loss:
                return "stop_loss"
            if position.take_profit and position.current_price >= position.take_profit:
                return "take_profit"
        else:
            # 做空检查
            if position.stop_loss and position.current_price >= position.stop_loss:
                return "stop_loss"
            if position.take_profit and position.current_price <= position.take_profit:
                return "take_profit"
        
        return None
    
    def close_position(self, symbol: str, close_price: float, reason: str = "manual"):
        """关闭持仓"""
        if symbol not in self.positions:
            return
        
        position = self.positions[symbol]
        
        # 更新最终盈亏
        self.update_position(symbol, close_price)
        
        # 记录交易历史
        trade_record = {
            'symbol': symbol,
            'side': position.side,
            'size': position.size,
            'entry_price': position.entry_price,
            'close_price': close_price,
            'pnl': position.pnl,
            'pnl_percentage': position.pnl_percentage,
            'hold_time': (datetime.now(timezone.utc) - position.created_at).total_seconds(),
            'close_reason': reason,
            'closed_at': datetime.now(timezone.utc)
        }
        
        self.trade_history.append(trade_record)
        
        # 更新统计
        self.daily_pnl += position.pnl
        
        if position.pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
        
        # 移除持仓
        del self.positions[symbol]
        
        logger.info(f"关闭持仓: {symbol} 盈亏: {position.pnl:.2f} 原因: {reason}")
    
    def get_position_summary(self) -> Dict[str, Any]:
        """获取持仓摘要"""
        if not self.positions:
            return {
                'total_positions': 0,
                'total_pnl': 0.0,
                'total_size': 0.0
            }
        
        total_pnl = sum(pos.pnl for pos in self.positions.values())
        total_size = sum(pos.size for pos in self.positions.values())
        
        return {
            'total_positions': len(self.positions),
            'total_pnl': total_pnl,
            'total_size': total_size,
            'positions': [
                {
                    'symbol': pos.symbol,
                    'side': pos.side,
                    'size': pos.size,
                    'pnl': pos.pnl,
                    'pnl_percentage': pos.pnl_percentage
                }
                for pos in self.positions.values()
            ]
        }
    
    def get_risk_report(self, current_balance: float) -> Dict[str, Any]:
        """获取风险报告"""
        risk_metrics = self._calculate_risk_metrics(current_balance)
        
        return {
            'risk_metrics': {
                'total_balance': risk_metrics.total_balance,
                'used_margin': risk_metrics.used_margin,
                'available_balance': risk_metrics.available_balance,
                'total_pnl': risk_metrics.total_pnl,
                'daily_pnl': risk_metrics.daily_pnl,
                'max_drawdown': risk_metrics.max_drawdown,
                'win_rate': risk_metrics.win_rate,
                'risk_level': risk_metrics.risk_level.value,
                'position_count': risk_metrics.position_count
            },
            'trading_stats': {
                'trade_count_today': self.trade_count_today,
                'consecutive_losses': self.consecutive_losses,
                'total_trades': len(self.trade_history),
                'in_cooldown': self._in_cooldown()
            },
            'limits': {
                'max_daily_loss': self.max_daily_loss,
                'max_position_size': self.max_position_size,
                'max_trades_per_day': self.max_trades_per_day,
                'max_consecutive_losses': self.max_consecutive_losses
            }
        }
    
    def adjust_risk_parameters(self, **kwargs):
        """调整风险参数"""
        if 'risk_percentage' in kwargs:
            self.risk_percentage = max(0.1, min(10.0, kwargs['risk_percentage']))
        
        if 'stop_loss_percentage' in kwargs:
            self.stop_loss_percentage = max(1.0, min(20.0, kwargs['stop_loss_percentage']))
        
        if 'take_profit_percentage' in kwargs:
            self.take_profit_percentage = max(1.0, min(50.0, kwargs['take_profit_percentage']))
        
        if 'max_position_size' in kwargs:
            self.max_position_size = max(10.0, kwargs['max_position_size'])
        
        logger.info(f"风险参数已调整: {kwargs}")
    
    def emergency_stop(self):
        """紧急停止交易"""
        self.consecutive_losses = self.max_consecutive_losses
        self.last_trade_time = datetime.now(timezone.utc)
        logger.warning("紧急停止交易已激活")
    
    def reset_risk_state(self):
        """重置风险状态"""
        self.consecutive_losses = 0
        self.daily_pnl = 0.0
        self.trade_count_today = 0
        self.last_trade_time = None
        logger.info("风险状态已重置")
