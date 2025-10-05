"""
主窗口GUI模块
提供应用程序的主界面，整合所有功能模块
"""

import sys
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, 
    QTabWidget, QTextEdit, QLabel, QPushButton, QTableWidget, 
    QTableWidgetItem, QHeaderView, QSplitter, QGroupBox, QGridLayout,
    QStatusBar, QMenuBar, QMessageBox, QProgressBar, QFrame
)
from PyQt6.QtCore import QTimer, QThread, pyqtSignal, Qt, QSize
from PyQt6.QtGui import QFont, QIcon, QPixmap, QPalette, QColor

from ..utils.config import config
from ..utils.logger import get_logger
from ..telegram.monitor import TelegramMonitor
from ..trading.bitget_client import BitgetClient
from ..trading.signal_parser import SignalParser, TradingSignal as SignalData
from ..trading.risk_manager import RiskManager
from ..database.database import db_manager
from ..notifications.notifier import notifier, NotificationType

logger = get_logger("MainWindow")


class WorkerThread(QThread):
    """后台工作线程"""
    signal_received = pyqtSignal(dict)
    status_update = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.telegram_monitor = None
        self.bitget_client = None
        self.signal_parser = SignalParser()
        self.risk_manager = RiskManager()
        self.running = False
    
    async def initialize_services(self):
        """初始化服务"""
        try:
            # 初始化Telegram监控
            self.telegram_monitor = TelegramMonitor()
            await self.telegram_monitor.initialize()
            
            # 添加信号回调
            self.telegram_monitor.add_signal_callback(self.handle_trading_signal)
            self.telegram_monitor.add_error_callback(self.handle_error)
            
            # 初始化Bitget客户端
            self.bitget_client = BitgetClient()
            await self.bitget_client.initialize()
            
            # 初始化数据库
            db_manager.initialize()
            
            self.status_update.emit("所有服务初始化完成")
            
        except Exception as e:
            self.error_occurred.emit(f"服务初始化失败: {str(e)}")
    
    async def handle_trading_signal(self, signal_dict: Dict[str, Any]):
        """处理交易信号"""
        try:
            # 解析信号
            signal = self.signal_parser.parse_signal(
                signal_dict['raw_message'], 
                signal_dict
            )
            
            if not signal:
                return
            
            # 保存信号到数据库
            signal_id = db_manager.save_trading_signal(signal, signal_dict)
            
            # 风险检查
            balance = await self.bitget_client.get_balance()
            risk_ok, risk_msg, risk_details = self.risk_manager.check_signal_risk(signal, balance)
            
            if not risk_ok:
                db_manager.update_signal_status(signal_id, 'ignored', risk_msg)
                await notifier.notify_risk_alert(f"信号被拒绝: {risk_msg}")
                return
            
            # 执行交易
            execution_result = await self.bitget_client.execute_signal(signal)
            
            if execution_result and execution_result.get('success'):
                db_manager.update_signal_status(signal_id, 'processed')
                await notifier.notify_trade_execution(execution_result)
                
                # 更新风险管理器
                order_info = execution_result.get('order', {})
                entry_price = float(order_info.get('price', 0))
                trade_amount = execution_result.get('trade_amount', 0)
                
                if entry_price > 0:
                    self.risk_manager.add_position(signal, entry_price, trade_amount)
            else:
                error_msg = execution_result.get('error', '执行失败') if execution_result else '执行失败'
                db_manager.update_signal_status(signal_id, 'error', error_msg)
                await notifier.notify(f"交易执行失败: {error_msg}", NotificationType.ERROR)
            
            # 发送信号到GUI
            self.signal_received.emit({
                'signal': signal.to_dict(),
                'execution': execution_result,
                'risk_details': risk_details
            })
            
        except Exception as e:
            logger.error(f"处理交易信号失败: {e}")
            self.error_occurred.emit(f"处理信号失败: {str(e)}")
    
    async def handle_error(self, error: Exception):
        """处理错误"""
        self.error_occurred.emit(str(error))
    
    def run(self):
        """线程主循环"""
        self.running = True
        
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # 初始化服务
            loop.run_until_complete(self.initialize_services())
            
            # 启动监控
            if self.telegram_monitor:
                loop.run_until_complete(self.telegram_monitor.start_monitoring())
            
            # 保持运行
            while self.running:
                loop.run_until_complete(asyncio.sleep(1))
                
        except Exception as e:
            self.error_occurred.emit(f"后台线程错误: {str(e)}")
        finally:
            loop.close()
    
    def stop(self):
        """停止线程"""
        self.running = False
        
        # 清理资源
        if self.telegram_monitor:
            asyncio.create_task(self.telegram_monitor.cleanup())
        if self.bitget_client:
            asyncio.create_task(self.bitget_client.close())


