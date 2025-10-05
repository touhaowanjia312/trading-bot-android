"""
配置管理模块
负责加载和管理应用程序的所有配置信息
"""

import os
from pathlib import Path
from typing import Optional, Any
from dotenv import load_dotenv
import json
from dataclasses import dataclass


@dataclass
class TelegramConfig:
    """Telegram API配置"""
    api_id: str
    api_hash: str
    phone_number: str
    session_name: str
    group_id: str


@dataclass
class BitgetConfig:
    """Bitget API配置"""
    api_key: str
    secret_key: str
    passphrase: str
    sandbox: bool = False


@dataclass
class TradingConfig:
    """交易配置"""
    default_trade_amount: float
    default_leverage: int
    max_position_size: float
    risk_percentage: float
    stop_loss_percentage: float
    take_profit_percentage: float
    use_trader_signals_for_tp_sl: bool


@dataclass
class DatabaseConfig:
    """数据库配置"""
    url: str


@dataclass
class LogConfig:
    """日志配置"""
    level: str
    file_path: str


@dataclass
class NotificationConfig:
    """通知配置"""
    enable_desktop: bool
    enable_sound: bool
    sound_path: Optional[str] = None


@dataclass
class GUIConfig:
    """GUI配置"""
    window_title: str
    window_width: int
    window_height: int
    theme: str


