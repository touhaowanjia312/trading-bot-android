#!/usr/bin/env python3
"""
图形界面交易机器人
使用tkinter创建简单的GUI界面
"""

import os
import sys
import signal
import asyncio
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from pathlib import Path
from datetime import datetime
import re

sys.path.insert(0, str(Path(__file__).parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from src.trading.bitget_client import BitgetClient
    from src.trading.signal_parser import SignalParser
    from src.utils.config import Config
    TRADING_MODULES_AVAILABLE = True
except ImportError as e:
    print(f"交易模块导入失败: {e}")
    TRADING_MODULES_AVAILABLE = False

try:
    from groups_config import get_monitor_groups
    GROUPS_CONFIG_AVAILABLE = True
except ImportError:
    print("群组配置文件未找到，使用默认配置")
    GROUPS_CONFIG_AVAILABLE = False


class TradingBotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Telegram交易跟单机器人 v1.0")
        self.root.geometry("800x600")
        # 移除背景色设置，使用系统默认
        
        # 状态变量
        self.running = False
        self.telegram_client = None
        self.target_channels = []  # 改为列表支持多个群组
        self.trade_count = 0
        self.shutdown_requested = False
        
        # 配置
        self.api_id = os.getenv('TELEGRAM_API_ID')
        self.api_hash = os.getenv('TELEGRAM_API_HASH')
        self.trade_amount = float(os.getenv('DEFAULT_TRADE_AMOUNT', '2.0'))
        self.leverage = int(os.getenv('DEFAULT_LEVERAGE', '20'))
        
        # 加载用户自定义配置
        self.load_trading_config()
        
        # Bitget配置
        self.bitget_api_key = os.getenv('BITGET_API_KEY')
        self.bitget_secret_key = os.getenv('BITGET_SECRET_KEY')
        self.bitget_passphrase = os.getenv('BITGET_PASSPHRASE')
        
        # Weex配置
        self.weex_api_key = os.getenv('WEEX_API_KEY')
        self.weex_secret_key = os.getenv('WEEX_SECRET_KEY')
        self.weex_passphrase = os.getenv('WEEX_PASSPHRASE')
        
        # 交易客户端 - 改为交易所管理器
        self.bitget_client = None  # 保持向后兼容
        self.exchange_manager = None
        self.current_exchange = "bitget"  # 默认交易所
        
        # 价格监控系统
        self.take_profit_targets = {}  # {symbol: {'price': float, 'side': str, 'timestamp': datetime}}
        self.price_monitoring_active = False
        self.price_monitor_task = None
        
        # 消息上下文系统 - 用于关联交易信号和止盈信息
        self.recent_signals = []  # 存储最近的交易信号，用于匹配后续的止盈信息
        self.max_context_messages = 10  # 保留最近10条信号用于上下文匹配
        
        # 清理可能的错误数据
        self.cleanup_invalid_targets()
        
        # 先设置UI，再设置信号处理
        self.setup_ui()
        
        # 设置信号处理 - 防止自动SIGINT中断（必须在UI初始化后）
        self.setup_signal_handlers()
    
    def setup_signal_handlers(self):
        """设置信号处理器 - 防止自动中断"""
        def robust_signal_handler(signum, frame):
            self.log(f"收到信号 {signum}，程序继续运行", "WARNING")
            
            # 只有连续收到3次信号才真正退出
            if not hasattr(self, 'signal_count'):
                self.signal_count = 0
            
            self.signal_count += 1
            
            if self.signal_count >= 3:
                self.log("收到连续3次中断信号，准备退出", "ERROR")
                self.shutdown_requested = True
                if hasattr(self.root, 'quit'):
                    self.root.quit()
            else:
                self.log(f"忽略第{self.signal_count}次中断信号 (需要3次才退出)", "WARNING")
        
        # 设置SIGINT处理器
        signal.signal(signal.SIGINT, robust_signal_handler)
        
        # 如果有SIGBREAK（Windows），也处理它
        if hasattr(signal, 'SIGBREAK'):
            signal.signal(signal.SIGBREAK, robust_signal_handler)
        
    def setup_ui(self):
        """设置用户界面"""
        # 主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 标题
        title_label = ttk.Label(main_frame, text="Telegram交易跟单机器人", font=('Arial', 16, 'bold'))
        title_label.pack(pady=(0, 10))
        
        # 状态框架
        status_frame = ttk.LabelFrame(main_frame, text="系统状态", padding=10)
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 状态指示器
        self.status_label = ttk.Label(status_frame, text="未连接", font=('Arial', 12))
        self.status_label.pack(anchor=tk.W)
        
        self.channel_label = ttk.Label(status_frame, text="频道: 未连接")
        self.channel_label.pack(anchor=tk.W)
        
        # 添加群组列表显示
        self.groups_label = ttk.Label(status_frame, text="监控群组: 0个")
        self.groups_label.pack(anchor=tk.W)
        
        self.trade_count_label = ttk.Label(status_frame, text="交易次数: 0")
        self.trade_count_label.pack(anchor=tk.W)
        
        self.signal_count_label = ttk.Label(status_frame, text="中断信号: 0", foreground="red")
        self.signal_count_label.pack(anchor=tk.W)
        
        # 配置框架
        config_frame = ttk.LabelFrame(main_frame, text="交易配置", padding=10)
        config_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 检查交易配置
        trading_mode = "真实交易" if self.is_trading_enabled() else "模拟交易"
        config_text = f"交易金额: {self.trade_amount}U  |  杠杆: {self.leverage}x  |  模式: {trading_mode}"
        ttk.Label(config_frame, text=config_text).pack()
        
        # 控制按钮框架
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.start_button = ttk.Button(control_frame, text="启动机器人", command=self.start_bot)
        self.start_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.stop_button = ttk.Button(control_frame, text="停止机器人", command=self.stop_bot, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.test_button = ttk.Button(control_frame, text="测试信号", command=self.test_signal)
        self.test_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.reset_button = ttk.Button(control_frame, text="重置信号计数", command=self.reset_signal_count)
        self.reset_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.config_button = ttk.Button(control_frame, text="群组配置", command=self.show_groups_config)
        self.config_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.trading_config_button = ttk.Button(control_frame, text="交易配置", command=self.show_trading_config)
        self.trading_config_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.exchange_config_button = ttk.Button(control_frame, text="交易所配置", command=self.show_exchange_config)
        self.exchange_config_button.pack(side=tk.LEFT)
        
        # 日志框架
        log_frame = ttk.LabelFrame(main_frame, text="实时日志", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        # 日志文本框 - 使用更稳定的组合
        log_container = ttk.Frame(log_frame)
        log_container.pack(fill=tk.BOTH, expand=True)
        
        # 使用最简单的文本框设置，避免字体和颜色问题
        self.log_text = tk.Text(log_container, height=20, wrap=tk.WORD, state=tk.DISABLED)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(log_container, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        # 打包
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 确保GUI完全初始化后再显示日志
        self.root.after(100, self.show_initial_logs)
        
        # 启动状态更新定时器
        self.update_signal_display()
    
    def cleanup_invalid_targets(self):
        """清理可能的无效监控目标"""
        try:
            # 清空所有监控目标，避免缓存的错误数据
            self.take_profit_targets.clear()
            self.recent_signals.clear()
            print("已清理价格监控目标缓存")
        except Exception as e:
            print(f"清理监控目标失败: {e}")
    
    async def emergency_cleanup_invalid_price_targets(self):
        """紧急清理价格异常的监控目标"""
        try:
            if not self.take_profit_targets or not self.bitget_client:
                return
                
            invalid_targets = []
            
            self.log("🔍 执行价格合理性检查", "INFO")
            
            for symbol, target_info in list(self.take_profit_targets.items()):
                try:
                    # 获取持仓信息而不是市场价格
                    positions = await self.bitget_client.get_positions(symbol)
                    if not positions:
                        self.log(f"🚨 {symbol} 持仓已不存在，移除监控目标", "WARNING")
                        invalid_targets.append(symbol)
                        continue
                    
                    position = positions[0]
                    entry_price = float(position.get('averageOpenPrice', 0))
                    side = position.get('holdSide', '')  # long 或 short
                    target_price = target_info['price']
                    
                    if entry_price <= 0:
                        self.log(f"🚨 {symbol} 开仓价格无效，移除监控目标", "ERROR")
                        invalid_targets.append(symbol)
                        continue
                    
                    # 检查第一止盈目标的方向合理性
                    is_valid = True
                    reason = ""
                    
                    if side == "long":
                        # 多头：第一止盈应该高于开仓价
                        if target_price <= entry_price:
                            is_valid = False
                            reason = f"多头止盈目标{target_price}不应低于开仓价{entry_price}"
                        elif (target_price - entry_price) / entry_price > 2.0:  # 涨幅超过200%
                            is_valid = False
                            reason = f"多头止盈目标涨幅{((target_price - entry_price) / entry_price * 100):.1f}%过大"
                    elif side == "short":
                        # 空头：第一止盈应该低于开仓价
                        if target_price >= entry_price:
                            is_valid = False
                            reason = f"空头止盈目标{target_price}不应高于开仓价{entry_price}"
                        elif (entry_price - target_price) / entry_price > 2.0:  # 跌幅超过200%
                            is_valid = False
                            reason = f"空头止盈目标跌幅{((entry_price - target_price) / entry_price * 100):.1f}%过大"
                    
                    if not is_valid:
                        invalid_targets.append(symbol)
                        self.log(f"🚨 发现异常监控目标: {symbol}", "ERROR")
                        self.log(f"   开仓价格: {entry_price}, 目标价格: {target_price}, 方向: {side}", "ERROR")
                        self.log(f"   异常原因: {reason}", "ERROR")
                    else:
                        profit_ratio = abs(target_price - entry_price) / entry_price * 100
                        self.log(f"✅ {symbol} 止盈目标合理: {side} {profit_ratio:.1f}%", "SUCCESS")
                        
                except Exception as e:
                    self.log(f"检查 {symbol} 时出错: {e}, 标记为无效", "ERROR")
                    invalid_targets.append(symbol)
            
            # 移除无效目标
            for symbol in invalid_targets:
                if symbol in self.take_profit_targets:
                    del self.take_profit_targets[symbol]
                    self.log(f"🧹 已移除异常监控目标: {symbol}", "SUCCESS")
                
            if invalid_targets:
                self.log(f"🧹 清理完成，移除了 {len(invalid_targets)} 个异常目标", "SUCCESS")
            else:
                self.log("✅ 所有监控目标通过合理性检查", "SUCCESS")
                
        except Exception as e:
            self.log(f"价格检查失败: {e}", "ERROR")
    
    def add_signal_to_context(self, signal, source_group):
        """将交易信号添加到上下文中"""
        try:
            from datetime import datetime
            
            signal_context = {
                'symbol': signal.get('symbol', ''),
                'direction': signal.get('direction', ''),
                'source_group': source_group,
                'timestamp': datetime.now(),
                'signal_type': signal.get('signal_type', 'market_order')
            }
            
            self.recent_signals.append(signal_context)
            
            # 保持列表大小限制
            if len(self.recent_signals) > self.max_context_messages:
                self.recent_signals = self.recent_signals[-self.max_context_messages:]
                
            self.log(f"📝 已记录交易信号上下文: {signal_context['symbol']} from {source_group}", "INFO")
            
        except Exception as e:
            self.log(f"记录信号上下文失败: {e}", "ERROR")
    
    def find_matching_signal_for_take_profit(self, take_profit_price, source_group):
        """为第一止盈找到匹配的交易信号"""
        try:
            from datetime import datetime, timedelta
            
            # 在最近5分钟内的信号中查找匹配
            cutoff_time = datetime.now() - timedelta(minutes=5)
            
            # 优先匹配同一群组的最近信号
            matching_signals = []
            for signal_ctx in reversed(self.recent_signals):  # 从最新的开始
                if signal_ctx['timestamp'] > cutoff_time:
                    # 同一群组的信号优先级更高
                    priority = 2 if signal_ctx['source_group'] == source_group else 1
                    matching_signals.append((priority, signal_ctx))
            
            if matching_signals:
                # 按优先级排序，选择最匹配的信号
                matching_signals.sort(key=lambda x: (x[0], x[1]['timestamp']), reverse=True)
                best_match = matching_signals[0][1]
                
                self.log(f"🔗 第一止盈匹配信号: {best_match['symbol']} (来自: {best_match['source_group']})", "SUCCESS")
                self.log(f"📊 匹配详情: 方向={best_match['direction']}, 时间差={(datetime.now() - best_match['timestamp']).seconds}秒", "INFO")
                
                return best_match
            
            return None
            
        except Exception as e:
            self.log(f"匹配信号失败: {e}", "ERROR")
            return None
    
    def show_initial_logs(self):
        """显示初始日志（延迟执行以确保GUI完全初始化）"""
        try:
            self.log("交易机器人界面已启动")
            self.log(f"配置: {self.trade_amount}U, {self.leverage}x杠杆")
            
            # 显示交易模式信息
            if self.is_trading_enabled():
                self.log("交易模式: 真实交易 (已配置Bitget API)", "SUCCESS")
            else:
                self.log("交易模式: 模拟交易 (未配置Bitget API)", "WARNING")
                self.log("要启用真实交易，请配置Bitget API密钥", "WARNING")
            
            # 显示新功能信息
            self.log("🛡️ 自动止损: 开仓后立即设置亏损7U自动平仓", "SUCCESS")
            self.log("🎯 第一止盈: 50%平仓 + 自动设置保本止损", "SUCCESS")
            
            self.log("已启用信号干扰防护 (需要连续3次中断才退出)")
            self.log("点击'启动机器人'开始监控")
            self.log("已清理历史监控目标，避免错误数据干扰", "INFO")
        except Exception as e:
            print(f"显示初始日志失败: {e}")
    
    def is_trading_enabled(self):
        """检查是否启用真实交易"""
        return (TRADING_MODULES_AVAILABLE and 
                self.bitget_api_key and 
                self.bitget_secret_key and 
                self.bitget_passphrase and
                self.bitget_api_key != '你的API_KEY' and
                self.bitget_secret_key != '你的SECRET_KEY')
        
    def log(self, message, level="INFO"):
        """添加日志"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        # 安全检查：确保log_text存在且可用
        if not hasattr(self, 'log_text') or not self.log_text:
            print(f"[{timestamp}] {message}")  # 回退到控制台输出
            return
        
        # 颜色映射
        colors = {
            "INFO": "#00ff00",
            "SUCCESS": "#00ff00", 
            "ERROR": "#ff0000",
            "WARNING": "#ffff00",
            "TRADE": "#00ffff",
            "TAKE_PROFIT": "#ff00ff"  # 紫色显示止盈信号
        }
        
        color = colors.get(level, "#00ff00")
        
        # 插入日志
        try:
            # 检查组件是否还存在
            if not self.log_text.winfo_exists():
                print(f"[{timestamp}] {message}")  # 回退到控制台输出
                return
            
            # 启用文本编辑
            self.log_text.config(state=tk.NORMAL)
            
            # 插入日志
            self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
            
            # 限制日志行数，避免内存问题
            lines = self.log_text.get('1.0', tk.END).split('\n')
            if len(lines) > 1000:
                # 删除前面的行
                self.log_text.delete('1.0', f'{len(lines)-500}.0')
            
            # 滚动到底部
            self.log_text.see(tk.END)
            
            # 禁用文本编辑
            self.log_text.config(state=tk.DISABLED)
            
        except Exception as e:
            print(f"[{timestamp}] {message}")  # 回退到控制台输出
            print(f"日志插入错误: {e}")
        
        # 更新界面
        try:
            if hasattr(self, 'root') and self.root:
                self.root.update_idletasks()
        except Exception as e:
            pass
    
    def update_signal_display(self):
        """更新信号计数显示"""
        try:
            if hasattr(self, 'signal_count'):
                self.signal_count_label.config(text=f"中断信号: {self.signal_count}")
            
            # 每秒更新一次
            if not self.shutdown_requested:
                self.root.after(1000, self.update_signal_display)
                
        except Exception as e:
            print(f"信号显示更新错误: {e}")
    
    def reset_signal_count(self):
        """重置信号计数"""
        self.signal_count = 0
        self.log("信号计数已重置", "SUCCESS")
    
    def show_groups_config(self):
        """显示群组配置窗口"""
        try:
            config_window = tk.Toplevel(self.root)
            config_window.title("群组监控配置")
            config_window.geometry("600x400")
            
            # 标题
            title_label = ttk.Label(config_window, text="监控群组配置", font=('Arial', 14, 'bold'))
            title_label.pack(pady=10)
            
            # 当前监控的群组
            current_frame = ttk.LabelFrame(config_window, text="当前监控的群组", padding=10)
            current_frame.pack(fill=tk.X, padx=10, pady=5)
            
            if hasattr(self, 'target_channels') and self.target_channels:
                for i, channel in enumerate(self.target_channels, 1):
                    channel_name = getattr(channel, 'title', 'Unknown')
                    ttk.Label(current_frame, text=f"{i}. {channel_name}").pack(anchor=tk.W)
            else:
                ttk.Label(current_frame, text="暂无监控群组").pack()
            
            # 配置规则
            rules_frame = ttk.LabelFrame(config_window, text="匹配规则", padding=10)
            rules_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            
            if GROUPS_CONFIG_AVAILABLE:
                target_keywords = get_monitor_groups()
                ttk.Label(rules_frame, text="当前配置的群组关键词:").pack(anchor=tk.W)
                for i, keywords in enumerate(target_keywords, 1):
                    ttk.Label(rules_frame, text=f"{i}. {keywords}").pack(anchor=tk.W, padx=20)
            else:
                ttk.Label(rules_frame, text="使用默认配置: [['Seven', '司'], ['Seven', 'VIP']]").pack(anchor=tk.W)
            
            # 说明文字
            help_text = """
添加新群组步骤:
1. 编辑 groups_config.py 文件
2. 在 MONITOR_GROUPS 列表中添加关键词
3. 重启机器人生效

示例: ['新群组', '关键词'] 会匹配包含"新群组"和"关键词"的群组
            """
            
            help_label = tk.Text(rules_frame, height=8, wrap=tk.WORD)
            help_label.pack(fill=tk.BOTH, expand=True, pady=10)
            help_label.insert(tk.END, help_text)
            help_label.config(state=tk.DISABLED)
            
            # 关闭按钮
            ttk.Button(config_window, text="关闭", command=config_window.destroy).pack(pady=10)
            
        except Exception as e:
            self.log(f"显示群组配置失败: {e}", "ERROR")
        
    def update_status(self, connected=False, channel_names=None):
        """更新状态显示"""
        try:
            if connected and channel_names:
                self.status_label.config(text="已连接并监控中")
                if isinstance(channel_names, list):
                    # 多个群组
                    if len(channel_names) == 1:
                        self.channel_label.config(text=f"频道: {channel_names[0]}")
                    else:
                        self.channel_label.config(text=f"主频道: {channel_names[0]}")
                    self.groups_label.config(text=f"监控群组: {len(channel_names)}个")
                else:
                    # 单个群组（兼容旧版本）
                    self.channel_label.config(text=f"频道: {channel_names}")
                    self.groups_label.config(text="监控群组: 1个")
            else:
                self.status_label.config(text="未连接")
                self.channel_label.config(text="频道: 未连接")
                self.groups_label.config(text="监控群组: 0个")
            
            self.trade_count_label.config(text=f"交易次数: {self.trade_count}")
        except Exception as e:
            print(f"状态更新错误: {e}")
        
    def start_bot(self):
        """启动机器人"""
        if self.running:
            return
            
        self.log("正在启动机器人...")
        
        # 检查交易配置
        if self.is_trading_enabled():
            self.log("检测到Bitget API配置，启用真实交易模式", "SUCCESS")
        else:
            self.log("未检测到完整的Bitget API配置，使用模拟交易模式", "WARNING")
            self.log("要启用真实交易，请在.env文件中配置:", "WARNING")
            self.log("BITGET_API_KEY, BITGET_SECRET_KEY, BITGET_PASSPHRASE", "WARNING")
        
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        # 在新线程中运行异步代码
        threading.Thread(target=self.run_async_bot, daemon=True).start()
        
    def run_async_bot(self):
        """在新线程中运行异步机器人"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(self.async_start_bot())
        except Exception as e:
            self.log(f"机器人运行出错: {e}", "ERROR")
        finally:
            loop.close()
            
    async def async_start_bot(self):
        """异步启动机器人"""
        try:
            from telethon import TelegramClient, events
            
            # 初始化Bitget客户端
            if self.is_trading_enabled():
                try:
                    # 先初始化配置，BitgetClient会自动使用全局config
                    config = Config()
                    self.bitget_client = BitgetClient()
                    self.log("Bitget交易客户端已初始化", "SUCCESS")
                    
                    # 测试连接
                    await self.bitget_client.get_account_info()
                    self.log("Bitget API连接测试成功", "SUCCESS")
                    
                except Exception as e:
                    self.log(f"Bitget客户端初始化失败: {e}", "ERROR")
                    self.log("将使用模拟交易模式", "WARNING")
                    self.bitget_client = None
            
            # 连接Telegram
            self.log("连接Telegram服务器...")
            self.telegram_client = TelegramClient('trading_session', self.api_id, self.api_hash)
            await self.telegram_client.connect()
            
            if not await self.telegram_client.is_user_authorized():
                self.log("未认证，请先运行认证程序", "ERROR")
                return
                
            self.log("Telegram连接成功", "SUCCESS")
            
            # 查找多个目标频道
            self.log("查找目标频道...")
            
            # 获取要监控的群组关键词
            if GROUPS_CONFIG_AVAILABLE:
                target_keywords = get_monitor_groups()
                self.log(f"从配置文件加载了 {len(target_keywords)} 个群组规则", "SUCCESS")
            else:
                # 默认配置
                target_keywords = [
                    ['Seven', '司'],  # Seven的手工壽司鋪
                    ['Seven', 'VIP'], # Seven VIP群组
                ]
                self.log("使用默认群组配置", "WARNING")
            
            channel_names = []
            async for dialog in self.telegram_client.iter_dialogs():
                if dialog.is_channel:
                    # 检查是否匹配任何目标关键词组合
                    for keywords in target_keywords:
                        if all(keyword in dialog.title for keyword in keywords):
                            self.target_channels.append(dialog.entity)
                            channel_names.append(dialog.title)
                            self.log(f"找到频道: {dialog.title}", "SUCCESS")
                            break
                    
            if not self.target_channels:
                self.log("未找到任何目标频道", "ERROR")
                self.log("请检查群组名称是否包含'Seven'和'司'或'VIP'", "ERROR")
                return
                
            self.log(f"总共找到 {len(self.target_channels)} 个监控频道", "SUCCESS")
            self.update_status(True, channel_names)
            
            # 为所有目标频道注册消息处理器
            @self.telegram_client.on(events.NewMessage(chats=self.target_channels))
            async def handle_message(event):
                await self.handle_new_message(event)
                
            self.running = True
            self.log("👀 开始监控频道消息...", "SUCCESS")
            self.log("💡 等待交易信号 (#币种 市價多/空)")
            
            # 保持运行
            await self.telegram_client.run_until_disconnected()
            
        except Exception as e:
            self.log(f" 启动失败: {e}", "ERROR")
        finally:
            self.running = False
            self.update_status(False)
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            
    async def handle_new_message(self, event):
        """处理新消息"""
        try:
            message = event.message
            if not message.text:
                return
                
            sender = await message.get_sender()
            sender_name = getattr(sender, 'first_name', 'Unknown') if sender else 'Unknown'
            
            # 获取消息来源群组
            chat = await event.get_chat()
            chat_name = getattr(chat, 'title', 'Unknown Chat')
            
            self.log(f"[{chat_name}] {sender_name}: {message.text[:50]}...")
            
            # 解析信号
            signal = self.parse_signal(message.text)
            
            if signal:
                self.log(f"检测到交易信号! 来源: {chat_name}", "SUCCESS")
                # 在信号中添加来源信息
                signal['source_group'] = chat_name
                await self.execute_trade(signal)
                
        except Exception as e:
            self.log(f" 处理消息失败: {e}", "ERROR")
            
    def parse_signal(self, message):
        """解析交易信号"""
        if not message:
            return None
        
        # 检查是否是第一止盈信号
        first_tp_match = re.search(r'第一止[盈贏][:：]?\s*(\d+(?:\.\d+)?)', message)
        if first_tp_match:
            take_profit_price = float(first_tp_match.group(1))
            return {
                'signal_type': 'first_take_profit',
                'take_profit': take_profit_price,
                'raw_message': message
            }
        
        # 原始开仓信号检测
        match = re.search(r'#(\w+)\s+市[價价]([多空])', message)
        if match:
            symbol = match.group(1).upper()
            direction = match.group(2)
            
            if not symbol.endswith('USDT'):
                symbol = f"{symbol}USDT"
                
            side = 'buy' if direction == '多' else 'sell'
            
            # 提取止盈止损
            stop_loss = None
            take_profit = None
            
            sl_match = re.search(r'止[损損]:\s*(\d+(?:\.\d+)?)', message)
            if sl_match:
                stop_loss = float(sl_match.group(1))
                
            tp_match = re.search(r'第一止[盈贏]:\s*(\d+(?:\.\d+)?)', message)
            if tp_match:
                take_profit = float(tp_match.group(1))
                
            return {
                'signal_type': 'market_order',
                'symbol': symbol,
                'side': side,
                'direction_cn': '做多' if side == 'buy' else '做空',
                'amount': self.trade_amount,
                'leverage': self.leverage,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'raw_message': message
            }
            
        return None
        
    async def execute_trade(self, signal):
        """执行交易"""
        try:
            # 检查信号类型
            signal_type = signal.get('signal_type', 'market_order')
            
            if signal_type == 'first_take_profit':
                # 处理第一止盈信号
                await self.handle_first_take_profit(signal)
                return
            
            # 处理普通开仓信号
            self.trade_count += 1
            
            # 记录信号到上下文中，用于后续的止盈匹配
            self.add_signal_to_context(signal, signal.get('source_group', '未知群组'))
            
            # 获取当前监控的群组名称列表
            channel_names = [getattr(ch, 'title', 'Unknown') for ch in self.target_channels] if hasattr(self, 'target_channels') else ["未知"]
            self.update_status(True, channel_names)
            
            self.log("=" * 50, "TRADE")
            self.log(f"执行交易 #{self.trade_count}", "TRADE")
            self.log(f"币种: {signal['symbol']}", "TRADE")
            self.log(f"来源: {signal.get('source_group', '未知群组')}", "TRADE")
            self.log(f"方向: {signal['direction_cn']}", "TRADE") 
            self.log(f" 金额: {signal['amount']}U", "TRADE")
            self.log(f" 杠杆: {signal['leverage']}x", "TRADE")
            
            if signal.get('stop_loss'):
                self.log(f"止损: {signal['stop_loss']}", "TRADE")
                
            if signal.get('take_profit'):
                self.log(f" 止盈: {signal['take_profit']}", "TRADE")
                
            # 真实交易执行
            if self.bitget_client:
                self.log("执行真实交易...", "TRADE")
                
                # 创建交易信号对象
                if TRADING_MODULES_AVAILABLE:
                    from src.trading.signal_parser import TradingSignal, OrderSide, SignalType
                    
                    trading_signal = TradingSignal(
                        symbol=signal['symbol'],
                        side=OrderSide.BUY if signal.get('direction') == 'buy' or signal.get('direction_cn') == '做多' else OrderSide.SELL,
                        signal_type=SignalType.MARKET_ORDER,
                        amount=signal.get('amount', self.trade_amount),
                        stop_loss=signal.get('stop_loss'),
                        take_profit=signal.get('take_profit'),
                        leverage=signal.get('leverage', self.leverage)
                    )
                    
                    # 执行交易
                    result = await self.bitget_client.execute_signal(trading_signal)
                    
                    if result and result.get('success'):
                        self.log("真实交易执行成功!", "SUCCESS")
                        if result.get('order'):
                            order_id = result['order'].get('orderId')
                            if order_id:
                                self.log(f"订单ID: {order_id}", "SUCCESS")
                        
                        # 显示自动止损设置状态
                        if result.get('auto_stop_loss_order'):
                            self.log("✅ 自动止损已设置: 亏损7U时自动平仓", "SUCCESS")
                        else:
                            self.log("⚠️ 自动止损设置失败或跳过", "WARNING")
                    else:
                        error_msg = result.get('error', '未知错误') if result else '未知错误'
                        self.log(f"真实交易执行失败: {error_msg}", "ERROR")
                        
            else:
                # 模拟交易
                self.log("执行模拟交易...", "WARNING")
                await asyncio.sleep(1)  # 模拟API调用延迟
                self.log("模拟交易执行完成", "SUCCESS")
            
            self.log("=" * 50, "TRADE")
            
        except Exception as e:
            self.log(f" 交易执行失败: {e}", "ERROR")
    
    async def handle_first_take_profit(self, signal):
        """处理第一止盈信号：设置价格监控目标"""
        try:
            self.log("=" * 50, "TAKE_PROFIT")
            self.log("🎯 检测到第一止盈价格目标!", "SUCCESS")
            self.log(f"止盈目标价格: {signal['take_profit']}", "TAKE_PROFIT")
            self.log(f"来源: {signal.get('source_group', '未知群组')}", "TAKE_PROFIT")
            
            take_profit_price = signal['take_profit']
            source_group = signal.get('source_group', '未知群组')
            
            # 尝试通过消息上下文匹配对应的币种
            matched_signal = self.find_matching_signal_for_take_profit(take_profit_price, source_group)
            
            if self.bitget_client:
                # 获取当前持仓来确定要监控的币种
                try:
                    positions = await self.bitget_client.get_positions()
                    if positions:
                        self.log(f"📊 发现 {len(positions)} 个持仓，将为所有持仓设置第一止盈监控", "INFO")
                        
                        # 显示所有持仓供用户了解
                        for i, pos in enumerate(positions):
                            pos_symbol = pos.get('symbol')
                            pos_side = pos.get('holdSide')
                            pos_size = pos.get('total', 0)
                            pos_price = pos.get('averageOpenPrice', 0)
                            self.log(f"持仓{i+1}: {pos_symbol} {pos_side} {pos_size}张 @{pos_price}", "INFO")
                        
                        # 智能选择持仓进行第一止盈监控
                        # 策略：优先使用消息上下文匹配，其次选择最新持仓
                        from datetime import datetime
                        
                        self.log("🔍 智能选择持仓进行第一止盈监控", "INFO")
                        
                        selected_position = None
                        selection_reason = ""
                        
                        # 策略1：如果有匹配的信号上下文，优先使用
                        if matched_signal and matched_signal['symbol']:
                            target_symbol = matched_signal['symbol']
                            # 转换为合约格式
                            if target_symbol.endswith('USDT') and not target_symbol.endswith('_UMCBL'):
                                target_symbol = f"{target_symbol}_UMCBL"
                            
                            # 在持仓中查找匹配的币种
                            for pos in positions:
                                if pos.get('symbol') == target_symbol:
                                    selected_position = pos
                                    selection_reason = f"消息上下文匹配 ({matched_signal['symbol']})"
                                    break
                        
                        # 策略2：如果上下文匹配失败，选择最新持仓
                        if not selected_position:
                            try:
                                sorted_positions = sorted(positions, key=lambda x: int(x.get('cTime', 0)), reverse=True)
                                selected_position = sorted_positions[0]
                                selection_reason = "最新开仓时间"
                            except:
                                selected_position = positions[0]
                                selection_reason = "默认选择"
                        
                        symbol = selected_position.get('symbol')
                        side = selected_position.get('holdSide')
                        open_time = selected_position.get('cTime', 0)
                        open_price = selected_position.get('averageOpenPrice', 0)
                        
                        # 显示选择逻辑
                        if len(positions) > 1:
                            self.log(f"📊 多持仓情况，选择策略: {selection_reason}", "INFO")
                            for i, pos in enumerate(positions):
                                pos_symbol = pos.get('symbol')
                                pos_time = pos.get('cTime', 0)
                                status = "✅ 已选择" if pos_symbol == symbol else "⏸️ 未选择"
                                self.log(f"  {status} {pos_symbol} (开仓时间: {pos_time})", "INFO")
                        
                        self.log(f"🎯 选择持仓: {symbol}", "TAKE_PROFIT")
                        self.log(f"📊 选择原因: {selection_reason}", "INFO")
                        self.log(f"📊 持仓详情: 方向={side}, 开仓价格={open_price}", "INFO")
                        
                        # 检查是否已经有监控目标
                        if symbol in self.take_profit_targets:
                            self.log(f"⚠️ {symbol} 已有监控目标，将更新价格", "WARNING")
                        
                        # 存储止盈目标（只为选择的持仓）
                        self.take_profit_targets[symbol] = {
                            'price': take_profit_price,
                            'side': side,
                            'timestamp': datetime.now(),
                            'executed': False
                        }
                        
                        self.log(f"📝 已设置价格监控: {symbol} (方向: {side})", "TAKE_PROFIT")
                        self.log(f"🎯 目标价格: {take_profit_price}", "TAKE_PROFIT")
                        self.log("🤖 价格达到目标时将自动执行50%止盈+保本止损", "SUCCESS")
                        
                        # 启动价格监控
                        if not self.price_monitoring_active:
                            await self.start_price_monitoring()
                    else:
                        self.log("⚠️ 未找到持仓，无法设置价格监控", "WARNING")
                        self.log(f"📝 记录止盈目标: {take_profit_price} (等待持仓信息)", "TAKE_PROFIT")
                except Exception as e:
                    self.log(f"获取持仓信息失败: {e}", "ERROR")
            else:
                self.log("📝 模拟模式: 记录第一止盈目标价格", "WARNING")
            
            self.log("=" * 50, "TAKE_PROFIT")
            
        except Exception as e:
            self.log(f"❌ 第一止盈处理失败: {e}", "ERROR")
    
    async def start_price_monitoring(self):
        """启动价格监控"""
        if self.price_monitoring_active:
            return
            
        self.price_monitoring_active = True
        self.log("🔍 启动价格监控系统", "SUCCESS")
        
        # 在后台运行价格监控任务
        if self.price_monitor_task:
            self.price_monitor_task.cancel()
        
        self.price_monitor_task = asyncio.create_task(self.price_monitor_loop())
    
    async def stop_price_monitoring(self):
        """停止价格监控"""
        self.price_monitoring_active = False
        if self.price_monitor_task:
            self.price_monitor_task.cancel()
            self.price_monitor_task = None
        self.log("⏹️ 价格监控系统已停止", "INFO")
    
    async def price_monitor_loop(self):
        """价格监控主循环"""
        try:
            while self.price_monitoring_active and self.bitget_client:
                if not self.take_profit_targets:
                    # 没有监控目标，暂停监控
                    await asyncio.sleep(10)
                    continue
                
                # 首先执行紧急清理检查
                await self.emergency_cleanup_invalid_price_targets()
                
                # 检查每个监控目标
                targets_to_remove = []
                for symbol, target_info in self.take_profit_targets.items():
                    if target_info['executed']:
                        continue
                        
                    try:
                        # 获取当前市场价格
                        current_price = await self.get_current_price(symbol)
                        if current_price is None:
                            continue
                        
                        target_price = target_info['price']
                        side = target_info['side']
                        
                        # 价格监控日志
                        self.log(f"📊 监控中: {symbol} 当前价格 {current_price}, 目标 {target_price} ({side})", "INFO")
                        
                        # 检查是否达到止盈条件
                        should_execute = False
                        if side == 'long' and current_price >= target_price:
                            # 多头持仓，价格达到或超过目标
                            should_execute = True
                            self.log(f"✅ 多仓止盈条件满足: {current_price} >= {target_price}", "SUCCESS")
                        elif side == 'short' and current_price <= target_price:
                            # 空头持仓，价格达到或低于目标
                            should_execute = True
                            self.log(f"✅ 空仓止盈条件满足: {current_price} <= {target_price}", "SUCCESS")
                        else:
                            self.log(f"⏳ 止盈条件未满足 ({side}: {current_price} vs {target_price})", "INFO")
                        
                        if should_execute:
                            self.log(f"🎯 价格触发! {symbol}: 当前价格 {current_price}, 目标 {target_price}", "SUCCESS")
                            self.log("🚀 准备执行第一止盈策略...", "INFO")
                            
                            # 执行50%止盈 + 保本止损
                            try:
                                success = await self.execute_first_take_profit_strategy(symbol, current_price, target_price)
                                self.log(f"📊 第一止盈策略执行结果: {success}", "INFO")
                            except Exception as e:
                                self.log(f"❌ 第一止盈策略执行异常: {e}", "ERROR")
                                import traceback
                                self.log(f"📋 异常详情: {traceback.format_exc()}", "DEBUG")
                                success = False
                            
                            if success:
                                target_info['executed'] = True
                                self.log(f"✅ {symbol} 第一止盈策略执行完成", "SUCCESS")
                            else:
                                self.log(f"❌ {symbol} 第一止盈策略执行失败", "ERROR")
                                
                    except Exception as e:
                        self.log(f"监控 {symbol} 价格时出错: {e}", "ERROR")
                
                # 清理已执行的目标
                self.take_profit_targets = {k: v for k, v in self.take_profit_targets.items() if not v['executed']}
                
                # 如果没有更多目标，停止监控
                if not self.take_profit_targets:
                    self.log("📝 所有止盈目标已处理完成，停止价格监控", "INFO")
                    self.price_monitoring_active = False
                    break
                
                # 等待下次检查 (每30秒检查一次)
                await asyncio.sleep(30)
                
        except asyncio.CancelledError:
            self.log("价格监控任务被取消", "INFO")
        except Exception as e:
            self.log(f"价格监控循环出错: {e}", "ERROR")
        finally:
            self.price_monitoring_active = False
    
    async def get_current_price(self, symbol):
        """获取当前市场价格"""
        try:
            # 获取指定symbol的持仓信息
            positions = await self.bitget_client.get_positions(symbol)
            if positions:
                # 找到匹配symbol的持仓
                target_position = None
                for pos in positions:
                    if pos.get('symbol') == symbol:
                        target_position = pos
                        break
                
                if target_position:
                    market_price = target_position.get('marketPrice')
                    if market_price:
                        self.log(f"📊 获取 {symbol} 当前价格: {market_price}", "DEBUG")
                        return float(market_price)
                    else:
                        self.log(f"⚠️ {symbol} 持仓中无市场价格信息", "WARNING")
                else:
                    self.log(f"⚠️ 未找到 {symbol} 的持仓信息", "WARNING")
            else:
                self.log(f"⚠️ {symbol} 无持仓记录", "WARNING")
            return None
        except Exception as e:
            self.log(f"获取 {symbol} 价格失败: {e}", "ERROR")
            return None
    
    async def execute_first_take_profit_strategy(self, symbol, current_price, target_price):
        """执行第一止盈策略：50%平仓 + 保本止损"""
        try:
            self.log("=" * 50, "TAKE_PROFIT")
            self.log(f"🎯 触发第一止盈策略: {symbol}", "SUCCESS")
            self.log(f"📊 当前价格: {current_price}, 目标价格: {target_price}", "TAKE_PROFIT")
            
            if not self.bitget_client:
                self.log("❌ Bitget客户端未初始化", "ERROR")
                self.log("=" * 50, "TAKE_PROFIT")
                return False
            
            # 确保使用合约格式的symbol
            contract_symbol = symbol
            if contract_symbol.endswith('USDT') and not contract_symbol.endswith('_UMCBL'):
                contract_symbol = f"{contract_symbol}_UMCBL"
            
            # 直接执行50%平仓和保本止损，不通过信号处理
            self.log("📤 开始执行50%平仓...", "INFO")
            
            # 第一步：50%平仓
            try:
                self.log("🔄 正在调用50%平仓方法...", "INFO")
                close_result = await self.bitget_client.close_position_partial(contract_symbol, 50.0)
                self.log(f"📋 平仓方法返回结果: {close_result}", "DEBUG")
                
                if not close_result:
                    self.log("❌ 50%平仓失败 - 返回结果为空", "ERROR")
                    self.log("=" * 50, "TAKE_PROFIT")
                    return False
                
                self.log("✅ 50%平仓成功!", "SUCCESS")
                if close_result.get('orderId'):
                    self.log(f"📤 平仓订单ID: {close_result['orderId']}", "SUCCESS")
                else:
                    self.log("⚠️ 平仓结果中没有订单ID", "WARNING")
                    
            except Exception as e:
                self.log(f"❌ 50%平仓过程中发生异常: {e}", "ERROR")
                import traceback
                self.log(f"📋 异常详情: {traceback.format_exc()}", "DEBUG")
                self.log("=" * 50, "TAKE_PROFIT")
                return False
            
            # 等待平仓完成
            await asyncio.sleep(2)
            
            # 获取开仓价格用于设置保本止损
            positions = await self.bitget_client.get_positions(contract_symbol)
            if not positions:
                self.log("⚠️ 未找到持仓信息，无法设置保本止损", "WARNING")
                self.log("=" * 50, "TAKE_PROFIT")
                return True  # 50%平仓成功，即使保本止损失败也返回True
            
            position = positions[0]
            entry_price = float(position.get('averageOpenPrice', 0))
            if entry_price <= 0:
                self.log("⚠️ 无法获取开仓价格，无法设置保本止损", "WARNING")
                self.log("=" * 50, "TAKE_PROFIT")
                return True
            
            # 第二步：设置保本止损（重试机制）
            self.log(f"🛡️ 设置保本止损，开仓价格: {entry_price}", "INFO")
            
            stop_loss_result = None
            max_retries = 3
            
            for retry in range(max_retries):
                try:
                    stop_loss_result = await self.bitget_client.set_break_even_stop_loss(contract_symbol, entry_price)
                    if stop_loss_result:
                        self.log("✅ 保本止损设置成功!", "SUCCESS")
                        if stop_loss_result.get('orderId'):
                            self.log(f"🛡️ 止损订单ID: {stop_loss_result['orderId']}", "SUCCESS")
                        break
                    else:
                        self.log(f"⚠️ 保本止损设置失败，尝试重试 {retry + 1}/{max_retries}", "WARNING")
                        if retry < max_retries - 1:
                            await asyncio.sleep(2)  # 等待2秒后重试
                except Exception as e:
                    self.log(f"❌ 保本止损设置异常 (尝试 {retry + 1}/{max_retries}): {e}", "ERROR")
                    if retry < max_retries - 1:
                        await asyncio.sleep(2)  # 等待2秒后重试
            
            if not stop_loss_result:
                self.log("🚨 警告: 保本止损设置失败，请手动设置止损!", "ERROR")
                self.log(f"🚨 建议手动设置止损价格: {entry_price}", "ERROR")
                # 即使保本止损失败，50%平仓已成功，仍返回True
            
            self.log("🎉 第一止盈策略执行完成!", "SUCCESS")
            self.log("=" * 50, "TAKE_PROFIT")
            return True
                
        except Exception as e:
            self.log(f"❌ 执行第一止盈策略失败: {e}", "ERROR")
            self.log("=" * 50, "TAKE_PROFIT")
            return False
            
    def stop_bot(self):
        """停止机器人"""
        if not self.running:
            return
            
        self.log(" 正在停止机器人...", "WARNING")
        
        # 停止价格监控
        if self.price_monitoring_active:
            asyncio.create_task(self.stop_price_monitoring())
        
        if self.telegram_client:
            # 在新线程中断开连接
            threading.Thread(target=self.async_stop, daemon=True).start()
            
        self.running = False
        self.update_status(False)
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        
    def async_stop(self):
        """异步停止"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            if self.telegram_client:
                loop.run_until_complete(self.telegram_client.disconnect())
        except:
            pass
        finally:
            loop.close()
            
        self.log(" 机器人已停止", "SUCCESS")
        
    def test_signal(self):
        """测试信号解析"""
        test_signals = [
            "#BTC 市價多",
            "#ETH 市價空 止损2800 第一止盈2500",
            "#SOL 市價多 第一止盈180"
        ]
        
        self.log(" 开始测试信号解析...", "WARNING")
        
        for signal_text in test_signals:
            self.log(f"测试: {signal_text}")
            signal = self.parse_signal(signal_text)
            
            if signal:
                self.log(f" 解析成功: {signal['symbol']} {signal['direction_cn']}")
            else:
                self.log(" 解析失败")
                
        self.log(" 测试完成", "SUCCESS")
    
    def show_trading_config(self):
        """显示交易配置窗口"""
        try:
            # 创建配置窗口
            config_window = tk.Toplevel(self.root)
            config_window.title("交易配置")
            config_window.geometry("500x450")
            config_window.resizable(True, True)
            
            # 使窗口居中
            config_window.transient(self.root)
            config_window.grab_set()
            
            # 主框架
            main_frame = ttk.Frame(config_window, padding=20)
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # 当前配置显示
            current_frame = ttk.LabelFrame(main_frame, text="当前配置", padding=10)
            current_frame.pack(fill=tk.X, pady=(0, 15))
            
            # 当前交易所状态
            exchange_status = "✅ 已配置" if self.current_exchange == "bitget" and self.is_trading_enabled() else "⚠️ 未配置或开发中"
            
            current_info = ttk.Label(current_frame, 
                text=f"当前交易所: {self.current_exchange.title()} {exchange_status}\n保证金: {self.trade_amount}U | 杠杆: {self.leverage}x\n交易模式: {'真实交易' if self.is_trading_enabled() else '模拟交易'}")
            current_info.pack()
            
            # 配置设置框架
            settings_frame = ttk.LabelFrame(main_frame, text="交易设置", padding=10)
            settings_frame.pack(fill=tk.X, pady=(0, 15))
            
            # 交易所选择 - 使用单选按钮替代下拉菜单
            exchange_frame = ttk.LabelFrame(settings_frame, text="选择交易所", padding=10)
            exchange_frame.pack(fill=tk.X, pady=(0, 10))
            
            self.exchange_var = tk.StringVar(value=self.current_exchange)
            
            # 创建单选按钮网格
            exchanges = [
                ("Bitget", "bitget", "完整功能"),
                ("Binance", "binance", "开发中"),
                ("Bybit", "bybit", "开发中"),
                ("OKEx", "okex", "开发中"),
                ("Weex", "weex", "新增")
            ]
            
            for i, (name, value, status) in enumerate(exchanges):
                row = i // 3  # 每行3个
                col = i % 3
                
                frame = ttk.Frame(exchange_frame)
                frame.grid(row=row, column=col, sticky="w", padx=5, pady=2)
                
                radio = ttk.Radiobutton(frame, text=name, variable=self.exchange_var, value=value)
                radio.pack(side=tk.LEFT)
                
                status_label = ttk.Label(frame, text=f"({status})", foreground="gray", font=("Arial", 8))
                status_label.pack(side=tk.LEFT, padx=(5, 0))
            
            # 配置网格权重
            for col in range(3):
                exchange_frame.columnconfigure(col, weight=1)
            
            # 保证金设置
            margin_frame = ttk.Frame(settings_frame)
            margin_frame.pack(fill=tk.X, pady=(0, 10))
            
            ttk.Label(margin_frame, text="保证金 (U):").pack(side=tk.LEFT)
            self.margin_var = tk.DoubleVar(value=self.trade_amount)
            margin_spinbox = ttk.Spinbox(margin_frame, from_=0.1, to=100.0, increment=0.1, 
                                       textvariable=self.margin_var, width=10)
            margin_spinbox.pack(side=tk.RIGHT)
            
            # 杠杆设置
            leverage_frame = ttk.Frame(settings_frame)
            leverage_frame.pack(fill=tk.X, pady=(0, 10))
            
            ttk.Label(leverage_frame, text="杠杆倍数:").pack(side=tk.LEFT)
            self.leverage_var = tk.IntVar(value=self.leverage)
            leverage_spinbox = ttk.Spinbox(leverage_frame, from_=1, to=125, increment=1, 
                                         textvariable=self.leverage_var, width=10)
            leverage_spinbox.pack(side=tk.RIGHT)
            
            # 快捷设置按钮
            quick_frame = ttk.LabelFrame(main_frame, text="快捷设置", padding=10)
            quick_frame.pack(fill=tk.X, pady=(0, 15))
            
            # 快捷按钮行1
            quick_row1 = ttk.Frame(quick_frame)
            quick_row1.pack(fill=tk.X, pady=(0, 5))
            
            ttk.Button(quick_row1, text="1U/10x", 
                      command=lambda: self.set_quick_config(1.0, 10)).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(quick_row1, text="2U/20x", 
                      command=lambda: self.set_quick_config(2.0, 20)).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(quick_row1, text="5U/10x", 
                      command=lambda: self.set_quick_config(5.0, 10)).pack(side=tk.LEFT)
            
            # 快捷按钮行2
            quick_row2 = ttk.Frame(quick_frame)
            quick_row2.pack(fill=tk.X)
            
            ttk.Button(quick_row2, text="10U/5x", 
                      command=lambda: self.set_quick_config(10.0, 5)).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(quick_row2, text="20U/3x", 
                      command=lambda: self.set_quick_config(20.0, 3)).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(quick_row2, text="50U/2x", 
                      command=lambda: self.set_quick_config(50.0, 2)).pack(side=tk.LEFT)
            
            # 按钮框架
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X)
            
            # 测试配置按钮
            ttk.Button(button_frame, text="测试选中交易所", 
                      command=self.test_selected_exchange).pack(side=tk.LEFT)
            
            ttk.Button(button_frame, text="应用", 
                      command=lambda: self.apply_trading_config(config_window)).pack(side=tk.RIGHT, padx=(5, 0))
            ttk.Button(button_frame, text="取消", 
                      command=config_window.destroy).pack(side=tk.RIGHT)
            
        except Exception as e:
            self.log(f"显示交易配置失败: {e}", "ERROR")
    
    def set_quick_config(self, margin, leverage):
        """设置快捷配置"""
        self.margin_var.set(margin)
        self.leverage_var.set(leverage)
    
    def test_selected_exchange(self):
        """测试选中的交易所配置"""
        try:
            if not hasattr(self, 'exchange_var'):
                tk.messagebox.showerror("错误", "请先选择一个交易所")
                return
                
            selected_exchange = self.exchange_var.get()
            
            if selected_exchange == "bitget":
                if self.bitget_api_key and self.bitget_secret_key and self.bitget_passphrase:
                    self.log(f"测试Bitget连接...", "INFO")
                    tk.messagebox.showinfo("测试结果", "Bitget: ✅ 配置完整\n连接测试功能开发中...")
                else:
                    tk.messagebox.showwarning("配置不完整", "Bitget: ⚠️ 请先在'交易所配置'中设置API密钥")
            elif selected_exchange == "weex":
                if self.weex_api_key and self.weex_secret_key:
                    self.log(f"测试Weex连接...", "INFO")
                    tk.messagebox.showinfo("测试结果", "Weex: ✅ 配置完整\n连接测试功能开发中...")
                else:
                    tk.messagebox.showwarning("配置不完整", "Weex: ⚠️ 请先在'交易所配置'中设置API密钥")
            else:
                tk.messagebox.showinfo("交易所状态", f"{selected_exchange.title()}: 🔄 功能开发中\n敬请期待！")
            
        except Exception as e:
            self.log(f"测试交易所失败: {e}", "ERROR")
            tk.messagebox.showerror("错误", f"测试失败: {e}")
    
    def apply_trading_config(self, window):
        """应用交易配置"""
        try:
            new_exchange = self.exchange_var.get()
            new_margin = self.margin_var.get()
            new_leverage = self.leverage_var.get()
            
            # 验证配置
            if new_margin <= 0:
                tk.messagebox.showerror("错误", "保证金必须大于0")
                return
                
            if new_leverage < 1 or new_leverage > 125:
                tk.messagebox.showerror("错误", "杠杆倍数必须在1-125之间")
                return
            
            # 应用配置
            old_exchange = self.current_exchange
            old_margin = self.trade_amount
            old_leverage = self.leverage
            
            self.current_exchange = new_exchange
            self.trade_amount = new_margin
            self.leverage = new_leverage
            
            # 更新配置文件
            self.save_trading_config()
            
            # 记录日志
            changes = []
            if old_exchange != new_exchange:
                changes.append(f"交易所: {old_exchange} → {new_exchange}")
            if old_margin != new_margin or old_leverage != new_leverage:
                changes.append(f"参数: {old_margin}U/{old_leverage}x → {new_margin}U/{new_leverage}x")
            
            if changes:
                self.log(f"交易配置已更新: {', '.join(changes)}", "SUCCESS")
            
            # 关闭窗口
            window.destroy()
            
            # 显示确认消息
            tk.messagebox.showinfo("成功", f"交易配置已更新!\n交易所: {new_exchange.title()}\n保证金: {new_margin}U\n杠杆: {new_leverage}x")
            
        except Exception as e:
            self.log(f"应用交易配置失败: {e}", "ERROR")
            tk.messagebox.showerror("错误", f"配置应用失败: {e}")
    
    def save_trading_config(self):
        """保存交易配置到文件"""
        try:
            import os
            config_dir = "config"
            if not os.path.exists(config_dir):
                os.makedirs(config_dir)
            
            config_file = os.path.join(config_dir, "user_trading_config.txt")
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write(f"# 用户交易配置\n")
                f.write(f"CURRENT_EXCHANGE={self.current_exchange}\n")
                f.write(f"TRADE_AMOUNT={self.trade_amount}\n")
                f.write(f"LEVERAGE={self.leverage}\n")
                f.write(f"# 配置更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            self.log(f"配置已保存到: {config_file}", "SUCCESS")
            
        except Exception as e:
            self.log(f"保存配置失败: {e}", "ERROR")
    
    def load_trading_config(self):
        """加载用户交易配置"""
        try:
            import os
            config_file = os.path.join("config", "user_trading_config.txt")
            
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('CURRENT_EXCHANGE='):
                            self.current_exchange = line.split('=')[1]
                        elif line.startswith('TRADE_AMOUNT='):
                            self.trade_amount = float(line.split('=')[1])
                        elif line.startswith('LEVERAGE='):
                            self.leverage = int(line.split('=')[1])
                
                self.log(f"已加载用户配置: {self.current_exchange.title()}, {self.trade_amount}U/{self.leverage}x", "SUCCESS")
                
        except Exception as e:
            self.log(f"加载用户配置失败: {e}", "WARNING")
    
    def show_exchange_config(self):
        """显示交易所配置窗口"""
        try:
            # 创建配置窗口
            config_window = tk.Toplevel(self.root)
            config_window.title("交易所配置")
            config_window.geometry("600x500")
            config_window.resizable(True, True)
            
            # 使窗口居中
            config_window.transient(self.root)
            config_window.grab_set()
            
            # 主框架
            main_frame = ttk.Frame(config_window, padding=20)
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # 说明信息
            info_frame = ttk.LabelFrame(main_frame, text="说明", padding=10)
            info_frame.pack(fill=tk.X, pady=(0, 15))
            
            info_text = "配置多个交易所的API密钥，程序会根据您在交易配置中选择的交易所进行交易。\n目前支持：Bitget（完整功能），其他交易所（开发中）"
            ttk.Label(info_frame, text=info_text, wraplength=550).pack()
            
            # 创建Notebook用于不同交易所的配置
            notebook = ttk.Notebook(main_frame)
            notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
            
            # Bitget配置页面
            bitget_frame = ttk.Frame(notebook, padding=10)
            notebook.add(bitget_frame, text="Bitget")
            
            self.create_bitget_config_tab(bitget_frame)
            
            # Weex配置页面
            weex_frame = ttk.Frame(notebook, padding=10)
            notebook.add(weex_frame, text="Weex")
            self.create_weex_config_tab(weex_frame)
            
            # 其他交易所配置页面（占位符）
            for exchange_name in ["Binance", "Bybit", "OKEx"]:
                exchange_frame = ttk.Frame(notebook, padding=10)
                notebook.add(exchange_frame, text=exchange_name)
                
                # 占位符内容
                ttk.Label(exchange_frame, 
                         text=f"{exchange_name} 交易所配置功能开发中...\n敬请期待！",
                         font=("Arial", 12)).pack(expand=True)
            
            # 按钮框架
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X)
            
            ttk.Button(button_frame, text="保存配置", 
                      command=lambda: self.save_exchange_config(config_window)).pack(side=tk.RIGHT, padx=(5, 0))
            ttk.Button(button_frame, text="取消", 
                      command=config_window.destroy).pack(side=tk.RIGHT)
            
        except Exception as e:
            self.log(f"显示交易所配置失败: {e}", "ERROR")
    
    def create_bitget_config_tab(self, parent_frame):
        """创建Bitget配置标签页"""
        # 当前配置显示
        current_frame = ttk.LabelFrame(parent_frame, text="当前配置", padding=10)
        current_frame.pack(fill=tk.X, pady=(0, 15))
        
        bitget_status = "已配置" if self.bitget_api_key and self.bitget_secret_key and self.bitget_passphrase else "未配置"
        ttk.Label(current_frame, text=f"状态: {bitget_status}").pack(anchor=tk.W)
        
        # API配置框架
        api_frame = ttk.LabelFrame(parent_frame, text="API配置", padding=10)
        api_frame.pack(fill=tk.X, pady=(0, 15))
        
        # API Key
        api_key_frame = ttk.Frame(api_frame)
        api_key_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(api_key_frame, text="API Key:", width=12).pack(side=tk.LEFT)
        self.bitget_api_key_var = tk.StringVar(value=self.bitget_api_key or "")
        api_key_entry = ttk.Entry(api_key_frame, textvariable=self.bitget_api_key_var, show="*")
        api_key_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(10, 0))
        
        # Secret Key
        secret_frame = ttk.Frame(api_frame)
        secret_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(secret_frame, text="Secret Key:", width=12).pack(side=tk.LEFT)
        self.bitget_secret_var = tk.StringVar(value=self.bitget_secret_key or "")
        secret_entry = ttk.Entry(secret_frame, textvariable=self.bitget_secret_var, show="*")
        secret_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(10, 0))
        
        # Passphrase
        passphrase_frame = ttk.Frame(api_frame)
        passphrase_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(passphrase_frame, text="Passphrase:", width=12).pack(side=tk.LEFT)
        self.bitget_passphrase_var = tk.StringVar(value=self.bitget_passphrase or "")
        passphrase_entry = ttk.Entry(passphrase_frame, textvariable=self.bitget_passphrase_var, show="*")
        passphrase_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(10, 0))
        
        # 沙盒模式
        sandbox_frame = ttk.Frame(api_frame)
        sandbox_frame.pack(fill=tk.X, pady=(5, 0))
        self.bitget_sandbox_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(sandbox_frame, text="沙盒模式（测试环境）", variable=self.bitget_sandbox_var).pack(side=tk.LEFT)
        
        # 测试连接按钮
        test_frame = ttk.Frame(parent_frame)
        test_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(test_frame, text="测试连接", command=self.test_bitget_connection).pack(side=tk.LEFT)
    
    def create_weex_config_tab(self, parent_frame):
        """创建Weex配置标签页"""
        # 当前配置显示
        current_frame = ttk.LabelFrame(parent_frame, text="当前配置", padding=10)
        current_frame.pack(fill=tk.X, pady=(0, 15))
        
        weex_status = "已配置" if self.weex_api_key and self.weex_secret_key else "未配置"
        ttk.Label(current_frame, text=f"状态: {weex_status}").pack(anchor=tk.W)
        
        # API配置框架
        api_frame = ttk.LabelFrame(parent_frame, text="API配置", padding=10)
        api_frame.pack(fill=tk.X, pady=(0, 15))
        
        # API Key
        api_key_frame = ttk.Frame(api_frame)
        api_key_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(api_key_frame, text="API Key:", width=12).pack(side=tk.LEFT)
        self.weex_api_key_var = tk.StringVar(value=self.weex_api_key or "")
        api_key_entry = ttk.Entry(api_key_frame, textvariable=self.weex_api_key_var, show="*")
        api_key_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(10, 0))
        
        # Secret Key
        secret_frame = ttk.Frame(api_frame)
        secret_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(secret_frame, text="Secret Key:", width=12).pack(side=tk.LEFT)
        self.weex_secret_var = tk.StringVar(value=self.weex_secret_key or "")
        secret_entry = ttk.Entry(secret_frame, textvariable=self.weex_secret_var, show="*")
        secret_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(10, 0))
        
        # Passphrase (可选)
        passphrase_frame = ttk.Frame(api_frame)
        passphrase_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(passphrase_frame, text="Passphrase:", width=12).pack(side=tk.LEFT)
        self.weex_passphrase_var = tk.StringVar(value=self.weex_passphrase or "")
        passphrase_entry = ttk.Entry(passphrase_frame, textvariable=self.weex_passphrase_var, show="*")
        passphrase_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(10, 0))
        
        # 说明文字
        info_frame = ttk.Frame(api_frame)
        info_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Label(info_frame, text="注: Passphrase字段可选，根据Weex API要求填写", 
                 font=("Arial", 8), foreground="gray").pack(side=tk.LEFT)
        
        # 沙盒模式
        sandbox_frame = ttk.Frame(api_frame)
        sandbox_frame.pack(fill=tk.X, pady=(5, 0))
        self.weex_sandbox_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(sandbox_frame, text="沙盒模式（测试环境）", variable=self.weex_sandbox_var).pack(side=tk.LEFT)
        
        # 测试连接按钮
        test_frame = ttk.Frame(parent_frame)
        test_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(test_frame, text="测试连接", command=self.test_weex_connection).pack(side=tk.LEFT)
    
    def test_bitget_connection(self):
        """测试Bitget连接"""
        try:
            api_key = self.bitget_api_key_var.get().strip()
            secret_key = self.bitget_secret_var.get().strip()
            passphrase = self.bitget_passphrase_var.get().strip()
            
            if not all([api_key, secret_key, passphrase]):
                tk.messagebox.showerror("错误", "请填写完整的API配置信息")
                return
            
            # 这里可以添加实际的连接测试逻辑
            self.log("正在测试Bitget连接...", "INFO")
            tk.messagebox.showinfo("测试结果", "连接测试功能开发中...")
            
        except Exception as e:
            self.log(f"测试连接失败: {e}", "ERROR")
            tk.messagebox.showerror("错误", f"测试连接失败: {e}")
    
    def test_weex_connection(self):
        """测试Weex连接"""
        try:
            api_key = self.weex_api_key_var.get().strip()
            secret_key = self.weex_secret_var.get().strip()
            passphrase = self.weex_passphrase_var.get().strip()
            
            if not all([api_key, secret_key]):
                tk.messagebox.showerror("错误", "请至少填写API Key和Secret Key")
                return
            
            # 这里可以添加实际的连接测试逻辑
            self.log("正在测试Weex连接...", "INFO")
            tk.messagebox.showinfo("测试结果", "Weex连接测试功能开发中...")
            
        except Exception as e:
            self.log(f"测试Weex连接失败: {e}", "ERROR")
            tk.messagebox.showerror("错误", f"测试连接失败: {e}")
    
    def save_exchange_config(self, window):
        """保存交易所配置"""
        try:
            # 更新Bitget配置
            if hasattr(self, 'bitget_api_key_var'):
                self.bitget_api_key = self.bitget_api_key_var.get().strip()
                self.bitget_secret_key = self.bitget_secret_var.get().strip()
                self.bitget_passphrase = self.bitget_passphrase_var.get().strip()
            
            # 更新Weex配置
            if hasattr(self, 'weex_api_key_var'):
                self.weex_api_key = self.weex_api_key_var.get().strip()
                self.weex_secret_key = self.weex_secret_var.get().strip()
                self.weex_passphrase = self.weex_passphrase_var.get().strip()
            
            # 保存到环境变量文件
            self.save_exchange_config_to_file()
            
            self.log("交易所配置已保存", "SUCCESS")
            window.destroy()
            tk.messagebox.showinfo("成功", "交易所配置已保存！")
            
        except Exception as e:
            self.log(f"保存交易所配置失败: {e}", "ERROR")
            tk.messagebox.showerror("错误", f"保存配置失败: {e}")
    
    def save_exchange_config_to_file(self):
        """保存交易所配置到文件"""
        try:
            import os
            config_dir = "config"
            if not os.path.exists(config_dir):
                os.makedirs(config_dir)
            
            config_file = os.path.join(config_dir, "exchange_config.txt")
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write(f"# 交易所配置文件\n")
                f.write(f"# Bitget配置\n")
                f.write(f"BITGET_API_KEY={self.bitget_api_key or ''}\n")
                f.write(f"BITGET_SECRET_KEY={self.bitget_secret_key or ''}\n")
                f.write(f"BITGET_PASSPHRASE={self.bitget_passphrase or ''}\n")
                f.write(f"\n# Weex配置\n")
                f.write(f"WEEX_API_KEY={self.weex_api_key or ''}\n")
                f.write(f"WEEX_SECRET_KEY={self.weex_secret_key or ''}\n")
                f.write(f"WEEX_PASSPHRASE={self.weex_passphrase or ''}\n")
                f.write(f"\n# 配置更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            self.log(f"交易所配置已保存到: {config_file}", "SUCCESS")
            
        except Exception as e:
            self.log(f"保存交易所配置失败: {e}", "ERROR")


def main():
    """主函数"""
    try:
        print("启动抗干扰版GUI交易机器人...")
        print("正在创建主窗口...")
        
        root = tk.Tk()
        print("主窗口已创建")
        
        print("正在初始化应用程序...")
        app = TradingBotGUI(root)
        print("应用程序初始化完成")
        
        def on_closing():
            try:
                if hasattr(app, 'log_text') and app.log_text.winfo_exists():
                    app.log("用户请求关闭程序", "WARNING")
            except:
                print("用户请求关闭程序")
            
            if app.running:
                app.stop_bot()
            app.shutdown_requested = True
            root.destroy()
        
        root.protocol("WM_DELETE_WINDOW", on_closing)
        
        print("程序已启动，GUI窗口应该已显示")
        print("程序具有抗干扰功能，需要连续3次中断信号才会退出")
        print("窗口标题: Telegram交易跟单机器人 v1.0")
        print("窗口大小: 800x600")
        
        # 确保窗口显示在前台
        root.lift()
        root.attributes('-topmost', True)
        root.after_idle(lambda: root.attributes('-topmost', False))
        
        print("开始GUI主循环...")
        root.mainloop()
        
        print("程序正常退出")
        
    except Exception as e:
        print(f"程序出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
