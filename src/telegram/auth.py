"""
Telegram认证管理模块
处理Telegram客户端的认证和会话管理
"""

import asyncio
from pathlib import Path
from typing import Optional
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneNumberInvalidError
from telethon.sessions import StringSession

from ..utils.config import config
from ..utils.logger import telegram_logger


class TelegramAuth:
    """Telegram认证管理器"""
    
    def __init__(self):
        self.client: Optional[TelegramClient] = None
        self.session_file = Path(f"data/{config.telegram.session_name}.session")
        self._authenticated = False
    
    async def initialize_client(self) -> bool:
        """
        初始化Telegram客户端
        
        Returns:
            是否成功初始化
        """
        try:
            # 确保会话文件目录存在
            self.session_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 创建客户端
            self.client = TelegramClient(
                str(self.session_file.with_suffix('')),  # 不包含.session后缀
                config.telegram.api_id,
                config.telegram.api_hash
            )
            
            telegram_logger.info("Telegram客户端初始化成功")
            return True
            
        except Exception as e:
            telegram_logger.error(f"Telegram客户端初始化失败: {e}")
            return False
    
    async def authenticate(self, phone_code: Optional[str] = None, password: Optional[str] = None) -> dict:
        """
        认证Telegram账户
        
        Args:
            phone_code: 手机验证码
            password: 两步验证密码
            
        Returns:
            认证结果字典
        """
        if not self.client:
            return {
                'success': False,
                'error': 'Telegram客户端未初始化',
                'need_phone_code': False,
                'need_password': False
            }
        
        try:
            # 连接到Telegram
            await self.client.connect()
            
            # 检查是否已经认证
            if await self.client.is_user_authorized():
                self._authenticated = True
                telegram_logger.info("已存在有效的Telegram会话")
                return {
                    'success': True,
                    'message': '认证成功（使用已存在会话）',
                    'need_phone_code': False,
                    'need_password': False
                }
            
            # 开始认证流程
            if not phone_code:
                # 发送验证码
                try:
                    await self.client.send_code_request(config.telegram.phone_number)
                    telegram_logger.info(f"验证码已发送到 {config.telegram.phone_number}")
                    return {
                        'success': False,
                        'message': '验证码已发送，请输入验证码',
                        'need_phone_code': True,
                        'need_password': False
                    }
                except PhoneNumberInvalidError:
                    return {
                        'success': False,
                        'error': '手机号码无效',
                        'need_phone_code': False,
                        'need_password': False
                    }
            
            # 使用验证码登录
            try:
                await self.client.sign_in(config.telegram.phone_number, phone_code)
                self._authenticated = True
                telegram_logger.info("Telegram认证成功")
                return {
                    'success': True,
                    'message': '认证成功',
                    'need_phone_code': False,
                    'need_password': False
                }
                
            except SessionPasswordNeededError:
                # 需要两步验证密码
                if not password:
                    return {
                        'success': False,
                        'message': '需要两步验证密码',
                        'need_phone_code': False,
                        'need_password': True
                    }
                
                # 使用两步验证密码登录
                await self.client.sign_in(password=password)
                self._authenticated = True
                telegram_logger.info("Telegram两步验证认证成功")
                return {
                    'success': True,
                    'message': '两步验证认证成功',
                    'need_phone_code': False,
                    'need_password': False
                }
                
            except PhoneCodeInvalidError:
                return {
                    'success': False,
                    'error': '验证码无效',
                    'need_phone_code': True,
                    'need_password': False
                }
        
        except Exception as e:
            telegram_logger.error(f"Telegram认证失败: {e}")
            return {
                'success': False,
                'error': f'认证失败: {str(e)}',
                'need_phone_code': False,
                'need_password': False
            }
    
    async def logout(self) -> bool:
        """
        登出并清除会话
        
        Returns:
            是否成功登出
        """
        try:
            if self.client and self.client.is_connected():
                await self.client.log_out()
                telegram_logger.info("已登出Telegram")
            
            # 删除会话文件
            if self.session_file.exists():
                self.session_file.unlink()
                telegram_logger.info("会话文件已删除")
            
            self._authenticated = False
            return True
            
        except Exception as e:
            telegram_logger.error(f"登出失败: {e}")
            return False
    
    async def disconnect(self):
        """断开连接"""
        try:
            if self.client and self.client.is_connected():
                await self.client.disconnect()
                telegram_logger.info("Telegram连接已断开")
        except Exception as e:
            telegram_logger.error(f"断开连接失败: {e}")
    
    @property
    def is_authenticated(self) -> bool:
        """检查是否已认证"""
        return self._authenticated and self.client and self.client.is_connected()
    
    async def get_me(self) -> Optional[dict]:
        """
        获取当前用户信息
        
        Returns:
            用户信息字典
        """
        if not self.is_authenticated:
            return None
        
        try:
            me = await self.client.get_me()
            return {
                'id': me.id,
                'username': me.username,
                'first_name': me.first_name,
                'last_name': me.last_name,
                'phone': me.phone
            }
        except Exception as e:
            telegram_logger.error(f"获取用户信息失败: {e}")
            return None
    
    async def test_connection(self) -> dict:
        """
        测试连接状态
        
        Returns:
            连接测试结果
        """
        try:
            if not self.client:
                return {'success': False, 'error': '客户端未初始化'}
            
            if not self.client.is_connected():
                await self.client.connect()
            
            if not await self.client.is_user_authorized():
                return {'success': False, 'error': '用户未认证'}
            
            # 尝试获取用户信息来测试连接
            me = await self.get_me()
            if me:
                return {
                    'success': True, 
                    'message': '连接正常',
                    'user': me
                }
            else:
                return {'success': False, 'error': '无法获取用户信息'}
                
        except Exception as e:
            telegram_logger.error(f"连接测试失败: {e}")
            return {'success': False, 'error': f'连接测试失败: {str(e)}'}
    
    def export_session(self) -> Optional[str]:
        """
        导出会话字符串（用于备份）
        
        Returns:
            会话字符串
        """
        try:
            if self.client and hasattr(self.client.session, 'save'):
                return self.client.session.save()
            return None
        except Exception as e:
            telegram_logger.error(f"导出会话失败: {e}")
            return None
    
    async def import_session(self, session_string: str) -> bool:
        """
        从会话字符串导入会话
        
        Args:
            session_string: 会话字符串
            
        Returns:
            是否成功导入
        """
        try:
            # 创建新的客户端使用字符串会话
            self.client = TelegramClient(
                StringSession(session_string),
                config.telegram.api_id,
                config.telegram.api_hash
            )
            
            await self.client.connect()
            
            if await self.client.is_user_authorized():
                self._authenticated = True
                telegram_logger.info("会话导入成功")
                return True
            else:
                telegram_logger.warning("导入的会话无效")
                return False
                
        except Exception as e:
            telegram_logger.error(f"导入会话失败: {e}")
            return False