class Config:
    """应用程序主配置类"""
    
    def __init__(self, env_file: Optional[str] = None):
        """
        初始化配置
        
        Args:
            env_file: 环境变量文件路径，默认为项目根目录下的.env
        """
        self.project_root = Path(__file__).parent.parent.parent
        
        # 加载环境变量
        if env_file:
            load_dotenv(env_file)
        else:
            # 尝试加载项目根目录下的.env文件
            env_path = self.project_root / ".env"
            if env_path.exists():
                load_dotenv(env_path)
        
        # 初始化各个配置模块
        self._load_configs()
    
    def _load_configs(self):
        """加载所有配置"""
        self.telegram = self._load_telegram_config()
        self.bitget = self._load_bitget_config()
        self.trading = self._load_trading_config()
        self.database = self._load_database_config()
        self.log = self._load_log_config()
        self.notification = self._load_notification_config()
        self.gui = self._load_gui_config()
    
    def _load_telegram_config(self) -> TelegramConfig:
        """加载Telegram配置"""
        return TelegramConfig(
            api_id=self._get_env("TELEGRAM_API_ID", "your_api_id"),
            api_hash=self._get_env("TELEGRAM_API_HASH", "your_api_hash"),
            phone_number=self._get_env("TELEGRAM_PHONE_NUMBER", "+86your_phone_number"),
            session_name=self._get_env("TELEGRAM_SESSION_NAME", "trading_bot"),
            group_id=self._get_env("TELEGRAM_GROUP_ID", "your_group_id")
        )
    
    def _load_bitget_config(self) -> BitgetConfig:
        """加载Bitget配置"""
        return BitgetConfig(
            api_key=self._get_env("BITGET_API_KEY", "your_bitget_api_key"),
            secret_key=self._get_env("BITGET_SECRET_KEY", "your_bitget_secret_key"),
            passphrase=self._get_env("BITGET_PASSPHRASE", "your_bitget_passphrase"),
            sandbox=self._get_env("BITGET_SANDBOX", "false").lower() == "true"
        )
    
    def _load_trading_config(self) -> TradingConfig:
        """加载交易配置"""
        return TradingConfig(
            default_trade_amount=float(self._get_env("DEFAULT_TRADE_AMOUNT", "2.0")),
            default_leverage=int(self._get_env("DEFAULT_LEVERAGE", "20")),
            max_position_size=float(self._get_env("MAX_POSITION_SIZE", "1000.0")),
            risk_percentage=float(self._get_env("RISK_PERCENTAGE", "2.0")),
            stop_loss_percentage=float(self._get_env("STOP_LOSS_PERCENTAGE", "5.0")),
            take_profit_percentage=float(self._get_env("TAKE_PROFIT_PERCENTAGE", "10.0")),
            use_trader_signals_for_tp_sl=self._get_env("USE_TRADER_SIGNALS_FOR_TP_SL", "true").lower() == "true"
        )
    
    def _load_database_config(self) -> DatabaseConfig:
        """加载数据库配置"""
        default_db_url = f"sqlite:///{self.project_root}/data/trading.db"
        return DatabaseConfig(
            url=self._get_env("DATABASE_URL", default_db_url)
        )
    
    def _load_log_config(self) -> LogConfig:
        """加载日志配置"""
        default_log_path = str(self.project_root / "data/logs/trading_bot.log")
        return LogConfig(
            level=self._get_env("LOG_LEVEL", "INFO"),
            file_path=self._get_env("LOG_FILE_PATH", default_log_path)
        )
    
    def _load_notification_config(self) -> NotificationConfig:
        """加载通知配置"""
        return NotificationConfig(
            enable_desktop=self._get_env("ENABLE_DESKTOP_NOTIFICATIONS", "true").lower() == "true",
            enable_sound=self._get_env("ENABLE_SOUND_NOTIFICATIONS", "true").lower() == "true",
            sound_path=self._get_env("NOTIFICATION_SOUND_PATH", None)
        )
    
    def _load_gui_config(self) -> GUIConfig:
        """加载GUI配置"""
        return GUIConfig(
            window_title=self._get_env("WINDOW_TITLE", "Telegram交易信号跟单系统"),
            window_width=int(self._get_env("WINDOW_WIDTH", "1200")),
            window_height=int(self._get_env("WINDOW_HEIGHT", "800")),
            theme=self._get_env("THEME", "light")
        )
    
    def _get_env(self, key: str, default: Optional[str] = None, required: bool = False) -> str:
        """
        获取环境变量
        
        Args:
            key: 环境变量键名
            default: 默认值
            required: 是否为必需项（已废弃，为了兼容性保留）
            
        Returns:
            环境变量值
        """
        value = os.getenv(key, default)
        return value or (default or "")
    
    def save_user_settings(self, settings: dict) -> None:
        """
        保存用户自定义设置到配置文件
        
        Args:
            settings: 设置字典
        """
        settings_file = self.project_root / "config/user_settings.json"
        settings_file.parent.mkdir(exist_ok=True)
        
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
    
    def load_user_settings(self) -> dict:
        """
        加载用户自定义设置
        
        Returns:
            设置字典
        """
        settings_file = self.project_root / "config/user_settings.json"
        
        if not settings_file.exists():
            return {}
        
        try:
            with open(settings_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    
    def validate_config(self, skip_required: bool = False) -> tuple[bool, list[str]]:
        """
        验证配置的有效性
        
        Args:
            skip_required: 是否跳过必需配置项检查（用于测试）
        
        Returns:
            (是否有效, 错误信息列表)
        """
        errors = []
        
        if not skip_required:
            # 验证Telegram配置
            if not self.telegram.api_id:
                errors.append("Telegram API ID未配置")
            if not self.telegram.api_hash:
                errors.append("Telegram API Hash未配置")
            if not self.telegram.phone_number:
                errors.append("Telegram手机号未配置")
            if not self.telegram.group_id:
                errors.append("Telegram群组ID未配置")
            
            # 验证Bitget配置
            if not self.bitget.api_key:
                errors.append("Bitget API Key未配置")
            if not self.bitget.secret_key:
                errors.append("Bitget Secret Key未配置")
            if not self.bitget.passphrase:
                errors.append("Bitget Passphrase未配置")
        
        # 验证交易配置
        if self.trading.default_trade_amount <= 0:
            errors.append("默认交易金额必须大于0")
        if self.trading.default_leverage < 1 or self.trading.default_leverage > 125:
            errors.append("默认杠杆倍数必须在1-125之间")
        if self.trading.max_position_size <= 0:
            errors.append("最大持仓金额必须大于0")
        if not 0 < self.trading.risk_percentage <= 100:
            errors.append("风险百分比必须在0-100之间")
        
        return len(errors) == 0, errors


# 全局配置实例
config = Config()
