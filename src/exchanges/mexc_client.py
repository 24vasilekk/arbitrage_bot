"""
Клиент для работы с MEXC Futures API
Автор: 24vasilekk
ОБНОВЛЕН: Поддержка плеча, фиксированный размер позиции
"""

import ccxt
import asyncio
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from datetime import datetime, timedelta

from ..utils.logger import get_logger
from ..config import config

class MEXCClient:
    """Клиент для торговли на MEXC Futures с АГРЕССИВНЫМИ настройками"""
    
    def __init__(self):
        self.logger = get_logger("mexc_client")
        self.exchange = None
        self._positions = {}
        self._balance = {}
        self._last_balance_update = None
        
        self._initialize_exchange()
    
    def _initialize_exchange(self):
        """Инициализация подключения к MEXC с плечом"""
        try:
            self.exchange = ccxt.mexc({
                'apiKey': config.mexc_api_key,
                'secret': config.mexc_secret,
                'sandbox': config.test_mode,  # Тестовая сеть в тест-режиме
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'swap',  # Фьючерсы
                    'adjustForTimeDifference': True,
                    'defaultLeverage': config.leverage  # Плечо по умолчанию
                }
            })
            
            # Загрузка рынков
            self.exchange.load_markets()
            self.logger.info(f"✅ MEXC подключен. Рынков: {len(self.exchange.markets)} | Плечо: {config.leverage}x")
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка инициализации MEXC: {e}")
            raise
    
    async def set_leverage(self, symbol: str, leverage: int = None) -> bool:
        """Установка плеча для символа"""
        if leverage is None:
            leverage = config.leverage
            
        try:
            # Устанавливаем плечо для символа
            result = self.exchange.set_leverage(leverage, symbol)
            self.logger.info(f"⚡ Установлено плечо {leverage}x для {symbol}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка установки плеча для {symbol}: {e}")
            return False
    
    async def get_ticker(self, symbol: str) -> Optional[Dict]:
        """Получение тикера для символа"""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return {
                'symbol': symbol,
                'price': float(ticker['last']),
                'bid': float(ticker['bid']) if ticker['bid'] else None,
                'ask': float(ticker['ask']) if ticker['ask'] else None,
                'timestamp': ticker['timestamp']
            }
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка получения тикера {symbol}: {e}")
            return None
    
    async def get_multiple_tickers(self, symbols: List[str]) -> Dict[str, Dict]:
        """Быстрое получение тикеров для нескольких символов"""
        tickers = {}
        
        try:
            # MEXC поддерживает получение всех тикеров одним запросом
            all_tickers = self.exchange.fetch_tickers(symbols)
            
            for symbol, ticker in all_tickers.items():
                if symbol in symbols:
                    tickers[symbol] = {
                        'symbol': symbol,
                        'price': float(ticker['last']),
                        'bid': float(ticker['bid']) if ticker['bid'] else None,
                        'ask': float(ticker['ask']) if ticker['ask'] else None,
                        'timestamp': ticker['timestamp']
                    }
            
            self.logger.debug(f"📊 Получено тикеров: {len(tickers)}")
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка получения тикеров: {e}")
        
        return tickers
    
    async def get_balance(self, force_update: bool = False) -> Dict[str, float]:
        """Получение баланса с кешированием"""
        now = datetime.now()
        
        # Кешируем баланс на 10 секунд для быстрых обновлений
        if (not force_update and self._balance and self._last_balance_update and 
            now - self._last_balance_update < timedelta(seconds=10)):
            return self._balance
        
        try:
            balance = self.exchange.fetch_balance()
            self._balance = {
                'USDT': {
                    'free': float(balance['USDT']['free'] or 0),
                    'used': float(balance['USDT']['used'] or 0),
                    'total': float(balance['USDT']['total'] or 0)
                }
            }
            self._last_balance_update = now
            
            self.logger.debug(f"💰 Баланс USDT: ${self._balance['USDT']['total']:.2f}")
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка получения баланса: {e}")
            
        return self._balance
    
    async def get_positions(self) -> List[Dict]:
        """Получение открытых позиций"""
        try:
            positions = self.exchange.fetch_positions()
            
            # Фильтруем только открытые позиции
            open_positions = []
            for position in positions:
                if position['contracts'] != 0:
                    open_positions.append({
                        'symbol': position['symbol'],
                        'side': position['side'],
                        'size': float(position['contracts']),
                        'entry_price': float(position['entryPrice']),
                        'mark_price': float(position['markPrice']),
                        'unrealized_pnl': float(position['unrealizedPnl']),
                        'percentage': float(position['percentage']),
                        'timestamp': position['timestamp'],
                        'leverage': position.get('leverage', config.leverage)
                    })
            
            self.logger.debug(f"📊 Открытых позиций: {len(open_positions)}")
            return open_positions
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка получения позиций: {e}")
            return []
    
    async def create_market_order(self, symbol: str, side: str, amount: float, 
                                 test_mode: bool = None) -> Optional[Dict]:
        """Создание рыночного ордера с плечом"""
        if test_mode is None:
            test_mode = config.test_mode
        
        # Устанавливаем плечо перед созданием ордера
        if not test_mode:
            await self.set_leverage(symbol, config.leverage)
        
        if test_mode:
            # Симуляция ордера в тест-режиме
            ticker = await self.get_ticker(symbol)
            if not ticker:
                return None
                
            return {
                'id': f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                'symbol': symbol,
                'side': side,
                'amount': amount,
                'price': ticker['price'],
                'status': 'closed',
                'timestamp': datetime.now().timestamp() * 1000,
                'test_mode': True,
                'leverage': config.leverage
            }
        
        try:
            # Реальный ордер с плечом
            order = self.exchange.create_market_order(
                symbol, side, amount,
                params={'leverage': config.leverage}
            )
            
            self.logger.info(f"📈 Ордер создан: {order['id']} | {symbol} | {side} | "
                           f"{amount:.8f} | Плечо: {config.leverage}x")
            
            return {
                'id': order['id'],
                'symbol': order['symbol'],
                'side': order['side'],
                'amount': float(order['amount']),
                'price': float(order['price']) if order['price'] else None,
                'status': order['status'],
                'timestamp': order['timestamp'],
                'test_mode': False,
                'leverage': config.leverage
            }
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка создания ордера: {e}")
            return None
    
    async def close_position(self, symbol: str, test_mode: bool = None) -> bool:
        """Закрытие позиции по символу"""
        if test_mode is None:
            test_mode = config.test_mode
            
        try:
            positions = await self.get_positions()
            position = next((p for p in positions if p['symbol'] == symbol), None)
            
            if not position:
                self.logger.warning(f"⚠️ Позиция {symbol} не найдена")
                return False
            
            # Определяем противоположную сторону для закрытия
            close_side = 'sell' if position['side'] == 'long' else 'buy'
            size = abs(position['size'])
            
            # Закрываем позицию рыночным ордером
            order = await self.create_market_order(symbol, close_side, size, test_mode)
            
            if order:
                self.logger.info(f"📉 Позиция {symbol} закрыта: {order['id']} | "
                               f"Плечо: {config.leverage}x")
                return True
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка закрытия позиции {symbol}: {e}")
            return False
    
    def calculate_fixed_position_size(self, symbol: str, price: float) -> float:
        """Расчет ФИКСИРОВАННОГО размера позиции"""
        try:
            # ФИКСИРОВАННЫЙ размер позиции в USDT
            fixed_size_usd = config.fixed_position_size  # $5.10
            
            # Размер в монетах
            position_size = fixed_size_usd / price
            
            # Округляем до разумного количества знаков
            if position_size > 1:
                position_size = round(position_size, 6)
            else:
                position_size = round(position_size, 8)
            
            self.logger.debug(f"💱 ФИКСИРОВАННЫЙ размер позиции {symbol}: {position_size:.8f} "
                            f"(${fixed_size_usd} при цене ${price:.8f}) | Плечо: {config.leverage}x")
            
            return position_size
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка расчета размера позиции: {e}")
            return 0.0
    
    async def get_trading_fees(self, symbol: str) -> Dict[str, float]:
        """Получение комиссий для символа"""
        try:
            market = self.exchange.markets.get(symbol, {})
            return {
                'maker': market.get('maker', 0.0002),  # 0.02% по умолчанию
                'taker': market.get('taker', 0.0002)   # 0.02% по умолчанию
            }
        except Exception as e:
            self.logger.error(f"❌ Ошибка получения комиссий: {e}")
            return {'maker': 0.0002, 'taker': 0.0002}
    
    async def set_margin_mode(self, symbol: str, margin_mode: str = 'isolated') -> bool:
        """Установка режима маржи"""
        try:
            # Устанавливаем изолированную маржу для безопасности
            result = self.exchange.set_margin_mode(margin_mode, symbol)
            self.logger.info(f"🛡️ Установлен режим маржи {margin_mode} для {symbol}")
            return True
            
        except Exception as e:
            self.logger.warning(f"⚠️ Не удалось установить режим маржи для {symbol}: {e}")
            return False
    
    def close_connection(self):
        """Закрытие соединения"""
        if self.exchange:
            self.exchange.close()
            self.logger.info("🔌 MEXC соединение закрыто")
    
    def __del__(self):
        """Деструктор - автоматическое закрытие соединения"""
        self.close_connection()