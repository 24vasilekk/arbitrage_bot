"""
Модуль логирования для арбитражного бота
Автор: 24vasilekk
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler
from colorama import Fore, Style, init

# Инициализация цветного вывода
init()

class ColoredFormatter(logging.Formatter):
    """Форматтер с цветным выводом для консоли"""
    
    COLORS = {
        'DEBUG': Fore.CYAN,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Style.BRIGHT
    }
    
    def format(self, record):
        # Добавляем цвет к уровню логирования
        levelname = record.levelname
        if levelname in self.COLORS:
            levelname_color = f"{self.COLORS[levelname]}{levelname}{Style.RESET_ALL}"
            record.levelname = levelname_color
        
        return super().format(record)

class ArbitrageLogger:
    """Класс для настройки логирования арбитражного бота"""
    
    def __init__(self, name: str = "arbitrage_bot"):
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Очистка предыдущих обработчиков
        self.logger.handlers.clear()
        
        self._setup_console_handler()
        self._setup_file_handler()
        self._setup_trade_handler()
        
    def _setup_console_handler(self):
        """Настройка вывода в консоль"""
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Цветной форматтер для консоли
        console_formatter = ColoredFormatter(
            '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        
        self.logger.addHandler(console_handler)
    
    def _setup_file_handler(self):
        """Настройка записи в файл"""
        # Создание папки для логов
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        
        # Основной файл логов с ротацией
        log_file = logs_dir / "arbitrage_bot.log"
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        
        # Подробный форматтер для файла
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        
        self.logger.addHandler(file_handler)
    
    def _setup_trade_handler(self):
        """Настройка отдельного лога для торговых операций"""
        logs_dir = Path("logs")
        
        # Отдельный файл для торговых операций
        trade_log_file = logs_dir / "trades.log"
        trade_handler = RotatingFileHandler(
            trade_log_file,
            maxBytes=5*1024*1024,  # 5MB
            backupCount=10,
            encoding='utf-8'
        )
        trade_handler.setLevel(logging.INFO)
        
        # Специальный форматтер для торговых операций
        trade_formatter = logging.Formatter(
            '%(asctime)s | TRADE | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        trade_handler.setFormatter(trade_formatter)
        
        # Создаем отдельный логгер для торговых операций
        self.trade_logger = logging.getLogger(f"{self.name}_trades")
        self.trade_logger.setLevel(logging.INFO)
        self.trade_logger.handlers.clear()
        self.trade_logger.addHandler(trade_handler)
        self.trade_logger.addHandler(console_handler := logging.StreamHandler())
        
        # Консольный вывод для торговых операций с особым форматом
        console_formatter = ColoredFormatter(
            f'%(asctime)s | {Fore.MAGENTA}TRADE{Style.RESET_ALL} | %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
    
    def get_logger(self) -> logging.Logger:
        """Получить основной логгер"""
        return self.logger
    
    def get_trade_logger(self) -> logging.Logger:
        """Получить логгер для торговых операций"""
        return self.trade_logger
    
    def log_opportunity(self, symbol: str, mexc_price: float, dex_price: float, 
                       spread: float, direction: str):
        """Логирование найденной арбитражной возможности"""
        message = (f"🎯 ВОЗМОЖНОСТЬ | {symbol} | "
                  f"MEXC: ${mexc_price:.4f} | DEX: ${dex_price:.4f} | "
                  f"Спред: {spread:.2f}% | Направление: {direction}")
        
        self.logger.info(message)
    
    def log_trade_open(self, symbol: str, side: str, size: float, price: float, 
                      spread: float):
        """Логирование открытия сделки"""
        message = (f"📈 ОТКРЫТИЕ | {symbol} | {side} | "
                  f"Размер: {size} | Цена: ${price:.4f} | Спред: {spread:.2f}%")
        
        self.trade_logger.info(message)
    
    def log_trade_close(self, symbol: str, side: str, size: float, 
                       open_price: float, close_price: float, pnl: float):
        """Логирование закрытия сделки"""
        pnl_emoji = "💰" if pnl >= 0 else "💸"
        message = (f"📉 ЗАКРЫТИЕ | {symbol} | {side} | "
                  f"Размер: {size} | Вход: ${open_price:.4f} | "
                  f"Выход: ${close_price:.4f} | PnL: {pnl_emoji}${pnl:.2f}")
        
        self.trade_logger.info(message)
    
    def log_error(self, error: Exception, context: str = ""):
        """Логирование ошибок с контекстом"""
        message = f"❌ ОШИБКА"
        if context:
            message += f" [{context}]"
        message += f": {str(error)}"
        
        self.logger.error(message, exc_info=True)
    
    def log_performance(self, total_trades: int, winning_trades: int, 
                       total_pnl: float, daily_pnl: float):
        """Логирование статистики производительности"""
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        message = (f"📊 СТАТИСТИКА | Всего сделок: {total_trades} | "
                  f"Прибыльных: {winning_trades} ({win_rate:.1f}%) | "
                  f"Общий PnL: ${total_pnl:.2f} | За день: ${daily_pnl:.2f}")
        
        self.logger.info(message)

# Глобальный логгер для использования в проекте
def get_logger(name: str = "arbitrage_bot") -> logging.Logger:
    """Получить настроенный логгер"""
    if name not in logging.Logger.manager.loggerDict:
        ArbitrageLogger(name)
    
    return logging.getLogger(name)

def get_trade_logger(name: str = "arbitrage_bot") -> logging.Logger:
    """Получить логгер для торговых операций"""
    if f"{name}_trades" not in logging.Logger.manager.loggerDict:
        ArbitrageLogger(name)
    
    return logging.getLogger(f"{name}_trades")

# Создание основного логгера при импорте модуля
main_logger = ArbitrageLogger()
logger = main_logger.get_logger()
trade_logger = main_logger.get_trade_logger()