"""
Android服务配置
用于后台运行交易监控服务
"""

from jnius import autoclass, PythonJavaClass, java_method
from android.runnable import run_on_ui_thread
from kivy.logger import Logger

# Android API
PythonService = autoclass('org.kivy.android.PythonService')
Intent = autoclass('android.content.Intent')
PendingIntent = autoclass('android.app.PendingIntent')
NotificationBuilder = autoclass('android.app.Notification$Builder')
NotificationManager = autoclass('android.app.NotificationManager')
Context = autoclass('android.content.Context')


class AndroidTradingService(PythonJavaClass):
    """Android后台交易服务"""
    
    __javainterfaces__ = ['org/kivy/android/PythonJavaClass']
    
    def __init__(self):
        super().__init__()
        self.service = None
        self.notification_manager = None
        
    @java_method('()V')
    def onCreate(self):
        """服务创建时调用"""
        Logger.info("TradingService: 服务已创建")
        
    @java_method('(Landroid/content/Intent;I)I')
    def onStartCommand(self, intent, flags, start_id):
        """服务启动时调用"""
        Logger.info("TradingService: 服务已启动")
        
        # 创建前台服务通知
        self.create_notification()
        
        # 返回START_STICKY以保持服务运行
        return 1  # START_STICKY
        
    @java_method('()V')
    def onDestroy(self):
        """服务销毁时调用"""
        Logger.info("TradingService: 服务已销毁")
        
    def create_notification(self):
        """创建前台服务通知"""
        try:
            # 获取通知管理器
            self.notification_manager = PythonService.mService.getSystemService(
                Context.NOTIFICATION_SERVICE
            )
            
            # 创建通知
            builder = NotificationBuilder(PythonService.mService)
            builder.setContentTitle("交易跟单机器人")
            builder.setContentText("正在监控交易信号...")
            builder.setSmallIcon(17301640)  # 使用系统图标
            builder.setOngoing(True)
            
            # 创建点击意图
            intent = Intent(PythonService.mService, PythonService.mService.__class__)
            pending_intent = PendingIntent.getActivity(
                PythonService.mService, 0, intent, 0
            )
            builder.setContentIntent(pending_intent)
            
            notification = builder.build()
            
            # 启动前台服务
            PythonService.mService.startForeground(1, notification)
            
            Logger.info("TradingService: 前台服务通知已创建")
            
        except Exception as e:
            Logger.error(f"TradingService: 创建通知失败: {e}")


def start_android_service():
    """启动Android后台服务"""
    try:
        from android import mActivity
        service = AndroidTradingService()
        Logger.info("Android服务已启动")
        return service
    except ImportError:
        Logger.info("非Android环境，跳过服务启动")
        return None
    except Exception as e:
        Logger.error(f"启动Android服务失败: {e}")
        return None
