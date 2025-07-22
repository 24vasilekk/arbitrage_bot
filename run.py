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
    parser.add_argument('--skip-tests', action='store_true',
                       help='Пропустить тестирование подключений')
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
    test_mode = args.test_mode or os.getenv('TEST_MODE', 'true').lower() == 'true'
    
    if test_mode:
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
        symbols = None  # Используем из конфига
        print(f"📈 Символы: будут загружены из конфигурации")
    
    print("✅ API ключи найдены")
    
    # Тестирование подключений (если не пропущено)
    if not args.skip_tests:
        print("🔄 Запуск тестирования подключений...")
        try:
            from test_connections import test_all_connections
            test_result = await test_all_connections()
            
            if not test_result:
                print("\n❌ Тестирование не прошло. Запуск остановлен.")
                print("💡 Используйте --skip-tests для пропуска тестов")
                return
            
            print("\n✅ Все тесты прошли успешно!")
            
        except Exception as e:
            print(f"\n❌ Ошибка тестирования: {e}")
            print("💡 Используйте --skip-tests для пропуска тестов")
            return
    
    # Запуск основного бота
    print("🎯 Запуск арбитражного бота...")
    
    try:
        from src.main import ArbitrageBot
        
        # Создаем и запускаем бота
        bot = ArbitrageBot(symbols=symbols, test_mode=test_mode)
        await bot.start()
        
    except KeyboardInterrupt:
        print("\n⏹️  Остановка бота пользователем...")
    except ImportError as e:
        print(f"\n❌ Ошибка импорта: {e}")
        print("🔧 Убедитесь, что все файлы на месте и зависимости установлены")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        print("🔧 Проверьте настройки API и интернет-соединение")

if __name__ == "__main__":
    # Создание необходимых папок
    os.makedirs('logs', exist_ok=True)
    os.makedirs('logs/stats', exist_ok=True)
    os.makedirs('data', exist_ok=True)
    
    # Запуск
    asyncio.run(main())