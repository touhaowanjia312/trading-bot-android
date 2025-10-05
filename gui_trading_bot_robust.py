#!/usr/bin/env python3
"""
抗干扰版GUI交易机器人
能够处理自动SIGINT信号的稳定版本
"""

import os
import sys
import signal
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from datetime import datetime
import re
import threading
import time

sys.path.insert(0, str(Path(__file__).parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class RobustTradingBotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Telegram交易跟单机器人 v1.0 (抗干扰版)")
        self.root.geometry("800x600")
        
        # 状态变量
        self.running = False
        self.trade_count = 0
        self.shutdown_requested = False
        
        # 配置
        self.trade_amount = float(os.getenv('DEFAULT_TRADE_AMOUNT', '2.0'))
        self.leverage = int(os.getenv('DEFAULT_LEVERAGE', '20'))
        
        # 设置信号处理 - 忽略自动SIGINT
        self.setup_signal_handlers()
        
        self.setup_ui()
        
        # 启动信号监控线程
        self.start_signal_monitor()
        
    def setup_signal_handlers(self):
        """设置信号处理器"""
        def robust_signal_handler(signum, frame):
            self.log(f"收到信号 {signum}，但程序继续运行", "WARNING")
            
            # 只有连续收到3次信号才真正退出
            if not hasattr(self, 'signal_count'):
                self.signal_count = 0
            
            self.signal_count += 1
            
            if self.signal_count >= 3:
                self.log("收到连续3次中断信号，准备退出", "ERROR")
                self.shutdown_requested = True
                self.root.quit()
            else:
                self.log(f"忽略第{self.signal_count}次中断信号", "WARNING")
        
        # 设置SIGINT处理器
        signal.signal(signal.SIGINT, robust_signal_handler)
        
        # 如果有SIGBREAK（Windows），也处理它
        if hasattr(signal, 'SIGBREAK'):
            signal.signal(signal.SIGBREAK, robust_signal_handler)
    
    def start_signal_monitor(self):
        """启动信号监控线程"""
        def monitor_signals():
            while not self.shutdown_requested:
                try:
                    time.sleep(1)
                    # 重置信号计数器（如果长时间没有信号）
                    if hasattr(self, 'signal_count') and self.signal_count > 0:
                        if hasattr(self, 'last_signal_time'):
                            if time.time() - self.last_signal_time > 10:  # 10秒后重置
                                self.signal_count = 0
                        else:
                            self.last_signal_time = time.time()
                except:
                    break
        
        monitor_thread = threading.Thread(target=monitor_signals, daemon=True)
        monitor_thread.start()
        
    def setup_ui(self):
        """设置用户界面"""
        # 主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 标题
        title_label = ttk.Label(main_frame, text="Telegram交易跟单机器人 (抗干扰版)", font=('Arial', 16, 'bold'))
        title_label.pack(pady=(0, 10))
        
        # 状态框架
        status_frame = ttk.LabelFrame(main_frame, text="系统状态", padding=10)
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.status_label = ttk.Label(status_frame, text="未连接", font=('Arial', 12))
        self.status_label.pack(anchor=tk.W)
        
        self.channel_label = ttk.Label(status_frame, text="频道: 未连接")
        self.channel_label.pack(anchor=tk.W)
        
        self.trade_count_label = ttk.Label(status_frame, text="交易次数: 0")
        self.trade_count_label.pack(anchor=tk.W)
        
        self.signal_count_label = ttk.Label(status_frame, text="中断信号: 0", fg="red")
        self.signal_count_label.pack(anchor=tk.W)
        
        # 配置框架
        config_frame = ttk.LabelFrame(main_frame, text="交易配置", padding=10)
        config_frame.pack(fill=tk.X, pady=(0, 10))
        
        config_text = f"交易金额: {self.trade_amount}U  |  杠杆: {self.leverage}x  |  模式: 市价单  |  抗干扰: 启用"
        ttk.Label(config_frame, text=config_text).pack()
        
        # 控制按钮
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.start_button = ttk.Button(control_frame, text="启动机器人", command=self.start_bot)
        self.start_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.stop_button = ttk.Button(control_frame, text="停止机器人", command=self.stop_bot, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.test_button = ttk.Button(control_frame, text="测试信号", command=self.test_signal)
        self.test_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.reset_button = ttk.Button(control_frame, text="重置信号计数", command=self.reset_signal_count)
        self.reset_button.pack(side=tk.LEFT)
        
        # 日志框架
        log_frame = ttk.LabelFrame(main_frame, text="实时日志", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        # 日志文本框
        log_container = ttk.Frame(log_frame)
        log_container.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = tk.Text(log_container, height=20, wrap=tk.WORD, state=tk.DISABLED)
        
        scrollbar = ttk.Scrollbar(log_container, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 初始日志
        self.log("抗干扰版交易机器人已启动")
        self.log(f"配置: {self.trade_amount}U, {self.leverage}x杠杆")
        self.log("系统已启用信号干扰防护")
        self.log("连续3次中断信号才会退出程序")
        
        # 启动状态更新定时器
        self.update_status_display()
        
    def log(self, message, level="INFO"):
        """添加日志"""
        try:
            timestamp = datetime.now().strftime('%H:%M:%S')
            
            # 颜色配置
            colors = {
                "INFO": "black",
                "SUCCESS": "green", 
                "WARNING": "orange",
                "ERROR": "red",
                "TRADE": "blue"
            }
            
            color = colors.get(level, "black")
            
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
            
            # 限制日志行数
            lines = self.log_text.get('1.0', tk.END).split('\n')
            if len(lines) > 500:
                self.log_text.delete('1.0', f'{len(lines)-400}.0')
            
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
            
            if hasattr(self.root, 'update_idletasks'):
                self.root.update_idletasks()
            
        except Exception as e:
            print(f"日志错误: {e}")
    
    def update_status_display(self):
        """更新状态显示"""
        try:
            if hasattr(self, 'signal_count'):
                self.signal_count_label.config(text=f"中断信号: {self.signal_count}")
            
            # 每秒更新一次
            if not self.shutdown_requested:
                self.root.after(1000, self.update_status_display)
                
        except Exception as e:
            print(f"状态更新错误: {e}")
    
    def reset_signal_count(self):
        """重置信号计数"""
        self.signal_count = 0
        self.log("信号计数已重置", "SUCCESS")
    
    def update_status(self, connected=False, channel_name="未连接"):
        """更新状态显示"""
        try:
            if connected:
                self.status_label.config(text="已连接")
                self.channel_label.config(text=f"频道: {channel_name}")
            else:
                self.status_label.config(text="未连接")
                self.channel_label.config(text="频道: 未连接")
                
            self.trade_count_label.config(text=f"交易次数: {self.trade_count}")
            
        except Exception as e:
            print(f"状态更新错误: {e}")
    
    def start_bot(self):
        """启动机器人"""
        if self.running:
            return
            
        self.log("正在启动机器人...")
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        self.running = True
        self.update_status(True, "模拟频道 (抗干扰模式)")
        self.log("机器人已启动 (抗干扰模式)", "SUCCESS")
        
    def stop_bot(self):
        """停止机器人"""
        if not self.running:
            return
            
        self.log("正在停止机器人...")
        
        self.running = False
        self.update_status(False)
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        
        self.log("机器人已停止", "SUCCESS")
        
    def test_signal(self):
        """测试信号解析"""
        test_signals = [
            "#BTC 市價多",
            "#ETH 市價空 50U 止损 3500 目标 3000",
            "#WLFI 市價空",
            "#BTC 市價多 100U 止損 45000 目標 50000"
        ]
        
        self.log("开始测试繁体字信号解析...", "WARNING")
        
        # 使用修复后的正则表达式
        pattern = r'#(\w+)\s+市[價price]([多空])(?:\s+(\d+(?:\.\d+)?)\s*[Uu](?:SDT)?)?(?:.*?止[损損][:：]?\s*(\d+(?:\.\d+)?))?(?:.*?目[标標][:：]?\s*(\d+(?:\.\d+)?))?'
        compiled_pattern = re.compile(pattern, re.IGNORECASE)
        
        for signal_text in test_signals:
            self.log(f"测试: {signal_text}")
            
            match = compiled_pattern.search(signal_text)
            if match:
                symbol, direction, amount, stop_loss, take_profit = match.groups()
                direction_cn = "做多" if direction == "多" else "做空"
                
                self.log(f"  解析成功: {symbol} {direction_cn}", "SUCCESS")
                if amount:
                    self.log(f"  金额: {amount}U")
                if stop_loss:
                    self.log(f"  止损: {stop_loss}")
                if take_profit:
                    self.log(f"  目标: {take_profit}")
                    
                self.trade_count += 1
                self.update_status(self.running, "模拟频道")
                
            else:
                self.log("  解析失败", "ERROR")
        
        self.log("繁体字信号解析测试完成", "SUCCESS")


def main():
    """主函数"""
    try:
        print("启动抗干扰版GUI交易机器人...")
        
        root = tk.Tk()
        app = RobustTradingBotGUI(root)
        
        def on_closing():
            app.log("用户请求关闭程序", "WARNING")
            if app.running:
                app.stop_bot()
            app.shutdown_requested = True
            root.destroy()
        
        root.protocol("WM_DELETE_WINDOW", on_closing)
        
        print("程序已启动，GUI窗口应该已显示")
        print("程序具有抗干扰功能，需要连续3次中断信号才会退出")
        
        root.mainloop()
        
        print("程序正常退出")
        
    except Exception as e:
        print(f"程序出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
