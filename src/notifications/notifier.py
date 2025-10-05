"""
实时通知系统模块
提供多种通知方式：桌面通知、声音提醒、邮件通知等
"""

import asyncio
import smtplib
import winsound
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Callable
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from enum import Enum

try:
    from plyer import notification as desktop_notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False
    desktop_notification = None

from ..utils.config import config
from ..utils.logger import get_logger
from ..trading.signal_parser import TradingSignal

logger = get_logger("Notifier")


class NotificationType(Enum):
    """通知类型"""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    TRADE_SIGNAL = "trade_signal"
    TRADE_EXECUTION = "trade_execution"
    RISK_ALERT = "risk_alert"


class NotificationChannel(Enum):
    """通知渠道"""
    DESKTOP = "desktop"
    SOUND = "sound"
    EMAIL = "email"
    WEBHOOK = "webhook"
    LOG = "log"


class NotificationManager:
    """通知管理器"""
    
    def __init__(self):
        self.enabled_channels = set()
        self.notification_history: List[Dict[str, Any]] = []
        self.custom_handlers: Dict[NotificationType, List[Callable]] = {}
        
        # 配置各种通知渠道
        self._setup_channels()
        
        # 声音文件路径
        self.sound_files = {
            NotificationType.INFO: "sounds/info.wav",
            NotificationType.SUCCESS: "sounds/success.wav",
            NotificationType.WARNING: "sounds/warning.wav",
            NotificationType.ERROR: "sounds/error.wav",
            NotificationType.TRADE_SIGNAL: "sounds/signal.wav",
            NotificationType.TRADE_EXECUTION: "sounds/execution.wav",
            NotificationType.RISK_ALERT: "sounds/alert.wav"
        }
        
        # 邮件配置
        self.email_config = {
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'email': '',
            'password': '',
            'to_emails': []
        }
    
    def _setup_channels(self):
        """设置通知渠道"""
        # 桌面通知
        if config.notification.enable_desktop and PLYER_AVAILABLE:
            self.enabled_channels.add(NotificationChannel.DESKTOP)
            logger.info("桌面通知已启用")
        
        # 声音通知
        if config.notification.enable_sound:
            self.enabled_channels.add(NotificationChannel.SOUND)
            logger.info("声音通知已启用")
        
        # 日志通知（始终启用）
        self.enabled_channels.add(NotificationChannel.LOG)
    
    async def notify(
        self, 
        message: str, 
        notification_type: NotificationType = NotificationType.INFO,
        title: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        channels: Optional[List[NotificationChannel]] = None
    ):
        """
        发送通知
        
        Args:
            message: 通知消息
            notification_type: 通知类型
            title: 通知标题
            data: 额外数据
            channels: 指定通知渠道
        """
        try:
            # 使用指定渠道或默认启用的渠道
            target_channels = channels or list(self.enabled_channels)
            
            # 记录通知历史
            notification_record = {
                'timestamp': datetime.now(timezone.utc),
                'type': notification_type.value,
                'title': title,
                'message': message,
                'data': data,
                'channels': [ch.value for ch in target_channels]
            }
            self.notification_history.append(notification_record)
            
            # 限制历史记录数量
            if len(self.notification_history) > 1000:
                self.notification_history = self.notification_history[-500:]
            
            # 发送到各个渠道
            tasks = []
            for channel in target_channels:
                if channel == NotificationChannel.DESKTOP:
                    tasks.append(self._send_desktop_notification(message, title, notification_type))
                elif channel == NotificationChannel.SOUND:
                    tasks.append(self._play_sound(notification_type))
                elif channel == NotificationChannel.EMAIL:
                    tasks.append(self._send_email_notification(message, title, notification_type))
                elif channel == NotificationChannel.LOG:
                    tasks.append(self._log_notification(message, notification_type))
            
            # 并发执行所有通知
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            
            # 执行自定义处理器
            await self._execute_custom_handlers(notification_type, notification_record)
            
        except Exception as e:
            logger.error(f"发送通知失败: {e}")
    
    async def _send_desktop_notification(
        self, 
        message: str, 
        title: Optional[str], 
        notification_type: NotificationType
    ):
        """发送桌面通知"""
        if not PLYER_AVAILABLE or NotificationChannel.DESKTOP not in self.enabled_channels:
            return
        
        try:
            # 设置默认标题
            if not title:
                title = self._get_default_title(notification_type)
            
            # 设置图标
            icon_path = self._get_notification_icon(notification_type)
            
            # 发送桌面通知
            desktop_notification.notify(
                title=title,
                message=message[:200],  # 限制消息长度
                app_name="Telegram Trading Bot",
                timeout=10,
                app_icon=icon_path
            )
            
            logger.debug(f"桌面通知已发送: {title}")
            
        except Exception as e:
            logger.error(f"发送桌面通知失败: {e}")
    
    async def _play_sound(self, notification_type: NotificationType):
        """播放通知声音"""
        if NotificationChannel.SOUND not in self.enabled_channels:
            return
        
        try:
            # 获取声音文件路径
            sound_file = self.sound_files.get(notification_type)
            
            if sound_file and Path(sound_file).exists():
                # 使用指定的声音文件
                winsound.PlaySound(str(Path(sound_file).absolute()), winsound.SND_FILENAME | winsound.SND_ASYNC)
            else:
                # 使用系统默认声音
                if notification_type == NotificationType.ERROR:
                    winsound.PlaySound("SystemHand", winsound.SND_ALIAS | winsound.SND_ASYNC)
                elif notification_type == NotificationType.WARNING:
                    winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS | winsound.SND_ASYNC)
                elif notification_type == NotificationType.SUCCESS:
                    winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
                else:
                    winsound.PlaySound("SystemDefault", winsound.SND_ALIAS | winsound.SND_ASYNC)
            
            logger.debug(f"声音通知已播放: {notification_type.value}")
            
        except Exception as e:
            logger.error(f"播放声音通知失败: {e}")
    
    async def _send_email_notification(
        self, 
        message: str, 
        title: Optional[str], 
        notification_type: NotificationType
    ):
        """发送邮件通知"""
        if NotificationChannel.EMAIL not in self.enabled_channels or not self.email_config['email']:
            return
        
        try:
            # 创建邮件内容
            msg = MIMEMultipart()
            msg['From'] = self.email_config['email']
            msg['To'] = ', '.join(self.email_config['to_emails'])
            msg['Subject'] = title or self._get_default_title(notification_type)
            
            # 邮件正文
            body = f"""
            {message}
            
            ---
            发送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            通知类型: {notification_type.value}
            来源: Telegram Trading Bot
            """
            
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # 发送邮件
            server = smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port'])
            server.starttls()
            server.login(self.email_config['email'], self.email_config['password'])
            
            text = msg.as_string()
            server.sendmail(self.email_config['email'], self.email_config['to_emails'], text)
            server.quit()
            
            logger.debug(f"邮件通知已发送: {title}")
            
        except Exception as e:
            logger.error(f"发送邮件通知失败: {e}")
    
    async def _log_notification(self, message: str, notification_type: NotificationType):
        """记录日志通知"""
        try:
            if notification_type == NotificationType.ERROR:
                logger.error(f"[通知] {message}")
            elif notification_type == NotificationType.WARNING:
                logger.warning(f"[通知] {message}")
            elif notification_type == NotificationType.SUCCESS:
                logger.info(f"[通知] {message}")
            else:
                logger.info(f"[通知] {message}")
                
        except Exception as e:
            logger.error(f"记录日志通知失败: {e}")
    
    def _get_default_title(self, notification_type: NotificationType) -> str:
        """获取默认标题"""
        titles = {
            NotificationType.INFO: "信息",
            NotificationType.SUCCESS: "成功",
            NotificationType.WARNING: "警告",
            NotificationType.ERROR: "错误",
            NotificationType.TRADE_SIGNAL: "交易信号",
            NotificationType.TRADE_EXECUTION: "交易执行",
            NotificationType.RISK_ALERT: "风险警报"
        }
        return titles.get(notification_type, "通知")
    
    def _get_notification_icon(self, notification_type: NotificationType) -> Optional[str]:
        """获取通知图标路径"""
        # 可以根据通知类型返回不同的图标路径
        icon_files = {
            NotificationType.SUCCESS: "icons/success.ico",
            NotificationType.ERROR: "icons/error.ico",
            NotificationType.WARNING: "icons/warning.ico",
            NotificationType.TRADE_SIGNAL: "icons/signal.ico"
        }
        
        icon_path = icon_files.get(notification_type)
        if icon_path and Path(icon_path).exists():
            return str(Path(icon_path).absolute())
        
        return None
    
    async def _execute_custom_handlers(self, notification_type: NotificationType, notification_data: Dict[str, Any]):
        """执行自定义通知处理器"""
        handlers = self.custom_handlers.get(notification_type, [])
        
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(notification_data)
                else:
                    handler(notification_data)
            except Exception as e:
                logger.error(f"自定义通知处理器执行失败: {e}")
    
    # ========== 便捷通知方法 ==========
    
    async def notify_trade_signal(self, signal: TradingSignal):
        """交易信号通知"""
        message = f"检测到交易信号: {signal.symbol} {signal.side.value} {signal.amount or '默认金额'}"
        await self.notify(
            message=message,
            notification_type=NotificationType.TRADE_SIGNAL,
            title="新交易信号",
            data=signal.to_dict()
        )
    
    async def notify_trade_execution(self, execution_result: Dict[str, Any]):
        """交易执行通知"""
        success = execution_result.get('success', False)
        symbol = execution_result.get('signal', {}).get('symbol', 'Unknown')
        
        if success:
            message = f"交易执行成功: {symbol}"
            notification_type = NotificationType.SUCCESS
        else:
            error = execution_result.get('error', '未知错误')
            message = f"交易执行失败: {symbol} - {error}"
            notification_type = NotificationType.ERROR
        
        await self.notify(
            message=message,
            notification_type=notification_type,
            title="交易执行结果",
            data=execution_result
        )
    
    async def notify_risk_alert(self, risk_message: str, risk_level: str = "medium"):
        """风险警报通知"""
        await self.notify(
            message=risk_message,
            notification_type=NotificationType.RISK_ALERT,
            title=f"风险警报 ({risk_level.upper()})",
            data={'risk_level': risk_level}
        )
    
    async def notify_system_status(self, status_message: str, is_error: bool = False):
        """系统状态通知"""
        notification_type = NotificationType.ERROR if is_error else NotificationType.INFO
        await self.notify(
            message=status_message,
            notification_type=notification_type,
            title="系统状态"
        )
    
    async def notify_connection_status(self, service: str, connected: bool):
        """连接状态通知"""
        status = "已连接" if connected else "连接断开"
        message = f"{service} {status}"
        notification_type = NotificationType.SUCCESS if connected else NotificationType.WARNING
        
        await self.notify(
            message=message,
            notification_type=notification_type,
            title="连接状态",
            data={'service': service, 'connected': connected}
        )
    
    # ========== 配置和管理方法 ==========
    
    def add_custom_handler(self, notification_type: NotificationType, handler: Callable):
        """添加自定义通知处理器"""
        if notification_type not in self.custom_handlers:
            self.custom_handlers[notification_type] = []
        
        self.custom_handlers[notification_type].append(handler)
        logger.info(f"已添加自定义处理器: {notification_type.value}")
    
    def remove_custom_handler(self, notification_type: NotificationType, handler: Callable):
        """移除自定义通知处理器"""
        if notification_type in self.custom_handlers:
            try:
                self.custom_handlers[notification_type].remove(handler)
                logger.info(f"已移除自定义处理器: {notification_type.value}")
            except ValueError:
                pass
    
    def enable_channel(self, channel: NotificationChannel):
        """启用通知渠道"""
        self.enabled_channels.add(channel)
        logger.info(f"已启用通知渠道: {channel.value}")
    
    def disable_channel(self, channel: NotificationChannel):
        """禁用通知渠道"""
        self.enabled_channels.discard(channel)
        logger.info(f"已禁用通知渠道: {channel.value}")
    
    def configure_email(self, smtp_server: str, smtp_port: int, email: str, password: str, to_emails: List[str]):
        """配置邮件通知"""
        self.email_config.update({
            'smtp_server': smtp_server,
            'smtp_port': smtp_port,
            'email': email,
            'password': password,
            'to_emails': to_emails
        })
        
        self.enabled_channels.add(NotificationChannel.EMAIL)
        logger.info("邮件通知配置已更新")
    
    def get_notification_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取通知历史"""
        return self.notification_history[-limit:]
    
    def clear_notification_history(self):
        """清空通知历史"""
        self.notification_history.clear()
        logger.info("通知历史已清空")
    
    def get_status(self) -> Dict[str, Any]:
        """获取通知系统状态"""
        return {
            'enabled_channels': [ch.value for ch in self.enabled_channels],
            'plyer_available': PLYER_AVAILABLE,
            'email_configured': bool(self.email_config['email']),
            'notification_count': len(self.notification_history),
            'custom_handlers': {
                nt.value: len(handlers) 
                for nt, handlers in self.custom_handlers.items()
            }
        }
    
    async def test_notifications(self):
        """测试所有通知渠道"""
        test_message = "这是一条测试通知"
        
        for notification_type in NotificationType:
            await self.notify(
                message=f"{test_message} - {notification_type.value}",
                notification_type=notification_type,
                title=f"测试 - {notification_type.value}"
            )
            
            # 间隔一秒避免通知过于频繁
            await asyncio.sleep(1)
        
        logger.info("通知系统测试完成")


# 全局通知管理器实例
notifier = NotificationManager()
