"""
数据库操作模块
提供数据库连接、CRUD操作和数据管理功能
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Union
from pathlib import Path
from sqlalchemy import create_engine, desc, func, and_, or_
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from contextlib import contextmanager

from .models import (
    Base, TradingSignal, TradeExecution, UserConfig, 
    TelegramSession, TradingStatistics, SystemLog, ApiUsage
)
from ..utils.config import config
from ..utils.logger import database_logger
from ..trading.signal_parser import TradingSignal as SignalData


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or config.database.url
        self.engine = None
        self.SessionLocal = None
        self._initialized = False
    
    def initialize(self):
        """初始化数据库连接"""
        try:
            # 确保数据库目录存在
            if self.database_url.startswith('sqlite:///'):
                db_path = Path(self.database_url.replace('sqlite:///', ''))
                db_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 创建数据库引擎
            self.engine = create_engine(
                self.database_url,
                echo=False,  # 设为True可以看到SQL语句
                pool_pre_ping=True,  # 连接前检查
                pool_recycle=3600,   # 连接回收时间
                connect_args={'check_same_thread': False} if 'sqlite' in self.database_url else {}
            )
            
            # 创建会话工厂
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
            # 创建所有表
            Base.metadata.create_all(bind=self.engine)
            
            self._initialized = True
            database_logger.info("数据库初始化成功")
            
        except Exception as e:
            database_logger.error(f"数据库初始化失败: {e}")
            raise
    
    @contextmanager
    def get_session(self):
        """获取数据库会话的上下文管理器"""
        if not self._initialized:
            self.initialize()
        
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            database_logger.error(f"数据库操作失败: {e}")
            raise
        finally:
            session.close()
    
    def test_connection(self) -> bool:
        """测试数据库连接"""
        try:
            with self.get_session() as session:
                session.execute("SELECT 1")
            database_logger.info("数据库连接测试成功")
            return True
        except Exception as e:
            database_logger.error(f"数据库连接测试失败: {e}")
            return False
    
    # ========== 交易信号相关操作 ==========
    
    def save_trading_signal(self, signal_data: SignalData, metadata: Optional[Dict] = None) -> int:
        """
        保存交易信号
        
        Args:
            signal_data: 信号数据
            metadata: 额外元数据
            
        Returns:
            信号ID
        """
        try:
            with self.get_session() as session:
                signal = TradingSignal(
                    symbol=signal_data.symbol,
                    side=signal_data.side.value,
                    signal_type=signal_data.signal_type.value,
                    amount=signal_data.amount,
                    price=signal_data.price,
                    stop_loss=signal_data.stop_loss,
                    take_profit=signal_data.take_profit,
                    leverage=signal_data.leverage,
                    confidence=signal_data.confidence,
                    raw_message=signal_data.raw_message,
                    parsed_at=signal_data.parsed_at,
                    metadata=metadata or signal_data.metadata
                )
                
                # 如果有Telegram消息元数据
                if metadata:
                    signal.message_id = metadata.get('message_id')
                    signal.sender_id = metadata.get('sender_id')
                    signal.sender_name = metadata.get('sender_name')
                    signal.chat_id = metadata.get('chat_id')
                    signal.received_at = metadata.get('received_at')
                
                session.add(signal)
                session.flush()  # 获取ID
                
                signal_id = signal.id
                database_logger.log_data_saved('trading_signals', str(signal_id))
                return signal_id
                
        except Exception as e:
            database_logger.error(f"保存交易信号失败: {e}")
            raise
    
    def get_trading_signals(
        self, 
        limit: int = 100, 
        status: Optional[str] = None,
        symbol: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        获取交易信号列表
        
        Args:
            limit: 返回数量限制
            status: 状态过滤
            symbol: 交易对过滤
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            信号列表
        """
        try:
            with self.get_session() as session:
                query = session.query(TradingSignal)
                
                # 应用过滤条件
                if status:
                    query = query.filter(TradingSignal.status == status)
                if symbol:
                    query = query.filter(TradingSignal.symbol == symbol)
                if start_date:
                    query = query.filter(TradingSignal.parsed_at >= start_date)
                if end_date:
                    query = query.filter(TradingSignal.parsed_at <= end_date)
                
                # 按时间倒序排列
                signals = query.order_by(desc(TradingSignal.parsed_at)).limit(limit).all()
                
                return [signal.to_dict() for signal in signals]
                
        except Exception as e:
            database_logger.error(f"获取交易信号失败: {e}")
            return []
    
    def update_signal_status(self, signal_id: int, status: str, error_message: Optional[str] = None):
        """
        更新信号状态
        
        Args:
            signal_id: 信号ID
            status: 新状态
            error_message: 错误信息
        """
        try:
            with self.get_session() as session:
                signal = session.query(TradingSignal).filter(TradingSignal.id == signal_id).first()
                if signal:
                    signal.status = status
                    signal.processed_at = datetime.now(timezone.utc)
                    if error_message:
                        signal.error_message = error_message
                    
                    database_logger.info(f"信号状态已更新: {signal_id} -> {status}")
                
        except Exception as e:
            database_logger.error(f"更新信号状态失败: {e}")
    
    # ========== 交易执行相关操作 ==========
    
    def save_trade_execution(self, execution_data: Dict[str, Any]) -> int:
        """
        保存交易执行记录
        
        Args:
            execution_data: 执行数据
            
        Returns:
            执行记录ID
        """
        try:
            with self.get_session() as session:
                execution = TradeExecution(
                    signal_id=execution_data.get('signal_id'),
                    bitget_order_id=execution_data.get('bitget_order_id'),
                    client_order_id=execution_data.get('client_order_id'),
                    symbol=execution_data.get('symbol'),
                    side=execution_data.get('side'),
                    order_type=execution_data.get('order_type', 'market'),
                    amount=execution_data.get('amount'),
                    price=execution_data.get('price'),
                    status=execution_data.get('status', 'pending'),
                    metadata=execution_data.get('metadata')
                )
                
                session.add(execution)
                session.flush()
                
                execution_id = execution.id
                database_logger.log_data_saved('trade_executions', str(execution_id))
                return execution_id
                
        except Exception as e:
            database_logger.error(f"保存交易执行失败: {e}")
            raise
    
    def update_trade_execution(self, execution_id: int, update_data: Dict[str, Any]):
        """
        更新交易执行记录
        
        Args:
            execution_id: 执行记录ID
            update_data: 更新数据
        """
        try:
            with self.get_session() as session:
                execution = session.query(TradeExecution).filter(TradeExecution.id == execution_id).first()
                if execution:
                    for key, value in update_data.items():
                        if hasattr(execution, key):
                            setattr(execution, key, value)
                    
                    execution.updated_at = datetime.now(timezone.utc)
                    database_logger.info(f"交易执行记录已更新: {execution_id}")
                
        except Exception as e:
            database_logger.error(f"更新交易执行失败: {e}")
    
    def get_trade_executions(
        self, 
        limit: int = 100,
        symbol: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        获取交易执行记录
        
        Args:
            limit: 返回数量限制
            symbol: 交易对过滤
            status: 状态过滤
            start_date: 开始日期
            
        Returns:
            执行记录列表
        """
        try:
            with self.get_session() as session:
                query = session.query(TradeExecution)
                
                if symbol:
                    query = query.filter(TradeExecution.symbol == symbol)
                if status:
                    query = query.filter(TradeExecution.status == status)
                if start_date:
                    query = query.filter(TradeExecution.created_at >= start_date)
                
                executions = query.order_by(desc(TradeExecution.created_at)).limit(limit).all()
                
                return [execution.to_dict() for execution in executions]
                
        except Exception as e:
            database_logger.error(f"获取交易执行记录失败: {e}")
            return []
    
    # ========== 用户配置相关操作 ==========
    
    def save_config(self, key: str, value: Any, config_type: str = 'string', description: Optional[str] = None):
        """
        保存配置项
        
        Args:
            key: 配置键
            value: 配置值
            config_type: 配置类型
            description: 描述
        """
        try:
            with self.get_session() as session:
                # 检查是否已存在
                config_item = session.query(UserConfig).filter(UserConfig.config_key == key).first()
                
                if config_item:
                    # 更新现有配置
                    config_item.config_value = str(value)
                    config_item.config_type = config_type
                    config_item.updated_at = datetime.now(timezone.utc)
                    if description:
                        config_item.description = description
                else:
                    # 创建新配置
                    config_item = UserConfig(
                        config_key=key,
                        config_value=str(value),
                        config_type=config_type,
                        description=description
                    )
                    session.add(config_item)
                
                database_logger.info(f"配置已保存: {key}")
                
        except Exception as e:
            database_logger.error(f"保存配置失败: {e}")
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """
        获取配置项
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置值
        """
        try:
            with self.get_session() as session:
                config_item = session.query(UserConfig).filter(UserConfig.config_key == key).first()
                
                if not config_item:
                    return default
                
                # 根据类型转换值
                value = config_item.config_value
                config_type = config_item.config_type
                
                if config_type == 'int':
                    return int(value)
                elif config_type == 'float':
                    return float(value)
                elif config_type == 'bool':
                    return value.lower() in ('true', '1', 'yes', 'on')
                elif config_type == 'json':
                    import json
                    return json.loads(value)
                else:
                    return value
                    
        except Exception as e:
            database_logger.error(f"获取配置失败: {e}")
            return default
    
    # ========== 统计分析相关操作 ==========
    
    def get_trading_statistics(self, days: int = 30) -> Dict[str, Any]:
        """
        获取交易统计信息
        
        Args:
            days: 统计天数
            
        Returns:
            统计信息
        """
        try:
            with self.get_session() as session:
                start_date = datetime.now(timezone.utc) - timedelta(days=days)
                
                # 基本统计
                total_signals = session.query(TradingSignal).filter(
                    TradingSignal.parsed_at >= start_date
                ).count()
                
                processed_signals = session.query(TradingSignal).filter(
                    and_(
                        TradingSignal.parsed_at >= start_date,
                        TradingSignal.status == 'processed'
                    )
                ).count()
                
                successful_trades = session.query(TradeExecution).filter(
                    and_(
                        TradeExecution.created_at >= start_date,
                        TradeExecution.status == 'filled',
                        TradeExecution.pnl > 0
                    )
                ).count()
                
                total_trades = session.query(TradeExecution).filter(
                    and_(
                        TradeExecution.created_at >= start_date,
                        TradeExecution.status == 'filled'
                    )
                ).count()
                
                # 盈亏统计
                pnl_result = session.query(func.sum(TradeExecution.pnl)).filter(
                    and_(
                        TradeExecution.created_at >= start_date,
                        TradeExecution.status == 'filled'
                    )
                ).scalar()
                
                total_pnl = float(pnl_result) if pnl_result else 0.0
                
                # 交易对分布
                symbol_distribution = session.query(
                    TradingSignal.symbol,
                    func.count(TradingSignal.symbol)
                ).filter(
                    TradingSignal.parsed_at >= start_date
                ).group_by(TradingSignal.symbol).all()
                
                return {
                    'period_days': days,
                    'total_signals': total_signals,
                    'processed_signals': processed_signals,
                    'total_trades': total_trades,
                    'successful_trades': successful_trades,
                    'win_rate': (successful_trades / total_trades * 100) if total_trades > 0 else 0,
                    'total_pnl': total_pnl,
                    'symbol_distribution': dict(symbol_distribution)
                }
                
        except Exception as e:
            database_logger.error(f"获取交易统计失败: {e}")
            return {}
    
    def cleanup_old_data(self, days_to_keep: int = 90):
        """
        清理旧数据
        
        Args:
            days_to_keep: 保留天数
        """
        try:
            with self.get_session() as session:
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
                
                # 清理旧的系统日志
                old_logs = session.query(SystemLog).filter(SystemLog.created_at < cutoff_date).count()
                session.query(SystemLog).filter(SystemLog.created_at < cutoff_date).delete()
                
                # 清理旧的API使用记录
                old_api_usage = session.query(ApiUsage).filter(ApiUsage.created_at < cutoff_date).count()
                session.query(ApiUsage).filter(ApiUsage.created_at < cutoff_date).delete()
                
                database_logger.info(f"清理完成: 删除了 {old_logs} 条日志和 {old_api_usage} 条API记录")
                
        except Exception as e:
            database_logger.error(f"清理旧数据失败: {e}")
    
    def backup_database(self, backup_path: Optional[str] = None) -> bool:
        """
        备份数据库
        
        Args:
            backup_path: 备份文件路径
            
        Returns:
            是否成功
        """
        try:
            if not backup_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = f"data/backups/trading_bot_backup_{timestamp}.db"
            
            backup_file = Path(backup_path)
            backup_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 对于SQLite数据库，直接复制文件
            if 'sqlite' in self.database_url:
                import shutil
                source_path = self.database_url.replace('sqlite:///', '')
                shutil.copy2(source_path, backup_path)
                database_logger.info(f"数据库备份成功: {backup_path}")
                return True
            else:
                database_logger.warning("非SQLite数据库备份功能暂未实现")
                return False
                
        except Exception as e:
            database_logger.error(f"数据库备份失败: {e}")
            return False


# 全局数据库管理器实例
db_manager = DatabaseManager()
