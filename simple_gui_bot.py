#!/usr/bin/env python3
"""
最简化的GUI交易机器人
专注于稳定性和可靠性
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import asyncio
from pathlib import Path
from datetime import datetime
import re
import time

sys.path.insert(0, str(Path(__file__).parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class SimpleTradingBot:
    def __init__(self):
        print("初始化交易机器人...")
        
        # 创建主窗口
        self.root = tk.Tk()
        self.root.title("Telegram交易跟单机器人")
        self.root.geometry("800x600")
        
        # 防止窗口被意外关闭
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 状态变量
        self.running = False
        self.connected = False
        self.trade_count = 0
        
        # 配置
        self.api_id = os.getenv('TELEGRAM_API_ID', 'NOT_SET')
        self.api_hash = os.getenv('TELEGRAM_API_HASH', 'NOT_SET')
        self.trade_amount = float(os.getenv('DEFAULT_TRADE_AMOUNT', '2.0'))
        self.leverage = int(os.getenv('DEFAULT_LEVERAGE', '20'))
        
        print(f"配置加载: API_ID={self.api_id[:10]}..., 金额={self.trade_amount}U")
        
        self.setup_ui()
        print("界面创建完成")
        
    def setup_ui(self):
        """创建界面"""
        try:
            # 主容器
            main_frame = tk.Frame(self.root, bg='white')
            main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
            
            # 标题
            title_label = tk.Label(main_frame, text="Telegram交易跟单机器人", 
                                 font=('Arial', 18, 'bold'), bg='white', fg='#2c3e50')
            title_label.pack(pady=(0, 20))
            
            # 状态区域
            status_frame = tk.LabelFrame(main_frame, text="系统状态", 
                                       font=('Arial', 12, 'bold'), bg='white', padx=10, pady=10)
            status_frame.pack(fill=tk.X, pady=(0, 20))
            
            # 连接状态
            self.status_text = tk.Label(status_frame, text="状态: 未连接", 
                                      font=('Arial', 11), bg='white', fg='red')
            self.status_text.pack(anchor=tk.W, pady=2)
            
            # 频道信息
            self.channel_text = tk.Label(status_frame, text="频道: 未连接", 
                                       font=('Arial', 11), bg='white')
            self.channel_text.pack(anchor=tk.W, pady=2)
            
            # 交易次数
            self.trade_text = tk.Label(status_frame, text="交易次数: 0", 
                                     font=('Arial', 11), bg='white')
            self.trade_text.pack(anchor=tk.W, pady=2)
            
            # 配置信息
            config_frame = tk.LabelFrame(main_frame, text="交易配置", 
                                       font=('Arial', 12, 'bold'), bg='white', padx=10, pady=10)
            config_frame.pack(fill=tk.X, pady=(0, 20))
            
            config_info = tk.Label(config_frame, 
                                 text=f"金额: {self.trade_amount}U  |  杠杆: {self.leverage}x  |  模式: 市价单",
                                 font=('Arial', 11), bg='white')
            config_info.pack(pady=5)
            
            # 控制按钮区域
            button_frame = tk.Frame(main_frame, bg='white')
            button_frame.pack(fill=tk.X, pady=(0, 20))
            
            # 启动按钮
            self.start_btn = tk.Button(button_frame, text="启动机器人", 
                                     command=self.start_bot, bg='#27ae60', fg='white',
                                     font=('Arial', 12, 'bold'), padx=20, pady=10)
            self.start_btn.pack(side=tk.LEFT, padx=(0, 10))
            
            # 停止按钮
            self.stop_btn = tk.Button(button_frame, text="停止机器人", 
                                    command=self.stop_bot, bg='#e74c3c', fg='white',
                                    font=('Arial', 12, 'bold'), padx=20, pady=10, state=tk.DISABLED)
            self.stop_btn.pack(side=tk.LEFT, padx=(0, 10))
            
            # 测试按钮
            self.test_btn = tk.Button(button_frame, text="测试信号", 
                                    command=self.test_signal, bg='#f39c12', fg='white',
                                    font=('Arial', 12, 'bold'), padx=20, pady=10)
            self.test_btn.pack(side=tk.LEFT)
            
            # 日志区域
            log_frame = tk.LabelFrame(main_frame, text="运行日志", 
                                    font=('Arial', 12, 'bold'), bg='white', padx=5, pady=5)
            log_frame.pack(fill=tk.BOTH, expand=True)
            
            # 创建文本区域和滚动条
            text_frame = tk.Frame(log_frame, bg='white')
            text_frame.pack(fill=tk.BOTH, expand=True)
            
            # 日志文本框
            self.log_text = tk.Text(text_frame, bg='#2c3e50', fg='#ecf0f1', 
                                  font=('Consolas', 10), wrap=tk.WORD, state=tk.DISABLED)
            self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            # 滚动条
            scrollbar = tk.Scrollbar(text_frame, command=self.log_text.yview)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            self.log_text.config(yscrollcommand=scrollbar.set)
            
            # 添加初始日志
            self.add_log("交易机器人界面已启动")
            self.add_log(f"配置: {self.trade_amount}U, {self.leverage}x杠杆")
            self.add_log("点击'启动机器人'开始监控")
            
            print("界面组件创建完成")
            
        except Exception as e:
            print(f"创建界面时出错: {e}")
            messagebox.showerror("界面错误", f"创建界面失败: {e}")
    
    def add_log(self, message, level="INFO"):
        """添加日志"""
        try:
            timestamp = datetime.now().strftime('%H:%M:%S')
            log_message = f"[{timestamp}] {message}\n"
            
            # 启用文本编辑
            self.log_text.config(state=tk.NORMAL)
            
            # 添加文本
            self.log_text.insert(tk.END, log_message)
            
            # 滚动到底部
            self.log_text.see(tk.END)
            
            # 禁用文本编辑
            self.log_text.config(state=tk.DISABLED)
            
            # 控制台也输出
            print(f"[{timestamp}] {message}")
            
        except Exception as e:
            print(f"添加日志时出错: {e}")
    
    def update_status(self):
        """更新状态显示"""
        try:
            if self.connected:
                self.status_text.config(text="状态: 已连接监控中", fg='green')
                self.channel_text.config(text="频道: Seven的手工壽司鋪（VIP）")
            else:
                self.status_text.config(text="状态: 未连接", fg='red')
                self.channel_text.config(text="频道: 未连接")
            
            self.trade_text.config(text=f"交易次数: {self.trade_count}")
            
        except Exception as e:
            print(f"更新状态时出错: {e}")
    
    def start_bot(self):
        """启动机器人"""
        if self.running:
            return
        
        try:
            self.add_log("正在启动机器人...")
            
            # 检查配置
            if self.api_id == 'NOT_SET' or self.api_hash == 'NOT_SET':
                self.add_log("错误: API配置未设置", "ERROR")
                messagebox.showerror("配置错误", "请先配置Telegram API信息")
                return
            
            # 更新按钮状态
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            
            # 在新线程中启动
            threading.Thread(target=self.run_bot_thread, daemon=True).start()
            
        except Exception as e:
            self.add_log(f"启动失败: {e}", "ERROR")
            print(f"启动机器人时出错: {e}")
    
    def run_bot_thread(self):
        """在线程中运行机器人"""
        try:
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 运行异步代码
            loop.run_until_complete(self.async_run_bot())
            
        except Exception as e:
            self.add_log(f"机器人运行错误: {e}", "ERROR")
        finally:
            # 重置状态
            self.running = False
            self.connected = False
            self.root.after(0, self.reset_buttons)
    
    async def async_run_bot(self):
        """异步运行机器人"""
        try:
            from telethon import TelegramClient, events
            
            self.add_log("连接Telegram服务器...")
            
            # 创建客户端
            client = TelegramClient('trading_session', self.api_id, self.api_hash)
            await client.connect()
            
            # 检查认证
            if not await client.is_user_authorized():
                self.add_log("未认证，请先运行认证", "ERROR")
                return
            
            self.add_log("Telegram连接成功", "SUCCESS")
            self.connected = True
            self.root.after(0, self.update_status)
            
            # 查找频道
            target_channel = None
            async for dialog in client.iter_dialogs():
                if dialog.is_channel and 'Seven' in dialog.title and '司' in dialog.title:
                    target_channel = dialog.entity
                    break
            
            if not target_channel:
                self.add_log("未找到目标频道", "ERROR")
                return
            
            self.add_log("找到频道: Seven的手工壽司鋪", "SUCCESS")
            
            # 注册消息处理
            @client.on(events.NewMessage(chats=target_channel))
            async def handle_message(event):
                await self.handle_message(event)
            
            self.running = True
            self.add_log("开始监控频道消息...", "SUCCESS")
            self.add_log("等待交易信号...")
            
            # 保持运行
            await client.run_until_disconnected()
            
        except Exception as e:
            self.add_log(f"运行出错: {e}", "ERROR")
    
    async def handle_message(self, event):
        """处理消息"""
        try:
            message = event.message
            if not message.text:
                return
            
            sender = await message.get_sender()
            sender_name = getattr(sender, 'first_name', 'Unknown') if sender else 'Unknown'
            
            self.add_log(f"收到消息 [{sender_name}]: {message.text}")
            
            # 解析信号
            signal = self.parse_signal(message.text)
            if signal:
                self.add_log("检测到交易信号!", "SUCCESS")
                await self.execute_trade(signal)
            
        except Exception as e:
            self.add_log(f"处理消息错误: {e}", "ERROR")
    
    def parse_signal(self, text):
        """解析信号"""
        if not text:
            return None
        
        match = re.search(r'#(\w+)\s+市[價价]([多空])', text)
        if match:
            symbol = match.group(1).upper()
            direction = match.group(2)
            
            if not symbol.endswith('USDT'):
                symbol = f"{symbol}USDT"
            
            return {
                'symbol': symbol,
                'side': '做多' if direction == '多' else '做空',
                'amount': self.trade_amount,
                'leverage': self.leverage
            }
        
        return None
    
    async def execute_trade(self, signal):
        """执行交易"""
        try:
            self.trade_count += 1
            self.root.after(0, self.update_status)
            
            self.add_log("=" * 40, "TRADE")
            self.add_log(f"执行交易 #{self.trade_count}", "TRADE")
            self.add_log(f"币种: {signal['symbol']}", "TRADE")
            self.add_log(f"方向: {signal['side']}", "TRADE")
            self.add_log(f"金额: {signal['amount']}U", "TRADE")
            self.add_log(f"杠杆: {signal['leverage']}x", "TRADE")
            self.add_log("模拟交易执行成功", "SUCCESS")
            self.add_log("=" * 40, "TRADE")
            
        except Exception as e:
            self.add_log(f"交易执行错误: {e}", "ERROR")
    
    def stop_bot(self):
        """停止机器人"""
        try:
            self.add_log("正在停止机器人...")
            self.running = False
            self.connected = False
            self.reset_buttons()
            self.update_status()
            self.add_log("机器人已停止", "SUCCESS")
            
        except Exception as e:
            print(f"停止机器人时出错: {e}")
    
    def reset_buttons(self):
        """重置按钮状态"""
        try:
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
        except:
            pass
    
    def test_signal(self):
        """测试信号"""
        try:
            test_signals = ["#BTC 市價多", "#ETH 市價空", "#SOL 市價多"]
            
            self.add_log("开始测试信号解析...", "WARNING")
            
            for signal_text in test_signals:
                signal = self.parse_signal(signal_text)
                if signal:
                    self.add_log(f"测试成功: {signal_text} -> {signal['symbol']} {signal['side']}")
                else:
                    self.add_log(f"测试失败: {signal_text}")
            
            self.add_log("测试完成", "SUCCESS")
            
        except Exception as e:
            self.add_log(f"测试出错: {e}", "ERROR")
    
    def on_closing(self):
        """窗口关闭事件"""
        try:
            if self.running:
                self.stop_bot()
                time.sleep(0.5)
            
            print("程序正常退出")
            self.root.destroy()
            
        except Exception as e:
            print(f"关闭程序时出错: {e}")
            self.root.destroy()
    
    def run(self):
        """运行程序"""
        try:
            print("启动GUI主循环...")
            self.root.mainloop()
            
        except KeyboardInterrupt:
            print("程序被用户中断")
        except Exception as e:
            print(f"程序运行出错: {e}")


def main():
    """主函数"""
    try:
        print("=" * 50)
        print("启动Telegram交易跟单机器人")
        print("=" * 50)
        
        bot = SimpleTradingBot()
        bot.run()
        
    except Exception as e:
        print(f"程序启动失败: {e}")
        messagebox.showerror("启动错误", f"程序启动失败: {e}")


if __name__ == "__main__":
    main()
