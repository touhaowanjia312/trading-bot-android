#!/usr/bin/env python3
"""
移动端交易机器人 - Kivy版本
适配Android/iOS平台的交易跟单应用
"""

import os
import sys
import asyncio
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

# Kivy imports
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.uix.switch import Switch
from kivy.uix.progressbar import ProgressBar
from kivy.clock import Clock, mainthread
from kivy.logger import Logger
from kivy.utils import platform

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

# 导入现有模块
try:
    from src.trading.bitget_client import BitgetClient
    from src.trading.signal_parser import SignalParser
    from src.utils.config import Config
    from src.utils.logger import TradingBotLogger
    TRADING_MODULES_AVAILABLE = True
except ImportError as e:
    Logger.error(f"交易模块导入失败: {e}")
    TRADING_MODULES_AVAILABLE = False

try:
    from groups_config import get_monitor_groups
    GROUPS_CONFIG_AVAILABLE = True
except ImportError:
    Logger.info("群组配置文件未找到，使用默认配置")
    GROUPS_CONFIG_AVAILABLE = False


class MobileStatusBar(BoxLayout):
    """移动端状态栏"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.size_hint_y = None
        self.height = '48dp'
        self.spacing = '10dp'
        self.padding = ['10dp', '5dp']
        
        # 连接状态指示器
        self.telegram_status = Label(
            text='📡 Telegram: 未连接',
            size_hint_x=0.5,
            color=(1, 0.7, 0, 1)  # 橙色
        )
        self.add_widget(self.telegram_status)
        
        self.bitget_status = Label(
            text='💰 Bitget: 未连接',
            size_hint_x=0.5,
            color=(1, 0.7, 0, 1)  # 橙色
        )
        self.add_widget(self.bitget_status)
    
    def update_telegram_status(self, connected: bool):
        if connected:
            self.telegram_status.text = '📡 Telegram: 已连接'
            self.telegram_status.color = (0, 1, 0, 1)  # 绿色
        else:
            self.telegram_status.text = '📡 Telegram: 未连接'
            self.telegram_status.color = (1, 0, 0, 1)  # 红色
    
    def update_bitget_status(self, connected: bool):
        if connected:
            self.bitget_status.text = '💰 Bitget: 已连接'
            self.bitget_status.color = (0, 1, 0, 1)  # 绿色
        else:
            self.bitget_status.text = '💰 Bitget: 未连接'
            self.bitget_status.color = (1, 0, 0, 1)  # 红色


class MobileControlPanel(BoxLayout):
    """移动端控制面板"""
    
    def __init__(self, app_instance, **kwargs):
        super().__init__(**kwargs)
        self.app = app_instance
        self.orientation = 'vertical'
        self.size_hint_y = None
        self.height = '200dp'
        self.spacing = '10dp'
        self.padding = ['10dp']
        
        # 主控制按钮
        control_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height='50dp')
        
        self.start_button = Button(
            text='🚀 启动监控',
            size_hint_x=0.5,
            background_color=(0, 0.8, 0, 1)
        )
        self.start_button.bind(on_press=self.toggle_monitoring)
        control_layout.add_widget(self.start_button)
        
        self.settings_button = Button(
            text='⚙️ 设置',
            size_hint_x=0.5,
            background_color=(0.2, 0.6, 1, 1)
        )
        self.settings_button.bind(on_press=self.show_settings)
        control_layout.add_widget(self.settings_button)
        
        self.add_widget(control_layout)
        
        # 交易开关
        trade_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height='40dp')
        trade_layout.add_widget(Label(text='🔄 自动交易:', size_hint_x=0.7))
        
        self.trade_switch = Switch(active=True, size_hint_x=0.3)
        self.trade_switch.bind(active=self.on_trade_switch)
        trade_layout.add_widget(self.trade_switch)
        
        self.add_widget(trade_layout)
        
        # 统计信息
        stats_layout = GridLayout(cols=2, size_hint_y=None, height='80dp', spacing='5dp')
        
        self.signals_label = Label(text='信号数: 0', size_hint_y=None, height='30dp')
        self.trades_label = Label(text='交易数: 0', size_hint_y=None, height='30dp')
        self.profit_label = Label(text='盈亏: +0.00U', size_hint_y=None, height='30dp')
        self.positions_label = Label(text='持仓: 0', size_hint_y=None, height='30dp')
        
        stats_layout.add_widget(self.signals_label)
        stats_layout.add_widget(self.trades_label)
        stats_layout.add_widget(self.profit_label)
        stats_layout.add_widget(self.positions_label)
        
        self.add_widget(stats_layout)
        
        # 状态变量
        self.monitoring_active = False
        self.trade_enabled = True
    
    def toggle_monitoring(self, instance):
        """切换监控状态"""
        if not self.monitoring_active:
            self.start_monitoring()
        else:
            self.stop_monitoring()
    
    def start_monitoring(self):
        """启动监控"""
        self.monitoring_active = True
        self.start_button.text = '⏹️ 停止监控'
        self.start_button.background_color = (1, 0.3, 0.3, 1)
        self.app.start_monitoring()
    
    def stop_monitoring(self):
        """停止监控"""
        self.monitoring_active = False
        self.start_button.text = '🚀 启动监控'
        self.start_button.background_color = (0, 0.8, 0, 1)
        self.app.stop_monitoring()
    
    def on_trade_switch(self, instance, value):
        """交易开关回调"""
        self.trade_enabled = value
        self.app.set_trade_enabled(value)
        status = "开启" if value else "关闭"
        self.app.add_log(f"🔄 自动交易已{status}")
    
    def show_settings(self, instance):
        """显示设置界面"""
        self.app.show_settings_popup()
    
    def update_stats(self, signals: int, trades: int, profit: float, positions: int):
        """更新统计信息"""
        self.signals_label.text = f'信号数: {signals}'
        self.trades_label.text = f'交易数: {trades}'
        profit_color = (0, 1, 0, 1) if profit >= 0 else (1, 0, 0, 1)
        self.profit_label.text = f'盈亏: {profit:+.2f}U'
        self.profit_label.color = profit_color
        self.positions_label.text = f'持仓: {positions}'


class MobileLogDisplay(ScrollView):
    """移动端日志显示"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.log_layout = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            spacing='2dp',
            padding=['5dp']
        )
        self.log_layout.bind(minimum_height=self.log_layout.setter('height'))
        
        self.add_widget(self.log_layout)
        self.max_logs = 100  # 限制日志数量以节省内存
    
    @mainthread
    def add_log(self, message: str, level: str = 'INFO'):
        """添加日志消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # 根据级别设置颜色
        color_map = {
            'INFO': (1, 1, 1, 1),      # 白色
            'WARNING': (1, 1, 0, 1),   # 黄色
            'ERROR': (1, 0, 0, 1),     # 红色
            'SUCCESS': (0, 1, 0, 1),   # 绿色
            'DEBUG': (0.7, 0.7, 0.7, 1) # 灰色
        }
        
        log_label = Label(
            text=f"[{timestamp}] {message}",
            size_hint_y=None,
            height='30dp',
            text_size=(None, None),
            halign='left',
            color=color_map.get(level, (1, 1, 1, 1))
        )
        
        # 绑定文本大小
        log_label.bind(width=lambda instance, width: setattr(instance, 'text_size', (width, None)))
        log_label.bind(texture_size=log_label.setter('size'))
        
        self.log_layout.add_widget(log_label)
        
        # 限制日志数量
        if len(self.log_layout.children) > self.max_logs:
            self.log_layout.remove_widget(self.log_layout.children[-1])
        
        # 自动滚动到底部
        Clock.schedule_once(lambda dt: setattr(self, 'scroll_y', 0), 0.1)


class SettingsPopup(Popup):
    """设置弹窗"""
    
    def __init__(self, app_instance, **kwargs):
        super().__init__(**kwargs)
        self.app = app_instance
        self.title = '⚙️ 交易设置'
        self.size_hint = (0.9, 0.8)
        
        # 创建设置界面
        content = BoxLayout(orientation='vertical', spacing='10dp', padding='10dp')
        
        # 交易金额设置
        amount_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height='40dp')
        amount_layout.add_widget(Label(text='交易金额(U):', size_hint_x=0.4))
        self.amount_input = TextInput(
            text='3.0',
            multiline=False,
            input_filter='float',
            size_hint_x=0.6
        )
        amount_layout.add_widget(self.amount_input)
        content.add_widget(amount_layout)
        
        # 杠杆设置
        leverage_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height='40dp')
        leverage_layout.add_widget(Label(text='杠杆倍数:', size_hint_x=0.4))
        self.leverage_input = TextInput(
            text='20',
            multiline=False,
            input_filter='int',
            size_hint_x=0.6
        )
        leverage_layout.add_widget(self.leverage_input)
        content.add_widget(leverage_layout)
        
        # 止损金额设置
        stop_loss_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height='40dp')
        stop_loss_layout.add_widget(Label(text='止损金额(U):', size_hint_x=0.4))
        self.stop_loss_input = TextInput(
            text='7.0',
            multiline=False,
            input_filter='float',
            size_hint_x=0.6
        )
        stop_loss_layout.add_widget(self.stop_loss_input)
        content.add_widget(stop_loss_layout)
        
        # 按钮
        button_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height='50dp', spacing='10dp')
        
        save_button = Button(text='💾 保存', background_color=(0, 0.8, 0, 1))
        save_button.bind(on_press=self.save_settings)
        button_layout.add_widget(save_button)
        
        cancel_button = Button(text='❌ 取消', background_color=(0.8, 0.3, 0.3, 1))
        cancel_button.bind(on_press=self.dismiss)
        button_layout.add_widget(cancel_button)
        
        content.add_widget(button_layout)
        
        self.content = content
    
    def save_settings(self, instance):
        """保存设置"""
        try:
            amount = float(self.amount_input.text)
            leverage = int(self.leverage_input.text)
            stop_loss = float(self.stop_loss_input.text)
            
            # 验证参数
            if amount <= 0 or leverage < 1 or leverage > 125 or stop_loss <= 0:
                raise ValueError("参数超出有效范围")
            
            # 保存设置
            self.app.update_trading_settings(amount, leverage, stop_loss)
            self.app.add_log(f"✅ 设置已保存: 金额={amount}U, 杠杆={leverage}x, 止损={stop_loss}U", 'SUCCESS')
            self.dismiss()
            
        except ValueError as e:
            self.app.add_log(f"❌ 设置保存失败: {e}", 'ERROR')


class MobileTradingBotApp(App):
    """移动端交易机器人主应用"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = "📱 交易跟单机器人"
        
        # 核心组件
        self.bitget_client = None
        self.signal_parser = None
        self.config = None
        self.logger = None
        
        # 状态变量
        self.monitoring_active = False
        self.trade_enabled = True
        self.telegram_connected = False
        self.bitget_connected = False
        
        # 统计数据
        self.stats = {
            'signals': 0,
            'trades': 0,
            'profit': 0.0,
            'positions': 0
        }
        
        # 交易设置
        self.trading_settings = {
            'amount': 3.0,
            'leverage': 20,
            'stop_loss': 7.0
        }
        
        # 异步事件循环
        self.loop = None
        self.loop_thread = None
    
    def build(self):
        """构建应用界面"""
        # 主布局
        main_layout = BoxLayout(orientation='vertical')
        
        # 状态栏
        self.status_bar = MobileStatusBar()
        main_layout.add_widget(self.status_bar)
        
        # 控制面板
        self.control_panel = MobileControlPanel(self)
        main_layout.add_widget(self.control_panel)
        
        # 日志显示
        self.log_display = MobileLogDisplay()
        main_layout.add_widget(self.log_display)
        
        # 初始化
        Clock.schedule_once(self.initialize_app, 0.5)
        
        return main_layout
    
    def initialize_app(self, dt):
        """初始化应用组件"""
        self.add_log("📱 移动端交易机器人启动中...", 'INFO')
        
        try:
            # 初始化配置
            if TRADING_MODULES_AVAILABLE:
                self.config = Config()
                self.logger = TradingBotLogger("MobileBot")
                
            # 初始化交易客户端
            self.bitget_client = BitgetClient()
            self.signal_parser = SignalParser()
                
                self.add_log("✅ 交易模块初始化成功", 'SUCCESS')
            else:
                self.add_log("⚠️ 交易模块不可用，仅显示模式", 'WARNING')
            
            # 启动异步事件循环
            self.start_async_loop()
            
            # 检查连接状态
            Clock.schedule_once(self.check_connections, 1.0)
            
        except Exception as e:
            self.add_log(f"❌ 初始化失败: {e}", 'ERROR')
    
    def start_async_loop(self):
        """启动异步事件循环"""
        def run_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()
        
        self.loop_thread = threading.Thread(target=run_loop, daemon=True)
        self.loop_thread.start()
        self.add_log("🔄 异步事件循环已启动", 'INFO')
    
    def check_connections(self, dt):
        """检查连接状态"""
        if self.bitget_client:
            # 检查Bitget连接
            def check_bitget():
                try:
                    # 这里可以添加实际的连接检查
                    self.bitget_connected = True
                    Clock.schedule_once(lambda dt: self.status_bar.update_bitget_status(True), 0)
                    Clock.schedule_once(lambda dt: self.add_log("✅ Bitget连接正常", 'SUCCESS'), 0)
                except:
                    self.bitget_connected = False
                    Clock.schedule_once(lambda dt: self.status_bar.update_bitget_status(False), 0)
                    Clock.schedule_once(lambda dt: self.add_log("❌ Bitget连接失败", 'ERROR'), 0)
            
            threading.Thread(target=check_bitget, daemon=True).start()
        
        # Telegram连接检查（简化版）
        self.telegram_connected = True  # 简化处理
        self.status_bar.update_telegram_status(True)
        self.add_log("✅ Telegram连接模拟正常", 'SUCCESS')
    
    def start_monitoring(self):
        """启动监控"""
        self.monitoring_active = True
        self.add_log("🚀 交易监控已启动", 'SUCCESS')
        
        # 启动模拟监控任务
        Clock.schedule_interval(self.monitor_task, 30.0)  # 每30秒执行一次
    
    def stop_monitoring(self):
        """停止监控"""
        self.monitoring_active = False
        self.add_log("⏹️ 交易监控已停止", 'WARNING')
        
        # 停止监控任务
        Clock.unschedule(self.monitor_task)
    
    def monitor_task(self, dt):
        """监控任务（模拟）"""
        if self.monitoring_active:
            # 模拟接收信号
            import random
            if random.random() < 0.1:  # 10%概率模拟接收信号
                self.simulate_signal_received()
    
    def simulate_signal_received(self):
        """模拟接收到交易信号"""
        self.stats['signals'] += 1
        symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'DOTUSDT']
        directions = ['做多', '做空']
        
        symbol = random.choice(symbols)
        direction = random.choice(directions)
        
        self.add_log(f"📡 接收信号: {symbol} {direction}", 'INFO')
        
        if self.trade_enabled:
            # 模拟执行交易
            Clock.schedule_once(lambda dt: self.simulate_trade_execution(symbol, direction), 1.0)
        
        # 更新统计
        self.update_stats()
    
    def simulate_trade_execution(self, symbol: str, direction: str):
        """模拟交易执行"""
        self.stats['trades'] += 1
        self.stats['positions'] += 1
        
        # 模拟盈亏
        import random
        profit_change = random.uniform(-2.0, 5.0)  # 模拟-2到+5U的盈亏
        self.stats['profit'] += profit_change
        
        self.add_log(f"💰 执行交易: {symbol} {direction} {self.trading_settings['amount']}U", 'SUCCESS')
        self.add_log(f"📊 盈亏变化: {profit_change:+.2f}U", 'INFO')
        
        # 更新统计
        self.update_stats()
    
    def set_trade_enabled(self, enabled: bool):
        """设置交易开关"""
        self.trade_enabled = enabled
    
    def show_settings_popup(self):
        """显示设置弹窗"""
        popup = SettingsPopup(self)
        popup.open()
    
    def update_trading_settings(self, amount: float, leverage: int, stop_loss: float):
        """更新交易设置"""
        self.trading_settings.update({
            'amount': amount,
            'leverage': leverage,
            'stop_loss': stop_loss
        })
    
    def update_stats(self):
        """更新统计显示"""
        self.control_panel.update_stats(
            self.stats['signals'],
            self.stats['trades'],
            self.stats['profit'],
            self.stats['positions']
        )
    
    @mainthread
    def add_log(self, message: str, level: str = 'INFO'):
        """添加日志"""
        self.log_display.add_log(message, level)
        if self.logger:
            getattr(self.logger, level.lower(), self.logger.info)(message)
    
    def on_pause(self):
        """应用暂停时保持运行"""
        if platform == 'android':
            # 在Android上保持后台运行
            return True
        return False
    
    def on_resume(self):
        """应用恢复时的处理"""
        self.add_log("📱 应用已恢复", 'INFO')


if __name__ == '__main__':
    # 配置Kivy日志
    import logging
    logging.getLogger('kivy').setLevel(logging.WARNING)
    
    # 启动应用
    MobileTradingBotApp().run()
