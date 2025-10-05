#!/usr/bin/env python3
"""
修复版GUI交易机器人
解决界面显示和稳定性问题
"""

import os
import sys
import asyncio
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from pathlib import Path
from datetime import datetime
import re
import queue
import time

sys.path.insert(0, str(Path(__file__).parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class TradingBotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Telegram交易跟单机器人 v1.0")
        self.root.geometry("900x700")
        
        # 状态变量
        self.running = False
        self.telegram_client = None
        self.target_channel = None
        self.trade_count = 0
        
        # 配置
        self.api_id = os.getenv('TELEGRAM_API_ID')
        self.api_hash = os.getenv('TELEGRAM_API_HASH')
        self.trade_amount = float(os.getenv('DEFAULT_TRADE_AMOUNT', '2.0'))
        self.leverage = int(os.getenv('DEFAULT_LEVERAGE', '20'))
        
        # 日志队列
        self.log_queue = queue.Queue()
        
        self.setup_ui()
        self.start_log_updater()
        
    def setup_ui(self):
        """设置用户界面"""
        try:
            # 设置样式
            style = ttk.Style()
            style.theme_use('clam')
            
            # 主框架
            main_frame = ttk.Frame(self.root)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # 标题
            title_label = ttk.Label(main_frame, text="Telegram交易跟单机器人", font=('Arial', 16, 'bold'))
            title_label.pack(pady=(0, 10))
            
            # 状态框架
            status_frame = ttk.LabelFrame(main_frame, text="系统状态", padding=10)
            status_frame.pack(fill=tk.X, pady=(0, 10))
            
            # 状态网格
            status_grid = ttk.Frame(status_frame)
            status_grid.pack(fill=tk.X)
            
            # 第一行状态
            row1 = ttk.Frame(status_grid)
            row1.pack(fill=tk.X, pady=2)
            
            ttk.Label(row1, text="连接状态:", font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
            self.status_label = ttk.Label(row1, text="未连接", foreground='red')
            self.status_label.pack(side=tk.LEFT, padx=(10, 0))
            
            # 第二行状态
            row2 = ttk.Frame(status_grid)
            row2.pack(fill=tk.X, pady=2)
            
            ttk.Label(row2, text="监控频道:", font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
            self.channel_label = ttk.Label(row2, text="未连接")
            self.channel_label.pack(side=tk.LEFT, padx=(10, 0))
            
            # 第三行状态
            row3 = ttk.Frame(status_grid)
            row3.pack(fill=tk.X, pady=2)
            
            ttk.Label(row3, text="交易次数:", font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
            self.trade_count_label = ttk.Label(row3, text="0")
            self.trade_count_label.pack(side=tk.LEFT, padx=(10, 0))
            
            # 配置框架
            config_frame = ttk.LabelFrame(main_frame, text="交易配置", padding=10)
            config_frame.pack(fill=tk.X, pady=(0, 10))
            
            config_text = f"交易金额: {self.trade_amount}U  |  杠杆: {self.leverage}x  |  模式: 市价单"
            ttk.Label(config_frame, text=config_text, font=('Arial', 10)).pack()
            
            # 控制按钮框架
            control_frame = ttk.Frame(main_frame)
            control_frame.pack(fill=tk.X, pady=(0, 10))
            
            self.start_button = ttk.Button(control_frame, text="启动机器人", command=self.start_bot)
            self.start_button.pack(side=tk.LEFT, padx=(0, 10))
            
            self.stop_button = ttk.Button(control_frame, text="停止机器人", command=self.stop_bot, state=tk.DISABLED)
            self.stop_button.pack(side=tk.LEFT, padx=(0, 10))
            
            self.test_button = ttk.Button(control_frame, text="测试信号", command=self.test_signal)
            self.test_button.pack(side=tk.LEFT, padx=(0, 10))
            
            self.clear_button = ttk.Button(control_frame, text="清空日志", command=self.clear_logs)
            self.clear_button.pack(side=tk.LEFT)
            
            # 日志框架
            log_frame = ttk.LabelFrame(main_frame, text="实时日志", padding=5)
            log_frame.pack(fill=tk.BOTH, expand=True)
            
            # 创建日志文本框和滚动条
            log_container = ttk.Frame(log_frame)
            log_container.pack(fill=tk.BOTH, expand=True)
            
            # 日志文本框
            self.log_text = tk.Text(log_container, height=20, bg='#1a1a1a', fg='#00ff00', 
                                   font=('Consolas', 9), wrap=tk.WORD, state=tk.DISABLED)
            
            # 滚动条
            scrollbar = ttk.Scrollbar(log_container, orient=tk.VERTICAL, command=self.log_text.yview)
            self.log_text.configure(yscrollcommand=scrollbar.set)
            
            # 打包
            self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # 初始日志
            self.add_log("交易机器人界面已启动")
            self.add_log(f"配置: {self.trade_amount}U, {self.leverage}x杠杆")
            self.add_log("点击'启动机器人'开始监控")
            
        except Exception as e:
            messagebox.showerror("界面错误", f"创建界面时出错: {e}")
            print(f"UI setup error: {e}")
    
    def start_log_updater(self):
        """启动日志更新器"""
        def update_logs():
            try:
                while True:
                    try:
                        log_entry = self.log_queue.get_nowait()
                        self.insert_log_text(log_entry['message'], log_entry['level'])
                    except queue.Empty:
                        break
                
                # 更新状态显示
                self.update_status_display()
                
            except Exception as e:
                print(f"Log update error: {e}")
            
            # 每100ms检查一次
            self.root.after(100, update_logs)
        
        update_logs()
    
    def insert_log_text(self, message, level="INFO"):
        """插入日志文本"""
        try:
            timestamp = datetime.now().strftime('%H:%M:%S')
            
            # 颜色映射
            colors = {
                "INFO": "#00ff00",
                "SUCCESS": "#00ff88", 
                "ERROR": "#ff4444",
                "WARNING": "#ffff00",
                "TRADE": "#00ffff"
            }
            
            color = colors.get(level, "#00ff00")
            
            # 启用文本框编辑
            self.log_text.config(state=tk.NORMAL)
            
            # 插入文本
            log_line = f"[{timestamp}] {message}\n"
            self.log_text.insert(tk.END, log_line)
            
            # 限制日志行数
            lines = self.log_text.get('1.0', tk.END).split('\n')
            if len(lines) > 1000:
                # 删除前面的行
                self.log_text.delete('1.0', f'{len(lines)-500}.0')
            
            # 滚动到底部
            self.log_text.see(tk.END)
            
            # 禁用文本框编辑
            self.log_text.config(state=tk.DISABLED)
            
        except Exception as e:
            print(f"Insert log error: {e}")
    
    def add_log(self, message, level="INFO"):
        """添加日志"""
        try:
            log_entry = {
                'message': message,
                'level': level,
                'time': datetime.now()
            }
            self.log_queue.put(log_entry)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        except Exception as e:
            print(f"Add log error: {e}")
    
    def update_status_display(self):
        """更新状态显示"""
        try:
            if self.running:
                self.status_label.config(text="已连接并监控中", foreground='green')
                if self.target_channel:
                    channel_name = getattr(self.target_channel, 'title', '未知频道')
                    self.channel_label.config(text=channel_name)
            else:
                self.status_label.config(text="未连接", foreground='red')
                self.channel_label.config(text="未连接")
            
            self.trade_count_label.config(text=str(self.trade_count))
        except Exception as e:
            print(f"Status update error: {e}")
    
    def start_bot(self):
        """启动机器人"""
        if self.running:
            return
            
        self.add_log("正在启动机器人...")
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        # 在新线程中运行
        threading.Thread(target=self.run_async_bot, daemon=True).start()
        
    def run_async_bot(self):
        """在新线程中运行异步机器人"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(self.async_start_bot())
        except Exception as e:
            self.add_log(f"机器人运行出错: {e}", "ERROR")
        finally:
            loop.close()
            self.running = False
            self.root.after(0, self.reset_buttons)
            
    def reset_buttons(self):
        """重置按钮状态"""
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
            
    async def async_start_bot(self):
        """异步启动机器人"""
        try:
            from telethon import TelegramClient, events
            
            # 连接Telegram
            self.add_log("连接Telegram服务器...")
            self.telegram_client = TelegramClient('trading_session', self.api_id, self.api_hash)
            await self.telegram_client.connect()
            
            if not await self.telegram_client.is_user_authorized():
                self.add_log("未认证，请先运行认证程序", "ERROR")
                return
                
            self.add_log("Telegram连接成功", "SUCCESS")
            
            # 查找频道
            self.add_log("查找目标频道...")
            
            async for dialog in self.telegram_client.iter_dialogs():
                if dialog.is_channel and 'Seven' in dialog.title and ('司' in dialog.title or 'VIP' in dialog.title):
                    self.target_channel = dialog.entity
                    break
                    
            if not self.target_channel:
                self.add_log("未找到目标频道", "ERROR")
                return
                
            channel_name = getattr(self.target_channel, 'title', '未知频道')
            self.add_log(f"找到频道: {channel_name}", "SUCCESS")
            
            # 注册消息处理器
            @self.telegram_client.on(events.NewMessage(chats=self.target_channel))
            async def handle_message(event):
                await self.handle_new_message(event)
                
            self.running = True
            self.add_log("开始监控频道消息...", "SUCCESS")
            self.add_log("等待交易信号 (#币种 市價多/空)")
            
            # 保持运行
            await self.telegram_client.run_until_disconnected()
            
        except Exception as e:
            self.add_log(f"启动失败: {e}", "ERROR")
        finally:
            self.running = False
            
    async def handle_new_message(self, event):
        """处理新消息"""
        try:
            message = event.message
            if not message.text:
                return
                
            sender = await message.get_sender()
            sender_name = getattr(sender, 'first_name', 'Unknown') if sender else 'Unknown'
            
            self.add_log(f"[{sender_name}]: {message.text}")
            
            # 解析信号
            signal = self.parse_signal(message.text)
            
            if signal:
                self.add_log("检测到交易信号!", "SUCCESS")
                await self.execute_trade(signal)
                
        except Exception as e:
            self.add_log(f"处理消息失败: {e}", "ERROR")
            
    def parse_signal(self, message):
        """解析交易信号"""
        if not message:
            return None
            
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
            self.trade_count += 1
            
            self.add_log("=" * 30, "TRADE")
            self.add_log(f"执行交易 #{self.trade_count}", "TRADE")
            self.add_log(f"币种: {signal['symbol']}", "TRADE")
            self.add_log(f"方向: {signal['direction_cn']}", "TRADE") 
            self.add_log(f"金额: {signal['amount']}U", "TRADE")
            self.add_log(f"杠杆: {signal['leverage']}x", "TRADE")
            
            if signal['stop_loss']:
                self.add_log(f"止损: {signal['stop_loss']}", "TRADE")
                
            if signal['take_profit']:
                self.add_log(f"止盈: {signal['take_profit']}", "TRADE")
                
            # 模拟交易执行
            self.add_log("模拟交易执行成功", "SUCCESS")
            self.add_log("=" * 30, "TRADE")
            
        except Exception as e:
            self.add_log(f"交易执行失败: {e}", "ERROR")
            
    def stop_bot(self):
        """停止机器人"""
        if not self.running:
            return
            
        self.add_log("正在停止机器人...", "WARNING")
        
        if self.telegram_client:
            threading.Thread(target=self.async_stop, daemon=True).start()
            
        self.running = False
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
            
        self.add_log("机器人已停止", "SUCCESS")
        
    def test_signal(self):
        """测试信号解析"""
        test_signals = [
            "#BTC 市價多",
            "#ETH 市價空 止损2800 第一止盈2500",
            "#SOL 市價多 第一止盈180"
        ]
        
        self.add_log("开始测试信号解析...", "WARNING")
        
        for signal_text in test_signals:
            self.add_log(f"测试: {signal_text}")
            signal = self.parse_signal(signal_text)
            
            if signal:
                self.add_log(f"解析成功: {signal['symbol']} {signal['direction_cn']}")
            else:
                self.add_log("解析失败")
                
        self.add_log("测试完成", "SUCCESS")
    
    def clear_logs(self):
        """清空日志"""
        try:
            self.log_text.config(state=tk.NORMAL)
            self.log_text.delete('1.0', tk.END)
            self.log_text.config(state=tk.DISABLED)
            self.add_log("日志已清空")
        except Exception as e:
            print(f"Clear logs error: {e}")


def main():
    """主函数"""
    try:
        root = tk.Tk()
        app = TradingBotGUI(root)
        
        # 设置窗口关闭事件
        def on_closing():
            if app.running:
                app.stop_bot()
                time.sleep(1)
            root.destroy()
        
        root.protocol("WM_DELETE_WINDOW", on_closing)
        
        # 启动主循环
        root.mainloop()
        
    except Exception as e:
        print(f"程序启动错误: {e}")
        messagebox.showerror("启动错误", f"程序启动失败: {e}")


if __name__ == "__main__":
    main()
