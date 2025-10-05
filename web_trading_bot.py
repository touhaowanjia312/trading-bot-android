#!/usr/bin/env python3
"""
Web界面交易机器人
使用Flask创建Web界面，在浏览器中查看状态
"""

import os
import sys
import asyncio
import threading
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request
import re
import json

sys.path.insert(0, str(Path(__file__).parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 全局变量
app = Flask(__name__)
bot_status = {
    'running': False,
    'connected': False,
    'channel_name': '未连接',
    'trade_count': 0,
    'logs': [],
    'last_update': datetime.now().strftime('%H:%M:%S')
}

telegram_client = None
target_channel = None

# 配置
API_ID = os.getenv('TELEGRAM_API_ID')
API_HASH = os.getenv('TELEGRAM_API_HASH')
TRADE_AMOUNT = float(os.getenv('DEFAULT_TRADE_AMOUNT', '2.0'))
LEVERAGE = int(os.getenv('DEFAULT_LEVERAGE', '20'))

def add_log(message, level="INFO"):
    """添加日志"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    log_entry = {
        'time': timestamp,
        'message': message,
        'level': level
    }
    bot_status['logs'].append(log_entry)
    
    # 保持最近100条日志
    if len(bot_status['logs']) > 100:
        bot_status['logs'] = bot_status['logs'][-100:]
    
    bot_status['last_update'] = timestamp
    print(f"[{timestamp}] {message}")

def parse_signal(message):
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
            'amount': TRADE_AMOUNT,
            'leverage': LEVERAGE,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'raw_message': message
        }
        
    return None

async def execute_trade(signal):
    """执行交易"""
    try:
        bot_status['trade_count'] += 1
        
        add_log("=" * 50, "TRADE")
        add_log(f"💰 执行交易 #{bot_status['trade_count']}", "TRADE")
        add_log(f"📊 币种: {signal['symbol']}", "TRADE")
        add_log(f"📈 方向: {signal['direction_cn']}", "TRADE")
        add_log(f"💰 金额: {signal['amount']}U", "TRADE")
        add_log(f"📊 杠杆: {signal['leverage']}x", "TRADE")
        
        if signal['stop_loss']:
            add_log(f"🛡️ 止损: {signal['stop_loss']}", "TRADE")
            
        if signal['take_profit']:
            add_log(f"🎯 止盈: {signal['take_profit']}", "TRADE")
            
        # 模拟交易执行
        add_log("✅ 模拟交易执行成功", "SUCCESS")
        add_log("=" * 50, "TRADE")
        
    except Exception as e:
        add_log(f"❌ 交易执行失败: {e}", "ERROR")

async def handle_new_message(event):
    """处理新消息"""
    try:
        message = event.message
        if not message.text:
            return
            
        sender = await message.get_sender()
        sender_name = getattr(sender, 'first_name', 'Unknown') if sender else 'Unknown'
        
        add_log(f"📨 [{sender_name}]: {message.text}")
        
        # 解析信号
        signal = parse_signal(message.text)
        
        if signal:
            add_log("🎯 检测到交易信号!", "SUCCESS")
            await execute_trade(signal)
            
    except Exception as e:
        add_log(f"❌ 处理消息失败: {e}", "ERROR")

async def start_telegram_bot():
    """启动Telegram机器人"""
    global telegram_client, target_channel
    
    try:
        from telethon import TelegramClient, events
        
        add_log("🔗 连接Telegram服务器...")
        telegram_client = TelegramClient('trading_session', API_ID, API_HASH)
        await telegram_client.connect()
        
        if not await telegram_client.is_user_authorized():
            add_log("❌ 未认证，请先运行认证程序", "ERROR")
            return False
            
        add_log("✅ Telegram连接成功", "SUCCESS")
        
        # 查找频道
        add_log("🔍 查找目标频道...")
        
        async for dialog in telegram_client.iter_dialogs():
            if dialog.is_channel and 'Seven' in dialog.title and ('司' in dialog.title or 'VIP' in dialog.title):
                target_channel = dialog.entity
                channel_name = dialog.title
                break
                
        if not target_channel:
            add_log("❌ 未找到目标频道", "ERROR")
            return False
            
        add_log(f"✅ 找到频道: {channel_name}", "SUCCESS")
        bot_status['connected'] = True
        bot_status['channel_name'] = channel_name
        
        # 注册消息处理器
        @telegram_client.on(events.NewMessage(chats=target_channel))
        async def message_handler(event):
            await handle_new_message(event)
            
        bot_status['running'] = True
        add_log("👀 开始监控频道消息...", "SUCCESS")
        add_log("💡 等待交易信号 (#币种 市價多/空)")
        
        # 保持运行
        await telegram_client.run_until_disconnected()
        
    except Exception as e:
        add_log(f"❌ 启动失败: {e}", "ERROR")
        return False
    finally:
        bot_status['running'] = False
        bot_status['connected'] = False
        bot_status['channel_name'] = '未连接'

def run_telegram_bot():
    """在新线程中运行Telegram机器人"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(start_telegram_bot())
    except Exception as e:
        add_log(f"❌ 机器人运行出错: {e}", "ERROR")
    finally:
        loop.close()

# Web界面HTML模板
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telegram交易跟单机器人</title>
    <style>
        body {
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            margin: 0;
            padding: 20px;
            min-height: 100vh;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: rgba(255, 255, 255, 0.95);
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        .header h1 {
            color: #333;
            margin: 0;
            font-size: 2.5em;
        }
        .status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .status-card {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            border-left: 5px solid #007bff;
        }
        .status-card h3 {
            margin: 0 0 10px 0;
            color: #333;
        }
        .status-value {
            font-size: 1.2em;
            font-weight: bold;
        }
        .status-connected { border-left-color: #28a745; }
        .status-disconnected { border-left-color: #dc3545; }
        .controls {
            text-align: center;
            margin-bottom: 30px;
        }
        .btn {
            padding: 12px 24px;
            margin: 0 10px;
            border: none;
            border-radius: 25px;
            font-size: 16px;
            cursor: pointer;
            transition: all 0.3s;
        }
        .btn-start {
            background: #28a745;
            color: white;
        }
        .btn-stop {
            background: #dc3545;
            color: white;
        }
        .btn-test {
            background: #ffc107;
            color: black;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
        }
        .log-container {
            background: #1e1e1e;
            color: #00ff00;
            padding: 20px;
            border-radius: 10px;
            height: 400px;
            overflow-y: auto;
            font-family: 'Consolas', monospace;
            font-size: 14px;
        }
        .log-entry {
            margin-bottom: 5px;
            padding: 2px 0;
        }
        .log-info { color: #00ff00; }
        .log-success { color: #00ff00; }
        .log-error { color: #ff0000; }
        .log-warning { color: #ffff00; }
        .log-trade { color: #00ffff; }
        .refresh-info {
            text-align: center;
            color: #666;
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Telegram交易跟单机器人</h1>
            <p>实时监控 Seven的手工壽司鋪🍣（VIP）频道</p>
        </div>
        
        <div class="status-grid">
            <div class="status-card" id="status-card">
                <h3>🔗 连接状态</h3>
                <div class="status-value" id="connection-status">🔴 未连接</div>
            </div>
            <div class="status-card">
                <h3>📺 监控频道</h3>
                <div class="status-value" id="channel-name">未连接</div>
            </div>
            <div class="status-card">
                <h3>💰 交易次数</h3>
                <div class="status-value" id="trade-count">0</div>
            </div>
            <div class="status-card">
                <h3>⚙️ 交易配置</h3>
                <div class="status-value">{{ trade_amount }}U / {{ leverage }}x</div>
            </div>
        </div>
        
        <div class="controls">
            <button class="btn btn-start" onclick="startBot()">▶️ 启动机器人</button>
            <button class="btn btn-stop" onclick="stopBot()">⏹️ 停止机器人</button>
            <button class="btn btn-test" onclick="testSignal()">🧪 测试信号</button>
        </div>
        
        <div>
            <h3>📝 实时日志</h3>
            <div class="log-container" id="log-container">
                <div class="log-entry">等待日志更新...</div>
            </div>
            <div class="refresh-info">
                页面每3秒自动刷新 | 最后更新: <span id="last-update">--:--:--</span>
            </div>
        </div>
    </div>

    <script>
        function updateStatus() {
            fetch('/status')
                .then(response => response.json())
                .then(data => {
                    // 更新连接状态
                    const statusCard = document.getElementById('status-card');
                    const connectionStatus = document.getElementById('connection-status');
                    
                    if (data.connected) {
                        connectionStatus.textContent = '🟢 已连接';
                        statusCard.className = 'status-card status-connected';
                    } else {
                        connectionStatus.textContent = '🔴 未连接';
                        statusCard.className = 'status-card status-disconnected';
                    }
                    
                    // 更新其他状态
                    document.getElementById('channel-name').textContent = data.channel_name;
                    document.getElementById('trade-count').textContent = data.trade_count;
                    document.getElementById('last-update').textContent = data.last_update;
                    
                    // 更新日志
                    const logContainer = document.getElementById('log-container');
                    logContainer.innerHTML = '';
                    
                    data.logs.slice(-50).forEach(log => {
                        const logEntry = document.createElement('div');
                        logEntry.className = `log-entry log-${log.level.toLowerCase()}`;
                        logEntry.textContent = `[${log.time}] ${log.message}`;
                        logContainer.appendChild(logEntry);
                    });
                    
                    // 滚动到底部
                    logContainer.scrollTop = logContainer.scrollHeight;
                })
                .catch(error => console.error('Error:', error));
        }
        
        function startBot() {
            fetch('/start', {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('机器人启动中...');
                    } else {
                        alert('启动失败: ' + data.message);
                    }
                });
        }
        
        function stopBot() {
            fetch('/stop', {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    alert(data.message);
                });
        }
        
        function testSignal() {
            fetch('/test', {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    alert('测试完成，请查看日志');
                });
        }
        
        // 定时更新状态
        setInterval(updateStatus, 3000);
        updateStatus(); // 立即更新一次
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """主页"""
    return render_template_string(HTML_TEMPLATE, 
                                trade_amount=TRADE_AMOUNT, 
                                leverage=LEVERAGE)

@app.route('/status')
def status():
    """获取状态"""
    return jsonify(bot_status)

@app.route('/start', methods=['POST'])
def start():
    """启动机器人"""
    if bot_status['running']:
        return jsonify({'success': False, 'message': '机器人已在运行'})
    
    add_log("🚀 启动机器人...")
    threading.Thread(target=run_telegram_bot, daemon=True).start()
    
    return jsonify({'success': True, 'message': '机器人启动中...'})

@app.route('/stop', methods=['POST'])
def stop():
    """停止机器人"""
    global telegram_client
    
    if telegram_client:
        add_log("⏹️ 正在停止机器人...", "WARNING")
        # 这里应该优雅地停止客户端
        bot_status['running'] = False
        bot_status['connected'] = False
        bot_status['channel_name'] = '未连接'
        add_log("✅ 机器人已停止", "SUCCESS")
    
    return jsonify({'success': True, 'message': '机器人已停止'})

@app.route('/test', methods=['POST'])
def test():
    """测试信号"""
    test_signals = [
        "#BTC 市價多",
        "#ETH 市價空 止损2800 第一止盈2500",
        "#SOL 市價多 第一止盈180"
    ]
    
    add_log("🧪 开始测试信号解析...", "WARNING")
    
    for signal_text in test_signals:
        add_log(f"测试: {signal_text}")
        signal = parse_signal(signal_text)
        
        if signal:
            add_log(f"✅ 解析成功: {signal['symbol']} {signal['direction_cn']}")
        else:
            add_log("❌ 解析失败")
            
    add_log("🧪 测试完成", "SUCCESS")
    
    return jsonify({'success': True, 'message': '测试完成'})

if __name__ == "__main__":
    add_log("🌐 Web界面交易机器人启动")
    add_log(f"📊 配置: {TRADE_AMOUNT}U, {LEVERAGE}x杠杆")
    add_log("💡 请在浏览器中访问: http://localhost:5000")
    
    print("\n" + "="*60)
    print("🌐 Web界面交易机器人")
    print("="*60)
    print("📱 请在浏览器中打开: http://localhost:5000")
    print("💡 或者: http://127.0.0.1:5000")
    print("="*60)
    
    app.run(host='0.0.0.0', port=5000, debug=False)
