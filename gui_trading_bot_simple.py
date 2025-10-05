#!/usr/bin/env python3
"""
简化版GUI交易机器人
移除复杂的异步功能，专注于基本的GUI和信号解析
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from datetime import datetime
import re

sys.path.insert(0, str(Path(__file__).parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class SimpleTradingBotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Telegram交易跟单机器人 v1.0")
        self.root.geometry("800x600")
        
        # 状态变量
        self.running = False
        self.trade_count = 0
        
        # 配置
        self.trade_amount = float(os.getenv('DEFAULT_TRADE_AMOUNT', '2.0'))
        self.leverage = int(os.getenv('DEFAULT_LEVERAGE', '20'))
        
        self.setup_ui()
        
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
        
        self.status_label = ttk.Label(status_frame, text="未连接", font=('Arial', 12))
        self.status_label.pack(anchor=tk.W)
        
        self.channel_label = ttk.Label(status_frame, text="频道: 未连接")
        self.channel_label.pack(anchor=tk.W)
        
        self.trade_count_label = ttk.Label(status_frame, text="交易次数: 0")
        self.trade_count_label.pack(anchor=tk.W)
        
        # 配置框架
        config_frame = ttk.LabelFrame(main_frame, text="交易配置", padding=10)
        config_frame.pack(fill=tk.X, pady=(0, 10))
        
        config_text = f"交易金额: {self.trade_amount}U  |  杠杆: {self.leverage}x  |  模式: 市价单"
        ttk.Label(config_frame, text=config_text).pack()
        
        # 控制按钮
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.start_button = ttk.Button(control_frame, text="启动机器人", command=self.start_bot)
        self.start_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.stop_button = ttk.Button(control_frame, text="停止机器人", command=self.stop_bot, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.test_button = ttk.Button(control_frame, text="测试信号", command=self.test_signal)
        self.test_button.pack(side=tk.LEFT)
        
        # 日志框架
        log_frame = ttk.LabelFrame(main_frame, text="实时日志", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        # 简单的日志文本框
        log_container = ttk.Frame(log_frame)
        log_container.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = tk.Text(log_container, height=20, wrap=tk.WORD, state=tk.DISABLED)
        
        scrollbar = ttk.Scrollbar(log_container, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 初始日志
        self.log("交易机器人界面已启动")
        self.log(f"配置: {self.trade_amount}U, {self.leverage}x杠杆")
        self.log("点击'启动机器人'开始监控")
        
    def log(self, message, level="INFO"):
        """添加日志"""
        try:
            timestamp = datetime.now().strftime('%H:%M:%S')
            
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
            
            self.root.update_idletasks()
            
        except Exception as e:
            print(f"日志错误: {e}")
    
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
        """启动机器人（简化版）"""
        if self.running:
            return
            
        self.log("正在启动机器人...")
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        # 简化版启动 - 不实际连接Telegram
        self.running = True
        self.update_status(True, "模拟频道")
        self.log("机器人已启动（模拟模式）", "SUCCESS")
        self.log("在实际使用时，这里会连接到Telegram群组")
        
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
        
        self.log("开始测试信号解析...", "WARNING")
        
        # 使用修复后的正则表达式
        pattern = r'#(\w+)\s+市[價price]([多空])(?:\s+(\d+(?:\.\d+)?)\s*[Uu](?:SDT)?)?(?:.*?止[损損][:：]?\s*(\d+(?:\.\d+)?))?(?:.*?目[标標][:：]?\s*(\d+(?:\.\d+)?))?'
        compiled_pattern = re.compile(pattern, re.IGNORECASE)
        
        for signal_text in test_signals:
            self.log(f"测试: {signal_text}")
            
            match = compiled_pattern.search(signal_text)
            if match:
                symbol, direction, amount, stop_loss, take_profit = match.groups()
                direction_cn = "做多" if direction == "多" else "做空"
                
                self.log(f"  解析成功: {symbol} {direction_cn}")
                if amount:
                    self.log(f"  金额: {amount}U")
                if stop_loss:
                    self.log(f"  止损: {stop_loss}")
                if take_profit:
                    self.log(f"  目标: {take_profit}")
                    
                # 模拟交易计数
                self.trade_count += 1
                self.update_status(self.running, "模拟频道")
                
            else:
                self.log("  解析失败")
        
        self.log("信号解析测试完成", "SUCCESS")


def main():
    """主函数"""
    try:
        root = tk.Tk()
        app = SimpleTradingBotGUI(root)
        
        def on_closing():
            if app.running:
                app.stop_bot()
            root.destroy()
        
        root.protocol("WM_DELETE_WINDOW", on_closing)
        
        root.mainloop()
        
    except KeyboardInterrupt:
        print("程序被中断")
    except Exception as e:
        print(f"程序出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
