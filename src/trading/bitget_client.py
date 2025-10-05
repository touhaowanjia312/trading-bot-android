"""
Bitget交易平台API客户端模块
负责与Bitget交易所进行API交互，执行交易操作
"""

import time
import hmac
import hashlib
import base64
import json
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import aiohttp

from .signal_parser import TradingSignal, OrderSide, SignalType
from ..utils.config import config
from ..utils.logger import bitget_logger
from ..utils.helpers import safe_float, generate_order_id, retry_async


class BitgetAPIError(Exception):
    """Bitget API错误"""
    
    def __init__(self, message: str, code: Optional[str] = None, response: Optional[Dict] = None):
        super().__init__(message)
        self.code = code
        self.response = response


class BitgetClient:
    """Bitget交易客户端"""
    
    def __init__(self):
        self.api_key = config.bitget.api_key
        self.secret_key = config.bitget.secret_key
        self.passphrase = config.bitget.passphrase
        self.sandbox = config.bitget.sandbox
        
        # API端点
        self.base_url = "https://api.bitget.com" if not self.sandbox else "https://api.sandbox.bitget.com"
        
        # HTTP会话
        self.session: Optional[aiohttp.ClientSession] = None
        
        # 请求限制
        self.request_count = 0
        self.last_request_time = 0
        self.rate_limit_per_second = 10
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
    
    async def initialize(self):
        """初始化客户端"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
            bitget_logger.info("Bitget客户端已初始化")
    
    async def close(self):
        """关闭客户端"""
        if self.session:
            await self.session.close()
            self.session = None
            bitget_logger.info("Bitget客户端已关闭")
    
    def _generate_signature(self, method: str, request_path: str, body: str = "", params: Dict[str, Any] = None) -> Dict[str, str]:
        """
        生成API签名
        
        Args:
            method: HTTP方法
            request_path: 请求路径
            body: 请求体
            params: query参数
            
        Returns:
            包含签名的请求头
        """
        timestamp = str(int(time.time() * 1000))
        
        # 如果有query参数，需要包含在签名中
        if params:
            query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
            if query_string:
                request_path = f"{request_path}?{query_string}"
        
        # 创建签名字符串
        message = timestamp + method.upper() + request_path + body
        
        # 生成签名
        signature = base64.b64encode(
            hmac.new(
                self.secret_key.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        
        return {
            'ACCESS-KEY': self.api_key,
            'ACCESS-SIGN': signature,
            'ACCESS-TIMESTAMP': timestamp,
            'ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json'
        }
    
    async def _rate_limit(self):
        """限制请求频率"""
        current_time = time.time()
        
        # 如果在同一秒内，检查请求数量
        if int(current_time) == int(self.last_request_time):
            if self.request_count >= self.rate_limit_per_second:
                sleep_time = 1 - (current_time - int(current_time))
                await asyncio.sleep(sleep_time)
                self.request_count = 0
        else:
            self.request_count = 0
        
        self.request_count += 1
        self.last_request_time = current_time
    
    @retry_async(max_retries=3, delay=1.0)
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict] = None, 
        data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        发送API请求
        
        Args:
            method: HTTP方法
            endpoint: API端点
            params: URL参数
            data: 请求数据
            
        Returns:
            API响应数据
        """
        if not self.session:
            await self.initialize()
        
        # 限制请求频率
        await self._rate_limit()
        
        url = self.base_url + endpoint
        body = json.dumps(data) if data else ""
        
        # 生成签名
        headers = self._generate_signature(method, endpoint, body, params)
        
        bitget_logger.log_api_call(endpoint, params or data or {})
        
        try:
            async with self.session.request(
                method, 
                url, 
                params=params, 
                data=body if data else None, 
                headers=headers
            ) as response:
                
                response_text = await response.text()
                
                if response.status != 200:
                    bitget_logger.error(f"API请求失败: {response.status} - {response_text}")
                    raise BitgetAPIError(
                        f"HTTP {response.status}: {response_text}",
                        code=str(response.status)
                    )
                
                try:
                    result = json.loads(response_text)
                except json.JSONDecodeError:
                    raise BitgetAPIError(f"无效的JSON响应: {response_text}")
                
                # 检查API错误
                if result.get('code') != '00000':
                    error_msg = result.get('msg', '未知错误')
                    error_code = result.get('code', 'UNKNOWN')
                    bitget_logger.error(f"Bitget API错误: {error_code} - {error_msg}")
                    raise BitgetAPIError(error_msg, error_code, result)
                
                return result
        
        except aiohttp.ClientError as e:
            bitget_logger.error(f"网络请求失败: {e}")
            raise BitgetAPIError(f"网络请求失败: {e}")
    
    async def get_account_info(self) -> Dict[str, Any]:
        """
        获取合约账户信息
        
        Returns:
            账户信息
        """
        try:
            # 使用合约账户API而不是现货账户API
            result = await self._make_request('GET', '/api/mix/v1/account/accounts', params={'productType': 'UMCBL'})
            return result.get('data', [])
        except Exception as e:
            bitget_logger.error(f"获取合约账户信息失败: {e}")
            raise
    
    async def get_balance(self, currency: str = "USDT") -> float:
        """
        获取合约账户指定币种余额
        
        Args:
            currency: 币种符号
            
        Returns:
            可用余额
        """
        try:
            account_info = await self.get_account_info()
            
            # 合约账户API返回的数据结构不同
            if isinstance(account_info, list) and account_info:
                for account in account_info:
                    if account.get('marginCoin') == currency:
                        return safe_float(account.get('available', 0))
            
            return 0.0
            
        except Exception as e:
            bitget_logger.error(f"获取合约账户余额失败: {e}")
            return 0.0
    
    async def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取合约交易对信息
        
        Args:
            symbol: 交易对符号
            
        Returns:
            交易对信息
        """
        try:
            # 使用合约产品信息API
            result = await self._make_request('GET', '/api/mix/v1/market/contracts', params={'productType': 'UMCBL'})
            products = result.get('data', [])
            
            for product in products:
                if product.get('symbol') == symbol:
                    return product
            
            return None
            
        except Exception as e:
            bitget_logger.error(f"获取合约交易对信息失败: {e}")
            return None
    
    async def get_ticker(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取合约行情数据
        
        Args:
            symbol: 交易对符号
            
        Returns:
            行情数据
        """
        try:
            params = {'symbol': symbol}
            # 使用合约行情API而不是现货API
            result = await self._make_request('GET', '/api/mix/v1/market/ticker', params=params)
            return result.get('data')
        except Exception as e:
            bitget_logger.error(f"获取合约行情数据失败: {e}")
            return None
    
    async def get_current_price(self, symbol: str) -> Optional[float]:
        """
        获取当前价格
        
        Args:
            symbol: 交易对符号
            
        Returns:
            当前价格
        """
        try:
            ticker_data = await self.get_ticker(symbol)
            if ticker_data:
                # 从ticker数据中提取当前价格
                if isinstance(ticker_data, list) and ticker_data:
                    price_str = ticker_data[0].get('last') or ticker_data[0].get('close')
                elif isinstance(ticker_data, dict):
                    price_str = ticker_data.get('last') or ticker_data.get('close')
                else:
                    return None
                
                if price_str:
                    return float(price_str)
            
            return None
        except Exception as e:
            bitget_logger.error(f"获取当前价格失败: {e}")
            return None
    
    async def place_market_order(
        self, 
        symbol: str, 
        side: str, 
        amount: float, 
        client_order_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        下市价单
        
        Args:
            symbol: 交易对符号
            side: 交易方向 (buy/sell)
            amount: 合约张数（经过计算的合约数量）
            client_order_id: 客户端订单ID
            
        Returns:
            订单信息
        """
        try:
            if not client_order_id:
                client_order_id = generate_order_id(symbol, side)
            
            # 对于合约交易，size参数表示合约张数
            order_data = {
                'symbol': symbol,
                'side': 'open_long' if side == 'buy' else 'open_short',
                'orderType': 'market',
                'size': str(amount),  # 合约张数（经过计算）
                'clientOrderId': client_order_id,
                'productType': 'UMCBL',
                'marginCoin': 'USDT',
                'marginMode': 'crossed'  # 全仓模式
            }
            
            result = await self._make_request('POST', '/api/mix/v1/order/placeOrder', data=order_data)
            order_info = result.get('data')
            
            if order_info:
                bitget_logger.log_order_placed(
                    order_info.get('orderId'),
                    symbol,
                    side,
                    amount
                )
            
            return order_info
            
        except Exception as e:
            bitget_logger.log_order_error(str(e), order_data)
            raise
    
    async def place_limit_order(
        self, 
        symbol: str, 
        side: str, 
        amount: float, 
        price: float,
        client_order_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        下限价单
        
        Args:
            symbol: 交易对符号
            side: 交易方向 (buy/sell)
            amount: 保证金金额（USDT）或平仓数量
            price: 限价价格
            client_order_id: 客户端订单ID
            
        Returns:
            订单信息
        """
        try:
            if not client_order_id:
                client_order_id = generate_order_id(symbol, side)
            
            # 处理合约方向
            if side in ['close_long', 'close_short', 'open_long', 'open_short']:
                contract_side = side
            else:
                contract_side = 'open_long' if side == 'buy' else 'open_short'
            
            order_data = {
                'symbol': symbol,
                'side': contract_side,
                'orderType': 'limit',
                'size': str(amount),  # 合约价值（USDT），不是保证金
                'price': str(price),
                'clientOrderId': client_order_id,
                'productType': 'UMCBL',
                'marginCoin': 'USDT',
                'marginMode': 'crossed'  # 全仓模式
            }
            
            result = await self._make_request('POST', '/api/mix/v1/order/placeOrder', data=order_data)
            order_info = result.get('data')
            
            if order_info:
                bitget_logger.log_order_placed(
                    order_info.get('orderId'),
                    symbol,
                    side,
                    amount
                )
            
            return order_info
            
        except Exception as e:
            bitget_logger.log_order_error(str(e), order_data)
            raise
    
    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """
        取消订单
        
        Args:
            symbol: 交易对符号
            order_id: 订单ID
            
        Returns:
            是否成功取消
        """
        try:
            order_data = {
                'symbol': symbol,
                'orderId': order_id
            }
            
            await self._make_request('POST', '/api/spot/v1/trade/cancel-order', data=order_data)
            bitget_logger.info(f"订单已取消: {order_id}")
            return True
            
        except Exception as e:
            bitget_logger.error(f"取消订单失败: {e}")
            return False
    
    async def get_order_status(self, symbol: str, order_id: str) -> Optional[Dict[str, Any]]:
        """
        获取订单状态
        
        Args:
            symbol: 交易对符号
            order_id: 订单ID
            
        Returns:
            订单状态信息
        """
        try:
            params = {
                'symbol': symbol,
                'orderId': order_id
            }
            
            result = await self._make_request('GET', '/api/spot/v1/trade/orderInfo', params=params)
            return result.get('data')
            
        except Exception as e:
            bitget_logger.error(f"获取订单状态失败: {e}")
            return None
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取未成交订单
        
        Args:
            symbol: 交易对符号，为None时获取所有
            
        Returns:
            未成交订单列表
        """
        try:
            params = {}
            if symbol:
                params['symbol'] = symbol
            
            result = await self._make_request('GET', '/api/spot/v1/trade/open-orders', params=params)
            return result.get('data', [])
            
        except Exception as e:
            bitget_logger.error(f"获取未成交订单失败: {e}")
            return []
    
    async def execute_signal(self, signal: TradingSignal) -> Optional[Dict[str, Any]]:
        """
        执行交易信号
        
        Args:
            signal: 交易信号
            
        Returns:
            执行结果
        """
        try:
            bitget_logger.info(f"执行交易信号: {signal.symbol} {signal.side.value} 杠杆:{signal.leverage}x")
            
            # 获取当前余额
            balance = await self.get_balance("USDT")
            if balance <= 0:
                raise BitgetAPIError("账户余额不足")
            
            # 转换为Bitget合约格式
            contract_symbol = signal.symbol
            if contract_symbol.endswith('USDT') and not contract_symbol.endswith('_UMCBL'):
                contract_symbol = f"{contract_symbol}_UMCBL"
            
            # 获取交易对信息
            symbol_info = await self.get_symbol_info(contract_symbol)
            if not symbol_info:
                raise BitgetAPIError(f"无效的交易对: {contract_symbol}")
            
            # 使用配置的固定交易金额（保证金）
            margin_amount = signal.amount or config.trading.default_trade_amount
            leverage = signal.leverage or config.trading.default_leverage
            
            # 检查余额是否足够
            if margin_amount > balance:
                bitget_logger.warning(f"保证金({margin_amount}U)超过余额({balance}U)，使用全部余额")
                margin_amount = balance
            
            # 关键修复：Bitget API的size参数表示合约张数（数量），不是USDT价值！
            # 正确计算公式：合约张数 = 保证金 ÷ (当前价格 ÷ 杠杆)
            # 或者：合约张数 = (保证金 × 杠杆) ÷ 当前价格
            
            # 获取当前市场价格用于计算合约张数
            current_price = await self.get_current_price(contract_symbol)
            
            if current_price is None or current_price <= 0:
                bitget_logger.error(f"无法获取 {contract_symbol} 的当前价格，无法计算正确的合约张数")
                raise BitgetAPIError(f"无法获取 {contract_symbol} 的当前价格")
            
            # 正确的计算方法：
            # 目标：使用指定保证金开仓
            # 公式：合约张数 = 保证金 ÷ (当前价格 ÷ 杠杆)
            # 简化：合约张数 = (保证金 × 杠杆) ÷ 当前价格
            
            # 但是！根据用户反馈和实际测试，正确的公式应该是：
            # 合约张数 = 保证金 ÷ (当前价格 ÷ 杠杆)
            # 这样可以确保实际使用的保证金就是指定的保证金
            
            contract_size = margin_amount / (current_price / leverage)
            
            bitget_logger.info("=" * 60)
            bitget_logger.info("🔧 修复后的开仓计算:")
            bitget_logger.info(f"📊 目标保证金: {margin_amount} USDT")
            bitget_logger.info(f"⚡ 杠杆倍数: {leverage}x")
            bitget_logger.info(f"💰 当前价格: {current_price}")
            bitget_logger.info(f"📐 计算公式: 合约张数 = 保证金 ÷ (当前价格 ÷ 杠杆)")
            bitget_logger.info(f"🎯 计算过程: {margin_amount} ÷ ({current_price} ÷ {leverage})")
            bitget_logger.info(f"✅ 合约张数: {contract_size}")
            bitget_logger.info(f"🔍 预期保证金: {contract_size * current_price / leverage:.4f} USDT")
            bitget_logger.info("=" * 60)
            
            # 执行订单 - 传入合约张数
            if signal.signal_type == SignalType.MARKET_ORDER:
                order_result = await self.place_market_order(
                    contract_symbol,
                    signal.side.value,
                    contract_size  # 传入合约张数
                )
            elif signal.signal_type == SignalType.LIMIT_ORDER and signal.price:
                # 对于限价单，也传入合约张数
                order_result = await self.place_limit_order(
                    contract_symbol,
                    signal.side.value,
                    contract_size,  # 传入合约张数
                    signal.price
                )
            else:
                raise BitgetAPIError("不支持的信号类型或缺少必要参数")
            
            # 处理止损止盈订单
            stop_loss_order = None
            take_profit_order = None
            
            if config.trading.use_trader_signals_for_tp_sl and (signal.stop_loss or signal.take_profit):
                bitget_logger.info("根据交易员信号设置止损止盈")
                
                # 获取主订单价格用于计算数量
                if order_result and order_result.get('orderId'):
                    # 等待主订单成交后设置止损止盈
                    await asyncio.sleep(2)  # 等待成交
                    
                    order_status = await self.get_order_status(contract_symbol, order_result['orderId'])
                    if order_status and order_status.get('status') == 'filled':
                        filled_price = float(order_status.get('fillPrice', 0))
                        filled_quantity = float(order_status.get('fillSize', 0))
                        
                        if signal.stop_loss and filled_price > 0:
                            try:
                                # 设置止损单 - 合约平仓
                                sl_side = "close_long" if signal.side.value == "buy" else "close_short"
                                stop_loss_order = await self.place_limit_order(
                                    contract_symbol,
                                    sl_side,
                                    filled_quantity,
                                    signal.stop_loss,
                                    f"SL_{order_result['orderId']}"
                                )
                                bitget_logger.info(f"止损单已设置: {signal.stop_loss}")
                            except Exception as e:
                                bitget_logger.error(f"设置止损单失败: {e}")
                        
                        if signal.take_profit and filled_price > 0:
                            try:
                                # 设置止盈单 - 合约平仓
                                tp_side = "close_long" if signal.side.value == "buy" else "close_short"
                                take_profit_order = await self.place_limit_order(
                                    contract_symbol,
                                    tp_side,
                                    filled_quantity,
                                    signal.take_profit,
                                    f"TP_{order_result['orderId']}"
                                )
                                bitget_logger.info(f"止盈单已设置: {signal.take_profit}")
                            except Exception as e:
                                bitget_logger.error(f"设置止盈单失败: {e}")
            
            # 设置自动止损 - 亏损7U时自动平仓
            auto_stop_loss_order = None
            try:
                bitget_logger.info("开始设置自动止损...")
                
                if order_result and order_result.get('orderId'):
                    bitget_logger.info(f"订单ID: {order_result.get('orderId')}, 等待订单成交...")
                    
                    # 等待主订单成交
                    await asyncio.sleep(3)  # 增加等待时间确保成交
                    
                    # 获取订单状态确认成交
                    order_status = await self.get_order_status(contract_symbol, order_result['orderId'])
                    bitget_logger.info(f"订单状态: {order_status}")
                    
                    if order_status and order_status.get('status') == 'filled':
                        filled_price = float(order_status.get('fillPrice', 0))
                        filled_quantity = float(order_status.get('fillSize', 0))
                        
                        bitget_logger.info(f"订单已成交: 成交价={filled_price}, 成交量={filled_quantity}")
                        
                        if filled_price > 0 and filled_quantity > 0:
                            # 计算止损价格：亏损7U时的价格
                            # 修正计算公式：
                            # 对于多头：止损价 = 开仓价 - (7U / (合约张数 / 杠杆))
                            # 对于空头：止损价 = 开仓价 + (7U / (合约张数 / 杠杆))
                            loss_amount = 7.0  # 亏损7U
                            
                            # 修正计算：每张合约的价值 = 合约张数 × 当前价格 / 杠杆
                            # 止损时的价格变动 = 亏损金额 / (合约张数 / 杠杆)
                            price_diff = loss_amount / (filled_quantity / leverage)
                            
                            if signal.side.value == "buy":  # 多头
                                stop_loss_price = filled_price - price_diff
                            else:  # 空头
                                stop_loss_price = filled_price + price_diff
                            
                            # 价格精度处理
                            stop_loss_price = round(stop_loss_price, 4)
                            
                            bitget_logger.info(f"止损计算详情:")
                            bitget_logger.info(f"  - 开仓价: {filled_price}")
                            bitget_logger.info(f"  - 成交量: {filled_quantity}")
                            bitget_logger.info(f"  - 杠杆: {leverage}x")
                            bitget_logger.info(f"  - 目标亏损: {loss_amount}U")
                            bitget_logger.info(f"  - 价格差值: {price_diff}")
                            bitget_logger.info(f"  - 止损价: {stop_loss_price}")
                            
                            # 使用计划委托设置止损
                            try:
                                auto_stop_loss_order = await self.set_auto_stop_loss(
                                    contract_symbol, 
                                    stop_loss_price, 
                                    filled_quantity,
                                    signal.side.value
                                )
                                
                                if auto_stop_loss_order:
                                    bitget_logger.info("✅ 自动止损设置成功!")
                                else:
                                    bitget_logger.error("❌ 自动止损设置失败: 返回结果为空")
                                    
                            except Exception as stop_loss_error:
                                bitget_logger.error(f"❌ 自动止损设置异常: {stop_loss_error}")
                                auto_stop_loss_order = None
                        else:
                            bitget_logger.error(f"无效的成交数据: 价格={filled_price}, 数量={filled_quantity}")
                    else:
                        bitget_logger.warning(f"订单未成交或状态异常: {order_status}")
                else:
                    bitget_logger.error("无有效订单ID，无法设置自动止损")
                    
            except Exception as e:
                bitget_logger.error(f"设置自动止损失败: {e}")
                import traceback
                bitget_logger.error(f"详细错误: {traceback.format_exc()}")

            execution_result = {
                'signal': signal.to_dict(),
                'order': order_result,
                'stop_loss_order': stop_loss_order,
                'take_profit_order': take_profit_order,
                'auto_stop_loss_order': auto_stop_loss_order,  # 新增自动止损订单
                'executed_at': datetime.now(timezone.utc).isoformat(),
                'margin_amount': margin_amount,
                'contract_size': contract_size,
                'leverage': signal.leverage,
                'success': True
            }
            
            bitget_logger.info(f"信号执行成功: 订单ID {order_result.get('orderId')}")
            return execution_result
            
        except Exception as e:
            bitget_logger.error(f"执行信号失败: {e}")
            return {
                'signal': signal.to_dict(),
                'error': str(e),
                'executed_at': datetime.now(timezone.utc).isoformat(),
                'success': False
            }
    
    async def get_trading_history(self, symbol: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取交易历史
        
        Args:
            symbol: 交易对符号
            limit: 返回数量限制
            
        Returns:
            交易历史列表
        """
        try:
            params = {'limit': str(limit)}
            if symbol:
                params['symbol'] = symbol
            
            result = await self._make_request('GET', '/api/spot/v1/trade/fills', params=params)
            return result.get('data', [])
            
        except Exception as e:
            bitget_logger.error(f"获取交易历史失败: {e}")
            return []
    
    async def test_connection(self) -> Dict[str, Any]:
        """
        测试API连接
        
        Returns:
            连接测试结果
        """
        try:
            result = await self._make_request('GET', '/api/spot/v1/public/time')
            server_time = result.get('data')
            
            return {
                'success': True,
                'message': 'API连接正常',
                'server_time': server_time,
                'local_time': int(time.time() * 1000)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取合约持仓信息
        
        Args:
            symbol: 交易对符号，为None时获取所有持仓
            
        Returns:
            持仓信息列表
        """
        try:
            params = {'productType': 'UMCBL'}
            if symbol:
                params['symbol'] = symbol
            
            result = await self._make_request('GET', '/api/mix/v1/position/allPosition', params=params)
            positions = result.get('data', [])
            
            bitget_logger.info(f"持仓API返回: {len(positions)} 条记录")
            
            # 调试：打印所有持仓信息
            for i, pos in enumerate(positions):
                bitget_logger.info(f"持仓{i+1}: {pos}")
            
            # 过滤出有持仓量的记录
            active_positions = []
            for pos in positions:
                # 检查多个可能的持仓量字段
                size = safe_float(pos.get('size', 0))
                total = safe_float(pos.get('total', 0))
                available = safe_float(pos.get('available', 0))
                
                bitget_logger.info(f"检查持仓: symbol={pos.get('symbol')}, size={size}, total={total}, available={available}")
                
                if size > 0 or total > 0:
                    active_positions.append(pos)
            
            bitget_logger.info(f"获取到 {len(active_positions)} 个活跃持仓")
            return active_positions
            
        except Exception as e:
            bitget_logger.error(f"获取持仓信息失败: {e}")
            return []
    
    async def close_position_partial(self, symbol: str, percentage: float = 50.0) -> Optional[Dict[str, Any]]:
        """
        部分平仓
        
        Args:
            symbol: 交易对符号
            percentage: 平仓百分比 (0-100)
            
        Returns:
            平仓订单信息
        """
        try:
            # 获取当前持仓
            positions = await self.get_positions(symbol)
            if not positions:
                bitget_logger.warning(f"未找到 {symbol} 的持仓")
                return None
            
            position = positions[0]  # 取第一个匹配的持仓
            # Bitget API中，size字段可能为0，真实持仓数量在total字段
            current_size = safe_float(position.get('total', 0))
            if current_size <= 0:
                current_size = safe_float(position.get('size', 0))
            
            side = position.get('holdSide')  # long 或 short (Bitget使用holdSide)
            
            if current_size <= 0:
                bitget_logger.warning(f"{symbol} 当前持仓为空")
                return None
            
            # 计算平仓数量
            close_size = current_size * (percentage / 100.0)
            close_size = round(close_size, 8)  # 保留8位小数
            
            bitget_logger.info(f"准备平仓 {symbol}: 当前持仓={current_size}, 平仓比例={percentage}%, 平仓数量={close_size}, 方向={side}")
            
            # 确定平仓方向 (Bitget合约平仓方向)
            close_side = "close_long" if side == "long" else "close_short"
            
            # 生成订单ID
            client_order_id = generate_order_id(symbol, f"close_{percentage}pct")
            
            # 下平仓订单
            order_data = {
                'symbol': symbol,
                'side': close_side,
                'orderType': 'market',
                'size': str(close_size),
                'clientOrderId': client_order_id,
                'productType': 'UMCBL',
                'marginCoin': 'USDT',
                'marginMode': 'crossed'
            }
            
            result = await self._make_request('POST', '/api/mix/v1/order/placeOrder', data=order_data)
            order_info = result.get('data')
            
            if order_info:
                bitget_logger.info(f"部分平仓订单已下达: {percentage}% - 订单ID: {order_info.get('orderId')}")
                bitget_logger.log_order_placed(
                    order_info.get('orderId'),
                    symbol,
                    close_side,
                    close_size
                )
            
            return order_info
            
        except Exception as e:
            bitget_logger.error(f"部分平仓失败: {e}")
            raise
    
    async def set_break_even_stop_loss(self, symbol: str, entry_price: float) -> Optional[Dict[str, Any]]:
        """
        设置保本止损（止损价格设为开仓价格）
        
        Args:
            symbol: 交易对符号
            entry_price: 开仓价格（保本价格）
            
        Returns:
            止损订单信息
        """
        try:
            # 获取当前持仓
            positions = await self.get_positions(symbol)
            if not positions:
                bitget_logger.warning(f"未找到 {symbol} 的持仓")
                return None
            
            position = positions[0]
            # Bitget API中，size字段可能为0，真实持仓数量在total字段
            current_size = safe_float(position.get('total', 0))
            if current_size <= 0:
                current_size = safe_float(position.get('size', 0))
            
            side = position.get('holdSide')  # long 或 short (Bitget使用holdSide)
            
            if current_size <= 0:
                bitget_logger.warning(f"{symbol} 当前持仓为空")
                return None
            
            # 确定止损方向 (Bitget合约平仓方向)
            stop_side = "close_long" if side == "long" else "close_short"
            
            # 生成订单ID
            client_order_id = generate_order_id(symbol, "break_even_sl")
            
            # 价格精度处理 - Bitget要求价格是0.0001的倍数
            rounded_entry_price = round(entry_price, 4)
            
            bitget_logger.info(f"设置保本止损 {symbol}: 持仓={current_size}, 保本价格={rounded_entry_price}, 方向={side}")
            
            # 下止损订单 - 使用市价止损单
            # 对于多头持仓，当价格跌至保本价时触发市价卖出
            # 对于空头持仓，当价格涨至保本价时触发市价买入
            trigger_price = rounded_entry_price
            
            # 根据持仓方向设置触发条件
            if side == "long":
                # 多头持仓：价格跌破保本价时触发止损
                plan_type = "normal_plan"  # 普通计划委托
                trigger_type = "fill_price"  # 最新价触发
                size_type = "market"  # 市价
            else:
                # 空头持仓：价格突破保本价时触发止损
                plan_type = "normal_plan"
                trigger_type = "fill_price"
                size_type = "market"
            
            bitget_logger.info(f"设置止损订单: 触发价格={trigger_price}, 触发类型={trigger_type}")
            
            # 使用计划委托API设置止损
            order_data = {
                'symbol': symbol,
                'side': stop_side,
                'orderType': 'market',  # 市价单
                'size': str(current_size),
                'triggerPrice': str(trigger_price),  # 触发价格
                'triggerType': trigger_type,  # 触发类型
                'clientOrderId': client_order_id,
                'productType': 'UMCBL',
                'planType': plan_type,
                'marginCoin': 'USDT',
                'marginMode': 'crossed'
            }
            
            # 使用计划委托API下单（止损订单）
            result = await self._make_request('POST', '/api/mix/v1/plan/placePlan', data=order_data)
            order_info = result.get('data')
            
            if order_info:
                bitget_logger.info(f"保本止损计划委托已设置: 触发价格={trigger_price} - 订单ID: {order_info.get('orderId')}")
                bitget_logger.log_order_placed(
                    order_info.get('orderId'),
                    symbol,
                    stop_side,
                    current_size
                )
            
            return order_info
            
        except Exception as e:
            bitget_logger.error(f"设置保本止损失败: {e}")
            raise

    async def set_auto_stop_loss(self, symbol: str, stop_loss_price: float, quantity: float, side: str) -> Optional[Dict[str, Any]]:
        """
        设置自动止损订单（亏损7U时自动平仓）
        
        Args:
            symbol: 交易对符号
            stop_loss_price: 止损价格
            quantity: 持仓数量
            side: 开仓方向 ("buy" 或 "sell")
            
        Returns:
            止损订单信息
        """
        try:
            # 确定平仓方向
            close_side = "close_long" if side == "buy" else "close_short"
            
            # 生成订单ID
            client_order_id = generate_order_id(symbol, "auto_sl")
            
            # 价格精度处理
            rounded_stop_price = round(stop_loss_price, 4)
            
            bitget_logger.info(f"设置自动止损 {symbol}: 数量={quantity}, 止损价格={rounded_stop_price}, 方向={close_side}")
            
            # 根据开仓方向设置触发条件
            if side == "buy":  # 多头持仓
                # 价格跌破止损价时触发
                plan_type = "normal_plan"
                trigger_type = "fill_price"
            else:  # 空头持仓
                # 价格突破止损价时触发
                plan_type = "normal_plan"
                trigger_type = "fill_price"
            
            # 使用计划委托API设置止损
            order_data = {
                'symbol': symbol,
                'side': close_side,
                'orderType': 'market',  # 市价单
                'size': str(quantity),
                'triggerPrice': str(rounded_stop_price),  # 触发价格
                'triggerType': trigger_type,  # 触发类型
                'clientOrderId': client_order_id,
                'productType': 'UMCBL',
                'planType': plan_type,
                'marginCoin': 'USDT',
                'marginMode': 'crossed'
            }
            
            result = await self._make_request('POST', '/api/mix/v1/plan/placePlan', data=order_data)
            order_info = result.get('data')
            
            if order_info:
                bitget_logger.info(f"自动止损计划委托已设置: 触发价格={rounded_stop_price} - 订单ID: {order_info.get('orderId')}")
                bitget_logger.log_order_placed(
                    order_info.get('orderId'),
                    symbol,
                    close_side,
                    quantity
                )
            
            return order_info
            
        except Exception as e:
            bitget_logger.error(f"设置自动止损失败: {e}")
            import traceback
            bitget_logger.error(f"详细错误信息: {traceback.format_exc()}")
            return None  # 返回None而不是抛出异常

    async def handle_first_take_profit(self, signal: TradingSignal, recent_trades: List[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        处理第一止盈信号：50%平仓 + 设置保本止损
        
        Args:
            signal: 第一止盈信号
            recent_trades: 最近的交易记录，用于推断币种和开仓价格
            
        Returns:
            处理结果
        """
        try:
            bitget_logger.info(f"处理第一止盈信号: 目标价格={signal.take_profit}")
            
            # 等待一段时间，让订单成交和持仓更新
            bitget_logger.info("等待持仓更新...")
            await asyncio.sleep(3)
            
            # 如果信号没有币种信息，需要从当前持仓推断
            target_symbol = signal.symbol
            if not target_symbol:
                # 获取所有活跃持仓
                all_positions = await self.get_positions()
                if not all_positions:
                    bitget_logger.warning("未找到任何持仓，无法执行第一止盈")
                    return None
                
                # 取最新的持仓（假设是刚开的仓）
                target_symbol = all_positions[0].get('symbol')
                bitget_logger.info(f"从当前持仓推断币种: {target_symbol}")
            
            # 确保使用合约格式
            if target_symbol.endswith('USDT') and not target_symbol.endswith('_UMCBL'):
                target_symbol = f"{target_symbol}_UMCBL"
            
            # 获取该币种的持仓信息
            positions = await self.get_positions(target_symbol)
            if not positions:
                bitget_logger.warning(f"未找到 {target_symbol} 的持仓")
                return None
            
            position = positions[0]
            entry_price = safe_float(position.get('averageOpenPrice', 0))
            if entry_price <= 0:
                # 如果无法获取开仓价格，从recent_trades推断
                if recent_trades:
                    for trade in recent_trades:
                        if trade.get('symbol') == target_symbol:
                            entry_price = safe_float(trade.get('price', 0))
                            break
            
            if entry_price <= 0:
                bitget_logger.error(f"无法获取 {target_symbol} 的开仓价格")
                return None
            
            bitget_logger.info(f"开仓价格: {entry_price}")
            
            # 第一步：50%平仓
            close_result = await self.close_position_partial(target_symbol, 50.0)
            if not close_result:
                bitget_logger.error("50%平仓失败")
                return None
            
            # 等待平仓完成
            await asyncio.sleep(2)
            
            # 第二步：设置保本止损
            stop_loss_result = await self.set_break_even_stop_loss(target_symbol, entry_price)
            
            result = {
                'signal': signal.to_dict(),
                'target_symbol': target_symbol,
                'entry_price': entry_price,
                'close_50_percent': close_result,
                'break_even_stop_loss': stop_loss_result,
                'executed_at': datetime.now(timezone.utc).isoformat(),
                'success': True
            }
            
            bitget_logger.info(f"第一止盈处理完成: 50%平仓 + 保本止损设置")
            return result
            
        except Exception as e:
            bitget_logger.error(f"处理第一止盈失败: {e}")
            raise

    def get_status(self) -> Dict[str, Any]:
        """获取客户端状态"""
        return {
            'initialized': self.session is not None,
            'api_key_configured': bool(self.api_key),
            'sandbox_mode': self.sandbox,
            'base_url': self.base_url,
            'request_count': self.request_count
        }
