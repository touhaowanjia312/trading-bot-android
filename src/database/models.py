"""
数据库模型定义
定义所有数据表的结构和关系
"""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class TradingSignal(Base):
    """交易信号表"""
    __tablename__ = 'trading_signals'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(String(10), nullable=False)  # buy/sell
    signal_type = Column(String(20), nullable=False)  # market/limit/stop
    amount = Column(Float, nullable=True)
    price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    leverage = Column(Integer, default=1)
    confidence = Column(Float, default=0.8)
    raw_message = Column(Text, nullable=False)
    parsed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Telegram消息元数据
    message_id = Column(String(50), nullable=True)
    sender_id = Column(String(50), nullable=True)
    sender_name = Column(String(100), nullable=True)
    chat_id = Column(String(50), nullable=True)
    received_at = Column(DateTime, nullable=True)
    
    # 处理状态
    status = Column(String(20), default='pending')  # pending/processed/ignored/error
    processed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # 额外元数据
    metadata = Column(JSON, nullable=True)
    
    # 关联的交易执行
    executions = relationship("TradeExecution", back_populates="signal")
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'side': self.side,
            'signal_type': self.signal_type,
            'amount': self.amount,
            'price': self.price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'leverage': self.leverage,
            'confidence': self.confidence,
            'raw_message': self.raw_message,
            'parsed_at': self.parsed_at.isoformat() if self.parsed_at else None,
            'message_id': self.message_id,
            'sender_name': self.sender_name,
            'status': self.status,
            'metadata': self.metadata
        }


class TradeExecution(Base):
    """交易执行表"""
    __tablename__ = 'trade_executions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    signal_id = Column(Integer, ForeignKey('trading_signals.id'), nullable=False)
    
    # 订单信息
    bitget_order_id = Column(String(50), nullable=True, index=True)
    client_order_id = Column(String(50), nullable=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(String(10), nullable=False)  # buy/sell
    order_type = Column(String(20), nullable=False)  # market/limit
    
    # 价格和数量
    amount = Column(Float, nullable=False)  # 交易金额或数量
    price = Column(Float, nullable=True)  # 执行价格
    filled_amount = Column(Float, default=0.0)  # 已成交数量
    avg_fill_price = Column(Float, nullable=True)  # 平均成交价格
    
    # 手续费
    fee = Column(Float, default=0.0)
    fee_currency = Column(String(10), default='USDT')
    
    # 状态和时间
    status = Column(String(20), default='pending')  # pending/filled/cancelled/failed
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    filled_at = Column(DateTime, nullable=True)
    
    # 盈亏信息
    pnl = Column(Float, default=0.0)  # 已实现盈亏
    pnl_percentage = Column(Float, default=0.0)  # 盈亏百分比
    
    # 风险管理信息
    stop_loss_price = Column(Float, nullable=True)
    take_profit_price = Column(Float, nullable=True)
    
    # 额外信息
    notes = Column(Text, nullable=True)
    metadata = Column(JSON, nullable=True)
    
    # 关联
    signal = relationship("TradingSignal", back_populates="executions")
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'signal_id': self.signal_id,
            'bitget_order_id': self.bitget_order_id,
            'client_order_id': self.client_order_id,
            'symbol': self.symbol,
            'side': self.side,
            'order_type': self.order_type,
            'amount': self.amount,
            'price': self.price,
            'filled_amount': self.filled_amount,
            'avg_fill_price': self.avg_fill_price,
            'fee': self.fee,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'filled_at': self.filled_at.isoformat() if self.filled_at else None,
            'pnl': self.pnl,
            'pnl_percentage': self.pnl_percentage,
            'metadata': self.metadata
        }


