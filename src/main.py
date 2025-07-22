"""
Основной модуль арбитражного бота MEXC vs DEX
Автор: 24vasilekk (24vasilekk@gmail.com)
"""

import asyncio
import signal
import sys
from typing import List, Optional
from datetime import datetime

from .config import config
from .strategies.arbitrage_strategy import ArbitrageStrategy
from .utils.logger import get_logger, get_trade_logger

class ArbitrageBot:
    """Главный класс арбитражного бота"""
    
    def __init__(self, symbols: Optional[List[str]] = None, test_mode: Optional[bool] = None):
        self.logger = get_logger("arbitrage_bot")
        self.trade_logger = get_trade_logger("arbitrage_bot")
        
        # Настройки бота
        self.symbols = symbols or config.symbols
        self.test_mode = test_mode if test_mode is not None else config.test_mode
        
        # Стратегия
        self.strategy = ArbitrageStrategy()
        
        # Флаг для корректного завершения
        self.running = False
        
        # Настройка обработчика сигналов
        self._setup_signal_handlers()
        
    def _setup_signal_handlers(self):
        """Настройка обработчиков сигналов для корректного завершения"""
        def signal_handler(signum, frame):
            self.logger.info(f"🛑 Получен сигнал {signum}, завершение работы...")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def start(self):
        """Запуск арбитражного бота"""
        self.logger.info("🚀 Запуск арбитражного бота MEXC vs DEX")
        self.logger.info("=" * 60)
        
        # Валидация конфигурации
        if not config.validate():
            self.logger.error("❌ Некорректная конфигурация, завершение работы")
            return
        
        # Вывод настроек
        await self._print_settings()
        
        # Проверка подключений
        if not await self._test_connections():
            self.logger.error("❌ Не удалось подключиться к биржам")
            return
        
        # Запуск основного цикла
        self.running = True
        
        try:
            # Запускаем стратегию
            await self.strategy.start()
            
        except KeyboardInterrupt:
            self.logger.info("⏹️ Остановка бота пользователем")
            
        except Exception as e:
            self.logger.error(f"❌ Критическая ошибка: {e}")
            
        finally:
            self.running = False
            await self._shutdown()
    
    async def _print_settings(self):
        """Вывод текущих настроек бота"""
        mode = "🧪 ТЕСТОВЫЙ" if self.test_mode else "⚠️ ПРОДАКШН"
        
        self.logger.info(f"⚙️ Настройки бота:")
        self.logger.info(f"   Режим: {mode}")
        self.logger.info(f"   Символов для мониторинга: {len(self.symbols)}")
        self.logger.info(f"   Минимальный спред: {config.min_spread_percent}%")
        self.logger.info(f"   Целевой спред: {config.target_spread_percent}%")
        self.logger.info(f"   Максимальный размер позиции: ${config.max_position_size}")
        self.logger.info(f"   Максимальные дневные потери: ${config.max_daily_loss}")
        self.logger.info(f"   Интервал обновления: {config.price_update_interval}с")
        
        if len(self.symbols) <= 10:
            self.logger.info(f"   Символы: {', '.join(self.symbols)}")
        else:
            self.logger.info(f"   Символы: {', '.join(self.symbols[:10])}... и еще {len(self.symbols)-10}")
    
    async def _test_connections(self) -> bool:
        """Тестирование подключений к биржам"""
        self.logger.info("🔄 Тестирование подключений...")
        
        try:
            # Тест MEXC
            mexc_balance = await self.strategy.mexc_client.get_balance()
            if mexc_balance:
                usdt_balance = mexc_balance.get('USDT', {}).get('total', 0)
                self.logger.info(f"✅ MEXC подключен | Баланс USDT: ${usdt_balance:.2f}")
            else:
                self.logger.error("❌ Не удалось подключиться к MEXC")
                return False
            
            # Тест DEX источников
            await self.strategy.dex_client.__aenter__()
            test_price = await self.strategy.dex_client.get_dex_price('BTC/USDT')
            
            if test_price:
                self.logger.info(f"✅ DEX источники подключены | BTC: ${test_price['price']:.2f}")
            else:
                self.logger.error("❌ Не удалось подключиться к DEX источникам")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка тестирования подключений: {e}")
            return False
    
    async def _shutdown(self):
        """Корректное завершение работы бота"""
        self.logger.info("🛑 Завершение работы арбитражного бота...")
        
        try:
            # Получаем финальную статистику
            status = self.strategy.get_status()
            
            # Выводим итоговую статистику
            self.logger.info("📊 ФИНАЛЬНАЯ СТАТИСТИКА:")
            self.logger.info("=" * 50)
            self.logger.info(f"   Всего сделок: {status['total_trades']}")
            self.logger.info(f"   Прибыльных сделок: {status['winning_trades']}")
            self.logger.info(f"   Процент прибыльности: {status['win_rate']:.1f}%")
            self.logger.info(f"   Общий PnL: ${status['total_pnl']:.2f}")
            self.logger.info(f"   PnL за день: ${status['daily_pnl']:.2f}")
            self.logger.info(f"   Активных позиций: {status['active_positions']}")
            self.logger.info(f"   Найдено возможностей: {status['opportunities_found']}")
            
            # Сохраняем статистику в файл
            await self._save_session_stats(status)
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка при завершении: {e}")
        
        self.logger.info("✅ Арбитражный бот успешно завершен")
    
    async def _save_session_stats(self, status: dict):
        """Сохранение статистики сессии"""
        try:
            from pathlib import Path
            import json
            
            # Создаем папку для статистики
            stats_dir = Path("logs/stats")
            stats_dir.mkdir(exist_ok=True)
            
            # Формируем данные сессии
            session_data = {
                'timestamp': datetime.now().isoformat(),
                'test_mode': self.test_mode,
                'symbols': self.symbols,
                'config': {
                    'min_spread': config.min_spread_percent,
                    'target_spread': config.target_spread_percent,
                    'max_position_size': config.max_position_size,
                    'max_daily_loss': config.max_daily_loss
                },
                'statistics': status,
                'opportunities_count': len(self.strategy.opportunities_history)
            }
            
            # Сохраняем в файл
            session_file = stats_dir / f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"💾 Статистика сессии сохранена: {session_file}")
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка сохранения статистики: {e}")
    
    def get_status(self) -> dict:
        """Получение текущего статуса бота"""
        base_status = {
            'running': self.running,
            'test_mode': self.test_mode,
            'symbols_count': len(self.symbols),
            'start_time': datetime.now().isoformat()
        }
        
        if hasattr(self, 'strategy'):
            strategy_status = self.strategy.get_status()
            base_status.update(strategy_status)
        
        return base_status
    
    async def stop(self):
        """Остановка бота"""
        self.logger.info("🛑 Получен запрос на остановку бота")
        self.running = False

# Точка входа для использования как модуль
async def main():
    """Основная функция для запуска бота"""
    bot = ArbitrageBot()
    await bot.start()

if __name__ == "__main__":
    # Запуск бота напрямую
    asyncio.run(main())