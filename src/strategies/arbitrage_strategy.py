"""
Арбитражная стратегия MEXC Futures vs DEX
Автор: 24vasilekk
"""

import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

from ..exchanges.mexc_client import MEXCClient
from ..exchanges.dex_client import DEXClient
from ..utils.logger import get_logger, get_trade_logger
from ..config import config

@dataclass
class ArbitrageOpportunity:
    """Класс для представления арбитражной возможности"""
    symbol: str
    mexc_price: float
    dex_price: float
    spread_percent: float
    direction: str  # 'long' или 'short' на MEXC
    potential_profit: float
    timestamp: datetime

@dataclass
class ActivePosition:
    """Класс для отслеживания активных позиций"""
    symbol: str
    side: str
    size: float
    entry_price: float
    entry_spread: float
    entry_time: datetime
    target_spread: float
    stop_loss_price: float
    take_profit_price: float

class ArbitrageStrategy:
    """Основная стратегия арбитража между MEXC и DEX"""
    
    def __init__(self):
        self.logger = get_logger("arbitrage_strategy")
        self.trade_logger = get_trade_logger("arbitrage_strategy")
        
        # Клиенты для бирж
        self.mexc_client = MEXCClient()
        self.dex_client = DEXClient()
        
        # Отслеживание позиций и статистики
        self.active_positions: Dict[str, ActivePosition] = {}
        self.opportunities_history: List[ArbitrageOpportunity] = []
        
        # Статистика
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl = 0.0
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.last_daily_reset = datetime.now().date()
        
        # Лимиты риск-менеджмента
        self.daily_loss_limit = config.max_daily_loss
        self.max_positions = config.max_positions
        
    async def start(self):
        """Запуск стратегии арбитража"""
        self.logger.info("🚀 Запуск арбитражной стратегии")
        
        try:
            # Инициализация DEX клиента
            await self.dex_client.__aenter__()
            
            # Основной цикл мониторинга
            while True:
                await self._monitor_markets()
                await self._manage_positions()
                await self._update_statistics()
                
                # Интервал между итерациями
                await asyncio.sleep(config.price_update_interval)
                
        except KeyboardInterrupt:
            self.logger.info("⏹️ Остановка стратегии пользователем")
        except Exception as e:
            self.logger.error(f"❌ Критическая ошибка стратегии: {e}")
        finally:
            await self._cleanup()
    
    async def _monitor_markets(self):
        """Мониторинг рынков и поиск возможностей"""
        symbols = config.symbols
        
        try:
            # Получаем цены параллельно
            mexc_prices_task = self.mexc_client.get_multiple_tickers(symbols)
            dex_prices_task = self.dex_client.get_multiple_dex_prices(symbols)
            
            mexc_prices, dex_prices = await asyncio.gather(
                mexc_prices_task, dex_prices_task
            )
            
            # Анализируем возможности для каждого символа
            for symbol in symbols:
                await self._analyze_symbol(symbol, mexc_prices, dex_prices)
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка мониторинга рынков: {e}")
    
    async def _analyze_symbol(self, symbol: str, mexc_prices: Dict, dex_prices: Dict):
        """Анализ возможности арбитража для конкретного символа"""
        if symbol not in mexc_prices or symbol not in dex_prices:
            return
        
        mexc_data = mexc_prices[symbol]
        dex_data = dex_prices[symbol]
        
        mexc_price = mexc_data['price']
        dex_price = dex_data['price']
        
        # Расчет спреда
        spread_percent = abs(mexc_price - dex_price) / mexc_price * 100
        
        # Определение направления арбитража
        if mexc_price < dex_price:
            direction = 'long'  # Покупаем на MEXC (дешевле)
        else:
            direction = 'short'  # Продаем на MEXC (дороже)
        
        # Проверяем, достаточен ли спред
        if spread_percent >= config.min_spread_percent:
            opportunity = ArbitrageOpportunity(
                symbol=symbol,
                mexc_price=mexc_price,
                dex_price=dex_price,
                spread_percent=spread_percent,
                direction=direction,
                potential_profit=spread_percent - 0.5,  # Учитываем комиссии
                timestamp=datetime.now()
            )
            
            # Логируем возможность
            self.logger.info(f"🎯 ВОЗМОЖНОСТЬ | {symbol} | "
                           f"MEXC: ${mexc_price:.4f} | DEX: ${dex_price:.4f} | "
                           f"Спред: {spread_percent:.2f}% | Направление: {direction}")
            
            # Сохраняем в историю
            self.opportunities_history.append(opportunity)
            
            # Проверяем возможность входа в позицию
            await self._consider_entry(opportunity)
    
    async def _consider_entry(self, opportunity: ArbitrageOpportunity):
        """Рассмотрение входа в позицию"""
        symbol = opportunity.symbol
        
        # Проверки перед входом
        if not await self._can_open_position(symbol):
            return
        
        # Если уже есть позиция по этому символу
        if symbol in self.active_positions:
            self.logger.debug(f"⚠️ Позиция по {symbol} уже открыта")
            return
        
        # Проверка дневных лимитов
        if abs(self.daily_pnl) >= self.daily_loss_limit:
            self.logger.warning(f"⚠️ Достигнут дневной лимит потерь: ${abs(self.daily_pnl):.2f}")
            return
        
        # Расчет размера позиции
        position_size = await self.mexc_client.calculate_position_size(
            symbol, opportunity.mexc_price, risk_percent=10.0
        )
        
        if position_size <= 0:
            self.logger.warning(f"⚠️ Недостаточно средств для позиции {symbol}")
            return
        
        # Открываем позицию
        await self._open_position(opportunity, position_size)
    
    async def _can_open_position(self, symbol: str) -> bool:
        """Проверка возможности открытия новой позиции"""
        # Проверяем количество активных позиций
        if len(self.active_positions) >= self.max_positions:
            self.logger.debug(f"⚠️ Достигнуто максимальное количество позиций: {self.max_positions}")
            return False
        
        # Проверяем баланс
        balance = await self.mexc_client.get_balance()
        available_balance = balance.get('USDT', {}).get('free', 0)
        
        if available_balance < 10:  # Минимум $10
            self.logger.warning(f"⚠️ Недостаточно баланса: ${available_balance:.2f}")
            return False
        
        return True
    
    async def _open_position(self, opportunity: ArbitrageOpportunity, size: float):
        """Открытие арбитражной позиции"""
        symbol = opportunity.symbol
        side = opportunity.direction  # 'long' или 'short'
        
        self.logger.info(f"📈 Открытие позиции {symbol} | {side.upper()} | "
                        f"Размер: {size} | Спред: {opportunity.spread_percent:.2f}%")
        
        try:
            # Открываем позицию на MEXC
            order = await self.mexc_client.create_market_order(
                symbol, 'buy' if side == 'long' else 'sell', size
            )
            
            if not order:
                self.logger.error(f"❌ Не удалось открыть позицию {symbol}")
                return
            
            # Рассчитываем уровни стоп-лосса и тейк-профита
            entry_price = order['price'] or opportunity.mexc_price
            
            if side == 'long':
                stop_loss_price = entry_price * (1 - config.stop_loss_percent / 100)
                take_profit_price = entry_price * (1 + config.take_profit_percent / 100)
            else:
                stop_loss_price = entry_price * (1 + config.stop_loss_percent / 100)
                take_profit_price = entry_price * (1 - config.take_profit_percent / 100)
            
            # Создаем запись об активной позиции
            position = ActivePosition(
                symbol=symbol,
                side=side,
                size=size,
                entry_price=entry_price,
                entry_spread=opportunity.spread_percent,
                entry_time=datetime.now(),
                target_spread=config.target_spread_percent,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price
            )
            
            self.active_positions[symbol] = position
            
            # Логируем открытие
            self.trade_logger.info(f"📈 ОТКРЫТИЕ | {symbol} | {side.upper()} | "
                                 f"Размер: {size} | Цена: ${entry_price:.4f} | "
                                 f"Спред: {opportunity.spread_percent:.2f}%")
            
            self.total_trades += 1
            self.daily_trades += 1
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка открытия позиции {symbol}: {e}")
    
    async def _manage_positions(self):
        """Управление активными позициями"""
        if not self.active_positions:
            return
        
        symbols_to_close = []
        
        for symbol, position in self.active_positions.items():
            should_close = await self._should_close_position(position)
            
            if should_close:
                symbols_to_close.append(symbol)
        
        # Закрываем позиции
        for symbol in symbols_to_close:
            await self._close_position(symbol)
    
    async def _should_close_position(self, position: ActivePosition) -> bool:
        """Проверка условий закрытия позиции"""
        symbol = position.symbol
        
        try:
            # Получаем текущие цены
            mexc_ticker = await self.mexc_client.get_ticker(symbol)
            dex_data = await self.dex_client.get_dex_price(symbol)
            
            if not mexc_ticker or not dex_data:
                return False
            
            current_mexc_price = mexc_ticker['price']
            current_dex_price = dex_data['price']
            
            # Расчет текущего спреда
            current_spread = abs(current_mexc_price - current_dex_price) / current_mexc_price * 100
            
            # Условие 1: Спред сузился до целевого уровня
            if current_spread <= position.target_spread:
                self.logger.info(f"🎯 Целевой спред достигнут для {symbol}: {current_spread:.2f}%")
                return True
            
            # Условие 2: Стоп-лосс
            if position.side == 'long' and current_mexc_price <= position.stop_loss_price:
                self.logger.warning(f"🛑 Стоп-лосс для {symbol}: ${current_mexc_price:.4f}")
                return True
            elif position.side == 'short' and current_mexc_price >= position.stop_loss_price:
                self.logger.warning(f"🛑 Стоп-лосс для {symbol}: ${current_mexc_price:.4f}")
                return True
            
            # Условие 3: Тейк-профит
            if position.side == 'long' and current_mexc_price >= position.take_profit_price:
                self.logger.info(f"💰 Тейк-профит для {symbol}: ${current_mexc_price:.4f}")
                return True
            elif position.side == 'short' and current_mexc_price <= position.take_profit_price:
                self.logger.info(f"💰 Тейк-профит для {symbol}: ${current_mexc_price:.4f}")
                return True
            
            # Условие 4: Максимальное время удержания (1 час)
            max_hold_time = timedelta(hours=1)
            if datetime.now() - position.entry_time > max_hold_time:
                self.logger.warning(f"⏰ Превышено время удержания для {symbol}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка проверки позиции {symbol}: {e}")
            return True  # В случае ошибки лучше закрыть позицию
    
    async def _close_position(self, symbol: str):
        """Закрытие позиции"""
        if symbol not in self.active_positions:
            return
        
        position = self.active_positions[symbol]
        
        self.logger.info(f"📉 Закрытие позиции {symbol} | {position.side.upper()}")
        
        try:
            # Получаем текущую цену для расчета PnL
            ticker = await self.mexc_client.get_ticker(symbol)
            if not ticker:
                self.logger.error(f"❌ Не удалось получить цену для закрытия {symbol}")
                return
            
            current_price = ticker['price']
            
            # Закрываем позицию на MEXC
            success = await self.mexc_client.close_position(symbol)
            
            if success:
                # Расчет PnL
                if position.side == 'long':
                    pnl = (current_price - position.entry_price) * position.size
                else:
                    pnl = (position.entry_price - current_price) * position.size
                
                # Учитываем комиссии (приблизительно)
                fees = position.entry_price * position.size * 0.0004  # 0.04% туда-обратно
                pnl -= fees
                
                # Обновляем статистику
                self.total_pnl += pnl
                self.daily_pnl += pnl
                
                if pnl > 0:
                    self.winning_trades += 1
                
                # Логируем закрытие
                pnl_emoji = "💰" if pnl >= 0 else "💸"
                self.trade_logger.info(f"📉 ЗАКРЫТИЕ | {symbol} | {position.side.upper()} | "
                                     f"Размер: {position.size} | Вход: ${position.entry_price:.4f} | "
                                     f"Выход: ${current_price:.4f} | PnL: {pnl_emoji}${pnl:.2f}")
                
                # Удаляем из активных позиций
                del self.active_positions[symbol]
                
            else:
                self.logger.error(f"❌ Не удалось закрыть позицию {symbol}")
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка закрытия позиции {symbol}: {e}")
    
    async def _update_statistics(self):
        """Обновление статистики"""
        current_date = datetime.now().date()
        
        # Сброс дневной статистики в новый день
        if current_date != self.last_daily_reset:
            self.logger.info(f"📊 Дневная статистика за {self.last_daily_reset}: "
                           f"PnL: ${self.daily_pnl:.2f} | Сделок: {self.daily_trades}")
            
            self.daily_pnl = 0.0
            self.daily_trades = 0
            self.last_daily_reset = current_date
        
        # Логируем статистику каждые 10 минут
        if datetime.now().minute % 10 == 0 and datetime.now().second < 5:
            win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
            
            self.logger.info(f"📊 Статистика | Всего сделок: {self.total_trades} | "
                           f"Прибыльных: {self.winning_trades} ({win_rate:.1f}%) | "
                           f"Общий PnL: ${self.total_pnl:.2f} | За день: ${self.daily_pnl:.2f} | "
                           f"Активных позиций: {len(self.active_positions)}")
    
    async def _cleanup(self):
        """Очистка ресурсов"""
        self.logger.info("🧹 Очистка ресурсов...")
        
        # Закрываем все активные позиции
        if self.active_positions:
            self.logger.info(f"🔄 Закрытие {len(self.active_positions)} активных позиций...")
            symbols = list(self.active_positions.keys())
            for symbol in symbols:
                await self._close_position(symbol)
        
        # Закрываем соединения
        await self.dex_client.close()
        self.mexc_client.close_connection()
        
        self.logger.info("✅ Очистка завершена")
    
    def get_status(self) -> Dict:
        """Получение текущего статуса стратегии"""
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        
        return {
            'active_positions': len(self.active_positions),
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'win_rate': win_rate,
            'total_pnl': self.total_pnl,
            'daily_pnl': self.daily_pnl,
            'daily_trades': self.daily_trades,
            'opportunities_found': len(self.opportunities_history)
        }