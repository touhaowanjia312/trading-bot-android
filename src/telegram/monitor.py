"""
Telegram群组消息监控模块
负责实时监控指定群组的消息并识别交易信号
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional, Callable, Dict, Any, List
from telethon import events
from telethon.tl.types import Channel, Chat, User

from .auth import TelegramAuth
from ..utils.config import config
from ..utils.logger import telegram_logger
from ..utils.helpers import parse_trading_signal


class TelegramMonitor:
    """Telegram群组消息监控器"""
    
    def __init__(self):
        self.auth = TelegramAuth()
        self.is_monitoring = False
        self.signal_callbacks: List[Callable] = []
        self.message_callbacks: List[Callable] = []
        self.error_callbacks: List[Callable] = []
        self.target_group = None
        self._monitoring_task: Optional[asyncio.Task] = None
    
    async def initialize(self) -> bool:
        """
        初始化监控器
        
        Returns:
            是否成功初始化
        """
        try:
            # 初始化Telegram认证
            if not await self.auth.initialize_client():
                return False
            
            # 检查认证状态
            if not self.auth.is_authenticated:
                auth_result = await self.auth.authenticate()
                if not auth_result['success']:
                    telegram_logger.error(f"Telegram认证失败: {auth_result}")
                    return False
            
            # 获取目标群组
            await self._get_target_group()
            
            telegram_logger.info("Telegram监控器初始化成功")
            return True
            
        except Exception as e:
            telegram_logger.error(f"监控器初始化失败: {e}")
            return False
    
    async def _get_target_group(self):
        """获取目标监控群组"""
        try:
            group_identifier = config.telegram.group_id
            
            # 尝试通过不同方式获取群组
            if group_identifier.startswith('@'):
                # 通过用户名获取
                self.target_group = await self.auth.client.get_entity(group_identifier)
            elif group_identifier.isdigit() or group_identifier.startswith('-'):
                # 通过ID获取
                self.target_group = await self.auth.client.get_entity(int(group_identifier))
            else:
                # 通过名称搜索
                async for dialog in self.auth.client.iter_dialogs():
                    if (hasattr(dialog.entity, 'title') and 
                        group_identifier.lower() in dialog.entity.title.lower()):
                        self.target_group = dialog.entity
                        break
            
            if self.target_group:
                group_name = getattr(self.target_group, 'title', str(self.target_group.id))
                telegram_logger.info(f"找到目标群组: {group_name}")
            else:
                telegram_logger.error(f"未找到群组: {group_identifier}")
                
        except Exception as e:
            telegram_logger.error(f"获取目标群组失败: {e}")
            self.target_group = None
    
    def add_signal_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """
        添加交易信号回调函数
        
        Args:
            callback: 回调函数，接收信号字典作为参数
        """
        self.signal_callbacks.append(callback)
    
    def add_message_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """
        添加消息回调函数
        
        Args:
            callback: 回调函数，接收消息字典作为参数
        """
        self.message_callbacks.append(callback)
    
    def add_error_callback(self, callback: Callable[[Exception], None]):
        """
        添加错误回调函数
        
        Args:
            callback: 回调函数，接收异常作为参数
        """
        self.error_callbacks.append(callback)
    
    async def start_monitoring(self) -> bool:
        """
        开始监控
        
        Returns:
            是否成功开始监控
        """
        if self.is_monitoring:
            telegram_logger.warning("监控已在运行中")
            return True
        
        if not self.target_group:
            telegram_logger.error("未设置目标群组，无法开始监控")
            return False
        
        try:
            # 注册事件处理器
            self.auth.client.add_event_handler(
                self._handle_new_message,
                events.NewMessage(chats=self.target_group)
            )
            
            self.is_monitoring = True
            telegram_logger.info(f"开始监控群组: {getattr(self.target_group, 'title', self.target_group.id)}")
            
            # 启动监控任务
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
            
            return True
            
        except Exception as e:
            telegram_logger.error(f"启动监控失败: {e}")
            await self._notify_error_callbacks(e)
            return False
    
    async def stop_monitoring(self):
        """停止监控"""
        if not self.is_monitoring:
            return
        
        try:
            self.is_monitoring = False
            
            # 移除事件处理器
            if self.auth.client:
                self.auth.client.remove_event_handler(self._handle_new_message)
            
            # 取消监控任务
            if self._monitoring_task and not self._monitoring_task.done():
                self._monitoring_task.cancel()
                try:
                    await self._monitoring_task
                except asyncio.CancelledError:
                    pass
            
            telegram_logger.info("监控已停止")
            
        except Exception as e:
            telegram_logger.error(f"停止监控失败: {e}")
    
    async def _monitoring_loop(self):
        """监控主循环"""
        try:
            while self.is_monitoring:
                # 检查连接状态
                if not self.auth.client.is_connected():
                    telegram_logger.warning("连接断开，尝试重连...")
                    try:
                        await self.auth.client.connect()
                        telegram_logger.info("重连成功")
                    except Exception as e:
                        telegram_logger.error(f"重连失败: {e}")
                        await asyncio.sleep(10)  # 等待10秒后重试
                        continue
                
                # 保持连接活跃
                await asyncio.sleep(30)  # 每30秒检查一次
                
        except asyncio.CancelledError:
            telegram_logger.info("监控循环已取消")
        except Exception as e:
            telegram_logger.error(f"监控循环异常: {e}")
            await self._notify_error_callbacks(e)
    
    async def _handle_new_message(self, event):
        """
        处理新消息事件
        
        Args:
            event: Telegram消息事件
        """
        try:
            message = event.message
            sender = await message.get_sender()
            
            # 构建消息数据
            message_data = {
                'id': message.id,
                'text': message.text or '',
                'date': message.date,
                'sender_id': sender.id if sender else None,
                'sender_name': self._get_sender_name(sender),
                'chat_id': message.chat_id,
                'raw_message': message
            }
            
            telegram_logger.log_message_received(
                message_data['text'], 
                message_data['sender_name']
            )
            
            # 通知消息回调
            await self._notify_message_callbacks(message_data)
            
            # 检查是否为交易信号
            if message_data['text']:
                signal = parse_trading_signal(message_data['text'])
                if signal:
                    # 添加消息元数据到信号
                    signal.update({
                        'message_id': message_data['id'],
                        'sender_id': message_data['sender_id'],
                        'sender_name': message_data['sender_name'],
                        'chat_id': message_data['chat_id'],
                        'received_at': datetime.now(timezone.utc).isoformat()
                    })
                    
                    telegram_logger.log_signal_detected(str(signal))
                    
                    # 通知信号回调
                    await self._notify_signal_callbacks(signal)
            
        except Exception as e:
            telegram_logger.error(f"处理消息失败: {e}")
            await self._notify_error_callbacks(e)
    
    def _get_sender_name(self, sender) -> str:
        """获取发送者名称"""
        if not sender:
            return "Unknown"
        
        if isinstance(sender, User):
            if sender.username:
                return f"@{sender.username}"
            elif sender.first_name:
                name = sender.first_name
                if sender.last_name:
                    name += f" {sender.last_name}"
                return name
            else:
                return f"User_{sender.id}"
        elif isinstance(sender, (Channel, Chat)):
            return getattr(sender, 'title', f"Chat_{sender.id}")
        else:
            return str(sender.id)
    
    async def _notify_signal_callbacks(self, signal: Dict[str, Any]):
        """通知所有信号回调函数"""
        for callback in self.signal_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(signal)
                else:
                    callback(signal)
            except Exception as e:
                telegram_logger.error(f"信号回调执行失败: {e}")
    
    async def _notify_message_callbacks(self, message_data: Dict[str, Any]):
        """通知所有消息回调函数"""
        for callback in self.message_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(message_data)
                else:
                    callback(message_data)
            except Exception as e:
                telegram_logger.error(f"消息回调执行失败: {e}")
    
    async def _notify_error_callbacks(self, error: Exception):
        """通知所有错误回调函数"""
        for callback in self.error_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(error)
                else:
                    callback(error)
            except Exception as e:
                telegram_logger.error(f"错误回调执行失败: {e}")
    
    async def get_group_info(self) -> Optional[Dict[str, Any]]:
        """
        获取群组信息
        
        Returns:
            群组信息字典
        """
        if not self.target_group:
            return None
        
        try:
            group_info = {
                'id': self.target_group.id,
                'title': getattr(self.target_group, 'title', 'Unknown'),
                'type': type(self.target_group).__name__,
                'member_count': getattr(self.target_group, 'participants_count', 0),
                'username': getattr(self.target_group, 'username', None)
            }
            
            return group_info
            
        except Exception as e:
            telegram_logger.error(f"获取群组信息失败: {e}")
            return None
    
    async def get_recent_messages(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取最近的消息
        
        Args:
            limit: 消息数量限制
            
        Returns:
            消息列表
        """
        if not self.target_group or not self.auth.client:
            return []
        
        try:
            messages = []
            async for message in self.auth.client.iter_messages(self.target_group, limit=limit):
                sender = await message.get_sender()
                
                message_data = {
                    'id': message.id,
                    'text': message.text or '',
                    'date': message.date.isoformat() if message.date else None,
                    'sender_name': self._get_sender_name(sender)
                }
                
                messages.append(message_data)
            
            return messages
            
        except Exception as e:
            telegram_logger.error(f"获取历史消息失败: {e}")
            return []
    
    async def send_test_message(self, message: str) -> bool:
        """
        发送测试消息（仅用于测试）
        
        Args:
            message: 测试消息内容
            
        Returns:
            是否发送成功
        """
        if not self.target_group or not self.auth.client:
            return False
        
        try:
            await self.auth.client.send_message(self.target_group, message)
            telegram_logger.info(f"测试消息已发送: {message}")
            return True
            
        except Exception as e:
            telegram_logger.error(f"发送测试消息失败: {e}")
            return False
    
    @property
    def status(self) -> Dict[str, Any]:
        """获取监控状态"""
        return {
            'is_monitoring': self.is_monitoring,
            'is_authenticated': self.auth.is_authenticated,
            'target_group': getattr(self.target_group, 'title', None) if self.target_group else None,
            'signal_callbacks_count': len(self.signal_callbacks),
            'message_callbacks_count': len(self.message_callbacks),
            'error_callbacks_count': len(self.error_callbacks)
        }
    
    async def cleanup(self):
        """清理资源"""
        try:
            await self.stop_monitoring()
            await self.auth.disconnect()
            telegram_logger.info("Telegram监控器资源已清理")
        except Exception as e:
            telegram_logger.error(f"清理资源失败: {e}")
