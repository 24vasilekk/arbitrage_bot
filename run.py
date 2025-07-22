#!/usr/bin/env python3
"""
Арбитражный бот для торговли между MEXC Futures и DEX биржами
Автор: 24vasilekk
Email: 24vasilekk@gmail.com

Запуск:
python run.py --test-mode
python run.py --test-mode --symbols "BTC/USDT,ETH/USDT"
"""

import argparse
import asyncio
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Добавляем корневую папку в PYTHONPATH
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Загрузка переменных окружения
load_dotenv()

def parse_args():
    parser = argparse.ArgumentParser(description='Арбитражный бот MEXC vs DEX')
    parser.add_argument('--test-mode', action='store_true', 
                       help='Запуск в тестовом режиме (без реальных сделок)')
    parser.add_argument('--symbols', 
                       help='Символы через запятую (например: BTC/USDT,ETH/USDT)')
    parser.add_argument('--log-level', default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'])
    return parser.parse_args()

async def main():
    args = parse_args()
    
    print("🚀 Арбитражный бот MEXC vs DEX")
    print("=" * 50)
    
    # Проверка API ключей
    if not os.getenv('MEXC_API_KEY'):
        print("❌ ОШИБКА: MEXC_API_KEY не найден в .env файле")
        print("💡 Создайте .env файл из .env.example и добавьте ваши API ключи")
        return
        
    if not os.getenv('MEXC_SECRET'):
        print("❌ ОШИБКА: MEXC_SECRET не найден в .env файле")
        return
    
    # Режим работы
    if args.test_mode or os.getenv('TEST_MODE', 'true').lower() == 'true':
        print("📋 Режим: ТЕСТОВЫЙ (без реальных сделок)")
    else:
        print("⚠️  Режим: ПРОДАКШН (реальные сделки!)")
        confirmation = input("Вы уверены? (введите 'YES'): ")
        if confirmation != 'YES':
            print("❌ Отменено пользователем")
            return
    
    # Символы для мониторинга
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(',')]
        print(f"📈 Символы: {symbols}")
    else:
        symbols = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT']  # По умолчанию
        print(f"📈 Символы по умолчанию: {symbols}")
    
    print("✅ API ключи найдены")
    print("🔄 Запуск тестирования подключений...")
    
    try:
        # Пока что просто тестируем подключения
        # Позже здесь будет запуск полноценного бота
        from test_connections import test_all_connections
        await test_all_connections()
        
        print("\n✅ Все тесты прошли успешно!")
        print("🎯 Бот готов к работе")
        
        # TODO: Здесь будет запуск основного бота
        # from src.main import ArbitrageBot
        # bot = ArbitrageBot(symbols=symbols, test_mode=args.test_mode)
        # await bot.start()
        
    except KeyboardInterrupt:
        print("\n⏹️  Остановка бота пользователем...")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        print("🔧 Проверьте настройки API и интернет-соединение")

if __name__ == "__main__":
    # Создание необходимых папок
    os.makedirs('logs', exist_ok=True)
    os.makedirs('data', exist_ok=True)
    os.makedirs('src/exchanges', exist_ok=True)
    os.makedirs('src/utils', exist_ok=True)
    os.makedirs('config', exist_ok=True)
    
    # Запуск
    asyncio.run(main())