class UserConfig(Base):
    """用户配置表"""
    __tablename__ = 'user_configs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    config_key = Column(String(100), nullable=False, unique=True, index=True)
    config_value = Column(Text, nullable=False)
    config_type = Column(String(20), default='string')  # string/int/float/bool/json
    description = Column(Text, nullable=True)
    is_encrypted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'config_key': self.config_key,
            'config_value': self.config_value,
            'config_type': self.config_type,
            'description': self.description,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class TelegramSession(Base):
    """Telegram会话表"""
    __tablename__ = 'telegram_sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_name = Column(String(100), nullable=False, unique=True, index=True)
    api_id = Column(String(20), nullable=False)
    api_hash = Column(String(100), nullable=False)
    phone_number = Column(String(20), nullable=False)
    is_active = Column(Boolean, default=True)
    
    # 会话状态
    is_authenticated = Column(Boolean, default=False)
    last_connected = Column(DateTime, nullable=True)
    connection_count = Column(Integer, default=0)
    
    # 监控配置
    target_group_id = Column(String(50), nullable=True)
    target_group_name = Column(String(200), nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'session_name': self.session_name,
            'phone_number': self.phone_number,
            'is_active': self.is_active,
            'is_authenticated': self.is_authenticated,
            'last_connected': self.last_connected.isoformat() if self.last_connected else None,
            'target_group_name': self.target_group_name
        }


class TradingStatistics(Base):
    """交易统计表"""
    __tablename__ = 'trading_statistics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime, nullable=False, index=True)  # 统计日期
    
    # 交易统计
    total_signals = Column(Integer, default=0)
    processed_signals = Column(Integer, default=0)
    successful_trades = Column(Integer, default=0)
    failed_trades = Column(Integer, default=0)
    
    # 盈亏统计
    total_pnl = Column(Float, default=0.0)
    realized_pnl = Column(Float, default=0.0)
    unrealized_pnl = Column(Float, default=0.0)
    total_fees = Column(Float, default=0.0)
    
    # 资金统计
    starting_balance = Column(Float, default=0.0)
    ending_balance = Column(Float, default=0.0)
    max_balance = Column(Float, default=0.0)
    min_balance = Column(Float, default=0.0)
    
    # 风险统计
    max_drawdown = Column(Float, default=0.0)
    win_rate = Column(Float, default=0.0)
    profit_factor = Column(Float, default=0.0)
    sharpe_ratio = Column(Float, default=0.0)
    
    # 交易品种统计
    most_traded_symbol = Column(String(20), nullable=True)
    symbol_distribution = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'date': self.date.isoformat() if self.date else None,
            'total_signals': self.total_signals,
            'processed_signals': self.processed_signals,
            'successful_trades': self.successful_trades,
            'failed_trades': self.failed_trades,
            'total_pnl': self.total_pnl,
            'realized_pnl': self.realized_pnl,
            'win_rate': self.win_rate,
            'max_drawdown': self.max_drawdown,
            'most_traded_symbol': self.most_traded_symbol
        }


class SystemLog(Base):
    """系统日志表"""
    __tablename__ = 'system_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    level = Column(String(10), nullable=False, index=True)  # DEBUG/INFO/WARNING/ERROR/CRITICAL
    logger_name = Column(String(50), nullable=False, index=True)
    message = Column(Text, nullable=False)
    
    # 上下文信息
    module = Column(String(50), nullable=True)
    function = Column(String(100), nullable=True)
    line_number = Column(Integer, nullable=True)
    
    # 异常信息
    exception_type = Column(String(100), nullable=True)
    exception_message = Column(Text, nullable=True)
    traceback = Column(Text, nullable=True)
    
    # 额外数据
    extra_data = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'level': self.level,
            'logger_name': self.logger_name,
            'message': self.message,
            'module': self.module,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class ApiUsage(Base):
    """API使用统计表"""
    __tablename__ = 'api_usage'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    api_name = Column(String(50), nullable=False, index=True)  # telegram/bitget
    endpoint = Column(String(200), nullable=False)
    method = Column(String(10), nullable=False)  # GET/POST/PUT/DELETE
    
    # 请求信息
    request_params = Column(JSON, nullable=True)
    response_status = Column(String(10), nullable=True)
    response_time = Column(Float, nullable=True)  # 响应时间（毫秒）
    
    # 错误信息
    error_code = Column(String(20), nullable=True)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'api_name': self.api_name,
            'endpoint': self.endpoint,
            'method': self.method,
            'response_status': self.response_status,
            'response_time': self.response_time,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