class MainWindow(QMainWindow):
    """主窗口类"""
    
    def __init__(self):
        super().__init__()
        
        # 设置窗口属性
        self.setWindowTitle(config.gui.window_title)
        self.setGeometry(100, 100, config.gui.window_width, config.gui.window_height)
        self.setMinimumSize(800, 600)
        
        # 初始化组件
        self.init_ui()
        self.init_worker_thread()
        self.init_timers()
        
        # 应用样式
        self.apply_styles()
        
        logger.info("主窗口初始化完成")
    
    def init_ui(self):
        """初始化用户界面"""
        # 创建中央窗口
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        
        # 创建顶部状态栏
        self.create_status_section(main_layout)
        
        # 创建标签页
        self.create_tab_widget(main_layout)
        
        # 创建底部状态栏
        self.create_status_bar()
        
        # 创建菜单栏
        self.create_menu_bar()
    
    def create_status_section(self, parent_layout):
        """创建状态区域"""
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        status_frame.setMaximumHeight(100)
        
        status_layout = QGridLayout(status_frame)
        
        # 连接状态
        self.telegram_status_label = QLabel("Telegram: 未连接")
        self.bitget_status_label = QLabel("Bitget: 未连接")
        self.database_status_label = QLabel("数据库: 未连接")
        
        # 统计信息
        self.signals_count_label = QLabel("信号: 0")
        self.trades_count_label = QLabel("交易: 0")
        self.pnl_label = QLabel("盈亏: $0.00")
        
        # 控制按钮
        self.start_button = QPushButton("启动监控")
        self.stop_button = QPushButton("停止监控")
        self.stop_button.setEnabled(False)
        
        # 布局
        status_layout.addWidget(QLabel("连接状态:"), 0, 0)
        status_layout.addWidget(self.telegram_status_label, 0, 1)
        status_layout.addWidget(self.bitget_status_label, 0, 2)
        status_layout.addWidget(self.database_status_label, 0, 3)
        
        status_layout.addWidget(QLabel("统计信息:"), 1, 0)
        status_layout.addWidget(self.signals_count_label, 1, 1)
        status_layout.addWidget(self.trades_count_label, 1, 2)
        status_layout.addWidget(self.pnl_label, 1, 3)
        
        status_layout.addWidget(self.start_button, 0, 4)
        status_layout.addWidget(self.stop_button, 1, 4)
        
        parent_layout.addWidget(status_frame)
        
        # 连接按钮事件
        self.start_button.clicked.connect(self.start_monitoring)
        self.stop_button.clicked.connect(self.stop_monitoring)
    
    def create_tab_widget(self, parent_layout):
        """创建标签页窗口"""
        self.tab_widget = QTabWidget()
        
        # 实时监控标签页
        self.create_monitoring_tab()
        
        # 交易历史标签页
        self.create_history_tab()
        
        # 风险管理标签页
        self.create_risk_tab()
        
        # 设置标签页
        self.create_settings_tab()
        
        # 日志标签页
        self.create_log_tab()
        
        parent_layout.addWidget(self.tab_widget)
    
    def create_monitoring_tab(self):
        """创建实时监控标签页"""
        monitoring_widget = QWidget()
        layout = QHBoxLayout(monitoring_widget)
        
        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧：实时信号列表
        signals_group = QGroupBox("实时信号")
        signals_layout = QVBoxLayout(signals_group)
        
        self.signals_table = QTableWidget()
        self.signals_table.setColumnCount(6)
        self.signals_table.setHorizontalHeaderLabels([
            "时间", "币种", "方向", "金额", "置信度", "状态"
        ])
        self.signals_table.horizontalHeader().setStretchLastSection(True)
        signals_layout.addWidget(self.signals_table)
        
        splitter.addWidget(signals_group)
        
        # 右侧：信号详情和图表
        details_group = QGroupBox("信号详情")
        details_layout = QVBoxLayout(details_group)
        
        self.signal_details_text = QTextEdit()
        self.signal_details_text.setReadOnly(True)
        details_layout.addWidget(self.signal_details_text)
        
        splitter.addWidget(details_group)
        
        # 设置分割器比例
        splitter.setSizes([400, 400])
        layout.addWidget(splitter)
        
        self.tab_widget.addTab(monitoring_widget, "实时监控")
    
    def create_history_tab(self):
        """创建交易历史标签页"""
        history_widget = QWidget()
        layout = QVBoxLayout(history_widget)
        
        # 历史交易表格
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(8)
        self.history_table.setHorizontalHeaderLabels([
            "时间", "币种", "方向", "金额", "价格", "状态", "盈亏", "备注"
        ])
        self.history_table.horizontalHeader().setStretchLastSection(True)
        
        layout.addWidget(self.history_table)
        
        self.tab_widget.addTab(history_widget, "交易历史")
    
    def create_risk_tab(self):
        """创建风险管理标签页"""
        risk_widget = QWidget()
        layout = QVBoxLayout(risk_widget)
        
        # 风险指标显示
        metrics_group = QGroupBox("风险指标")
        metrics_layout = QGridLayout(metrics_group)
        
        self.balance_label = QLabel("账户余额: $0.00")
        self.used_margin_label = QLabel("已用保证金: $0.00")
        self.daily_pnl_label = QLabel("今日盈亏: $0.00")
        self.max_drawdown_label = QLabel("最大回撤: 0%")
        self.win_rate_label = QLabel("胜率: 0%")
        
        metrics_layout.addWidget(self.balance_label, 0, 0)
        metrics_layout.addWidget(self.used_margin_label, 0, 1)
        metrics_layout.addWidget(self.daily_pnl_label, 1, 0)
        metrics_layout.addWidget(self.max_drawdown_label, 1, 1)
        metrics_layout.addWidget(self.win_rate_label, 2, 0)
        
        layout.addWidget(metrics_group)
        
        # 持仓列表
        positions_group = QGroupBox("当前持仓")
        positions_layout = QVBoxLayout(positions_group)
        
        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(6)
        self.positions_table.setHorizontalHeaderLabels([
            "币种", "方向", "数量", "入场价", "当前价", "盈亏"
        ])
        positions_layout.addWidget(self.positions_table)
        
        layout.addWidget(positions_group)
        
        self.tab_widget.addTab(risk_widget, "风险管理")
    
    def create_settings_tab(self):
        """创建设置标签页"""
        settings_widget = QWidget()
        layout = QVBoxLayout(settings_widget)
        
        # TODO: 添加各种设置选项
        settings_text = QTextEdit()
        settings_text.setPlainText("设置界面开发中...")
        settings_text.setReadOnly(True)
        
        layout.addWidget(settings_text)
        
        self.tab_widget.addTab(settings_widget, "设置")
    
    def create_log_tab(self):
        """创建日志标签页"""
        log_widget = QWidget()
        layout = QVBoxLayout(log_widget)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        
        layout.addWidget(self.log_text)
        
        self.tab_widget.addTab(log_widget, "日志")
    
    def create_status_bar(self):
        """创建状态栏"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # 添加进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
        
        self.status_bar.showMessage("就绪")
    
    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu('文件')
        
        # 查看菜单
        view_menu = menubar.addMenu('查看')
        
        # 工具菜单
        tools_menu = menubar.addMenu('工具')
        
        # 帮助菜单
        help_menu = menubar.addMenu('帮助')
    
    def init_worker_thread(self):
        """初始化工作线程"""
        self.worker_thread = WorkerThread()
        self.worker_thread.signal_received.connect(self.on_signal_received)
        self.worker_thread.status_update.connect(self.on_status_update)
        self.worker_thread.error_occurred.connect(self.on_error_occurred)
    
    def init_timers(self):
        """初始化定时器"""
        # 状态更新定时器
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(5000)  # 每5秒更新一次
        
        # 数据刷新定时器
        self.data_timer = QTimer()
        self.data_timer.timeout.connect(self.refresh_data)
        self.data_timer.start(10000)  # 每10秒刷新一次
    
    def apply_styles(self):
        """应用样式"""
        # 设置应用样式
        if config.gui.theme == "dark":
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                QTabWidget::pane {
                    border: 1px solid #555555;
                    background-color: #3c3c3c;
                }
                QTabBar::tab {
                    background-color: #555555;
                    color: #ffffff;
                    padding: 8px 16px;
                    margin-right: 2px;
                }
                QTabBar::tab:selected {
                    background-color: #007acc;
                }
                QTableWidget {
                    background-color: #3c3c3c;
                    color: #ffffff;
                    gridline-color: #555555;
                }
                QTextEdit {
                    background-color: #3c3c3c;
                    color: #ffffff;
                    border: 1px solid #555555;
                }
                QPushButton {
                    background-color: #007acc;
                    color: #ffffff;
                    border: none;
                    padding: 6px 12px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #005a9e;
                }
            """)
    
    # ========== 事件处理方法 ==========
    
    def start_monitoring(self):
        """启动监控"""
        try:
            self.worker_thread.start()
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.status_bar.showMessage("正在启动监控...")
            self.progress_bar.setVisible(True)
            
            logger.info("开始启动监控服务")
            
        except Exception as e:
            logger.error(f"启动监控失败: {e}")
            QMessageBox.critical(self, "错误", f"启动监控失败: {str(e)}")
    
    def stop_monitoring(self):
        """停止监控"""
        try:
            self.worker_thread.stop()
            self.worker_thread.wait()  # 等待线程结束
            
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.status_bar.showMessage("监控已停止")
            self.progress_bar.setVisible(False)
            
            logger.info("监控服务已停止")
            
        except Exception as e:
            logger.error(f"停止监控失败: {e}")
            QMessageBox.critical(self, "错误", f"停止监控失败: {str(e)}")
    
    def on_signal_received(self, signal_data: Dict[str, Any]):
        """处理接收到的信号"""
        try:
            signal = signal_data.get('signal', {})
            execution = signal_data.get('execution', {})
            
            # 更新信号表格
            self.add_signal_to_table(signal, execution)
            
            # 更新信号详情
            self.update_signal_details(signal_data)
            
            # 更新统计
            self.update_statistics()
            
        except Exception as e:
            logger.error(f"处理信号显示失败: {e}")
    
    def on_status_update(self, message: str):
        """处理状态更新"""
        self.status_bar.showMessage(message)
        self.add_log_message(f"[状态] {message}")
    
    def on_error_occurred(self, error_message: str):
        """处理错误"""
        self.status_bar.showMessage(f"错误: {error_message}")
        self.add_log_message(f"[错误] {error_message}")
        
        # 显示错误对话框
        QMessageBox.warning(self, "错误", error_message)
    
    def add_signal_to_table(self, signal: Dict[str, Any], execution: Dict[str, Any]):
        """添加信号到表格"""
        try:
            table = self.signals_table
            row = table.rowCount()
            table.insertRow(row)
            
            # 填充数据
            table.setItem(row, 0, QTableWidgetItem(signal.get('parsed_at', '')[:19]))
            table.setItem(row, 1, QTableWidgetItem(signal.get('symbol', '')))
            table.setItem(row, 2, QTableWidgetItem(signal.get('side', '')))
            table.setItem(row, 3, QTableWidgetItem(str(signal.get('amount', ''))))
            table.setItem(row, 4, QTableWidgetItem(f"{signal.get('confidence', 0):.2f}"))
            
            status = "成功" if execution and execution.get('success') else "失败"
            table.setItem(row, 5, QTableWidgetItem(status))
            
            # 滚动到最新行
            table.scrollToBottom()
            
        except Exception as e:
            logger.error(f"添加信号到表格失败: {e}")
    
    def update_signal_details(self, signal_data: Dict[str, Any]):
        """更新信号详情"""
        try:
            signal = signal_data.get('signal', {})
            execution = signal_data.get('execution', {})
            risk_details = signal_data.get('risk_details', {})
            
            details_text = f"""
信号详情:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
交易对: {signal.get('symbol', 'N/A')}
方向: {signal.get('side', 'N/A')}
类型: {signal.get('signal_type', 'N/A')}
金额: {signal.get('amount', 'N/A')}
价格: {signal.get('price', 'N/A')}
止损: {signal.get('stop_loss', 'N/A')}
止盈: {signal.get('take_profit', 'N/A')}
杠杆: {signal.get('leverage', 1)}x
置信度: {signal.get('confidence', 0):.2f}

原始消息:
{signal.get('raw_message', 'N/A')}

执行结果:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
状态: {'成功' if execution and execution.get('success') else '失败'}
{f"错误: {execution.get('error', '')}" if execution and not execution.get('success') else ""}
{f"订单ID: {execution.get('order', {}).get('orderId', 'N/A')}" if execution and execution.get('success') else ""}

风险评估:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
建议金额: ${risk_details.get('suggested_amount', 0):.2f}
风险等级: {risk_details.get('risk_level', 'N/A')}
当前持仓: {risk_details.get('current_positions', 0)}

时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            
            self.signal_details_text.setPlainText(details_text)
            
        except Exception as e:
            logger.error(f"更新信号详情失败: {e}")
    
    def update_status(self):
        """更新状态显示"""
        try:
            # 更新连接状态标签
            # TODO: 实际检查各服务连接状态
            self.telegram_status_label.setText("Telegram: 已连接")
            self.bitget_status_label.setText("Bitget: 已连接")
            self.database_status_label.setText("数据库: 已连接")
            
        except Exception as e:
            logger.error(f"更新状态失败: {e}")
    
    def refresh_data(self):
        """刷新数据"""
        try:
            # 刷新交易历史
            self.refresh_history_table()
            
            # 刷新风险管理数据
            self.refresh_risk_data()
            
        except Exception as e:
            logger.error(f"刷新数据失败: {e}")
    
    def refresh_history_table(self):
        """刷新历史交易表格"""
        # TODO: 从数据库加载历史数据
        pass
    
    def refresh_risk_data(self):
        """刷新风险管理数据"""
        # TODO: 更新风险指标和持仓信息
        pass
    
    def update_statistics(self):
        """更新统计信息"""
        try:
            # TODO: 计算实际统计数据
            signals_count = self.signals_table.rowCount()
            self.signals_count_label.setText(f"信号: {signals_count}")
            
        except Exception as e:
            logger.error(f"更新统计信息失败: {e}")
    
    def add_log_message(self, message: str):
        """添加日志消息"""
        try:
            timestamp = datetime.now().strftime('%H:%M:%S')
            log_entry = f"[{timestamp}] {message}"
            
            self.log_text.append(log_entry)
            
            # 限制日志行数
            if self.log_text.document().blockCount() > 1000:
                cursor = self.log_text.textCursor()
                cursor.movePosition(cursor.MoveOperation.Start)
                cursor.movePosition(cursor.MoveOperation.Down, cursor.MoveMode.KeepAnchor, 100)
                cursor.removeSelectedText()
            
        except Exception as e:
            logger.error(f"添加日志消息失败: {e}")
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        try:
            # 停止监控
            if self.worker_thread.isRunning():
                self.worker_thread.stop()
                self.worker_thread.wait()
            
            logger.info("主窗口已关闭")
            event.accept()
            
        except Exception as e:
            logger.error(f"关闭窗口失败: {e}")
            event.accept()


def run_gui():
    """运行GUI应用程序"""
    app = QApplication(sys.argv)
    
    # 设置应用程序信息
    app.setApplicationName("Telegram Trading Bot")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Trading Bot Team")
    
    # 创建主窗口
    main_window = MainWindow()
    main_window.show()
    
    # 运行应用程序
    sys.exit(app.exec())
