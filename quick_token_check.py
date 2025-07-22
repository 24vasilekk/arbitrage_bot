#!/usr/bin/env python3
"""
Быстрая проверка соответствия конкретных токенов
Автор: 24vasilekk
Путь: quick_token_check.py (в корне проекта)

Использование:
python quick_token_check.py PEPE/USDT
python quick_token_check.py "BTC/USDT,ETH/USDT,PEPE/USDT"
python quick_token_check.py --live  # Режим реального времени
"""

import asyncio
import sys
import os
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from colorama import init, Fore, Style

# Инициализация цветного вывода
init()

# Добавляем корневую папку в PYTHONPATH
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Загрузка переменных окружения
load_dotenv()

async def check_single_token(symbol: str, detailed: bool = False):
    """Проверка одного токена"""
    print(f"\n🔍 Проверяем {symbol}...")
    
    try:
        from src.exchanges.mexc_client import MEXCClient
        from src.exchanges.dex_client import DEXClient
        
        # Создаем клиентов
        mexc_client = MEXCClient()
        
        # Получаем данные параллельно
        mexc_task = mexc_client.get_ticker(symbol)
        
        async with DEXClient() as dex_client:
            dex_task = dex_client.get_dex_price(symbol)
            
            mexc_data, dex_data = await asyncio.gather(
                mexc_task, dex_task, return_exceptions=True
            )
        
        mexc_client.close_connection()
        
        # Анализируем результаты
        mexc_ok = not isinstance(mexc_data, Exception) and mexc_data is not None
        dex_ok = not isinstance(dex_data, Exception) and dex_data is not None
        
        print(f"  📊 MEXC: ", end="")
        if mexc_ok:
            mexc_price = mexc_data['price']
            print(f"{Fore.GREEN}✅ ${mexc_price:.8f}{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}❌ Недоступен{Style.RESET_ALL}")
            if isinstance(mexc_data, Exception):
                print(f"     Ошибка: {mexc_data}")
        
        print(f"  📊 DEX:  ", end="")
        if dex_ok:
            dex_price = dex_data['price']
            sources = len(dex_data.get('sources', []))
            print(f"{Fore.GREEN}✅ ${dex_price:.8f} ({sources} источников){Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}❌ Недоступен{Style.RESET_ALL}")
            if isinstance(dex_data, Exception):
                print(f"     Ошибка: {dex_data}")
        
        if mexc_ok and dex_ok:
            # Сравниваем цены
            spread = abs(mexc_price - dex_price) / mexc_price * 100
            ratio = max(mexc_price, dex_price) / min(mexc_price, dex_price)
            
            print(f"  📈 Спред: {spread:.2f}%")
            print(f"  📊 Соотношение цен: {ratio:.2f}x")
            
            # Оценка
            if ratio > 10:
                print(f"  🚨 {Fore.RED}КРИТИЧНО: Цены отличаются в {ratio:.1f} раз!{Style.RESET_ALL}")
                print(f"     ❓ Возможно, это РАЗНЫЕ токены с одинаковым символом")
            elif spread > 100:
                print(f"  ⚠️  {Fore.YELLOW}ВНИМАНИЕ: Очень высокий спред {spread:.1f}%{Style.RESET_ALL}")
            elif spread > 50:
                print(f"  ⚠️  {Fore.YELLOW}Высокий спред {spread:.1f}%{Style.RESET_ALL}")
            elif spread > 7.5:
                print(f"  🎯 {Fore.GREEN}АРБИТРАЖНАЯ ВОЗМОЖНОСТЬ: {spread:.1f}%{Style.RESET_ALL}")
            else:
                print(f"  ✅ {Fore.GREEN}Нормальный спред: {spread:.1f}%{Style.RESET_ALL}")
            
            # Детальная информация
            if detailed and dex_ok:
                print(f"\n  📋 Детальная информация DEX:")
                if 'sources' in dex_data:
                    print(f"     Источники: {', '.join(dex_data['sources'])}")
                
                # Пробуем получить больше информации
                try:
                    import aiohttp
                    base_token = symbol.split('/')[0].upper()
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            f"https://api.dexscreener.com/latest/dex/search?q={base_token}"
                        ) as response:
                            if response.status == 200:
                                data = await response.json()
                                pairs = data.get('pairs', [])
                                
                                if pairs:
                                    best_pair = pairs[0]
                                    token_info = best_pair.get('baseToken', {})
                                    
                                    print(f"     Название: {token_info.get('name', 'N/A')}")
                                    print(f"     Адрес: {token_info.get('address', 'N/A')[:10]}...")
                                    print(f"     Сеть: {best_pair.get('chainId', 'N/A')}")
                                    print(f"     DEX: {best_pair.get('dexId', 'N/A')}")
                                    
                                    liquidity = best_pair.get('liquidity', {}).get('usd', 0)
                                    if liquidity:
                                        print(f"     Ликвидность: ${liquidity:,.0f}")
                except:
                    pass
            
            return {
                'symbol': symbol,
                'mexc_price': mexc_price,
                'dex_price': dex_price,
                'spread': spread,
                'ratio': ratio,
                'status': 'ok' if ratio < 2 and spread < 50 else 'warning' if ratio < 10 else 'critical'
            }
        else:
            return {
                'symbol': symbol,
                'status': 'error',
                'mexc_available': mexc_ok,
                'dex_available': dex_ok
            }
            
    except Exception as e:
        print(f"  ❌ Критическая ошибка: {e}")
        return {'symbol': symbol, 'status': 'error', 'error': str(e)}

async def live_monitoring(symbols: list, interval: int = 5):
    """Режим мониторинга в реальном времени"""
    print(f"{Fore.CYAN}⚡ РЕЖИМ РЕАЛЬНОГО ВРЕМЕНИ")
    print(f"Обновление каждые {interval} секунд. Нажмите Ctrl+C для выхода.")
    print("=" * 80)
    
    try:
        while True:
            # Очищаем экран (для Unix/Linux/Mac)
            if os.name == 'posix':
                os.system('clear')
            
            print(f"{Fore.CYAN}🕐 {datetime.now().strftime('%H:%M:%S')} - Мониторинг токенов:{Style.RESET_ALL}")
            print("=" * 80)
            print(f"{'Токен':<12} {'MEXC':<15} {'DEX':<15} {'Спред':<8} {'Статус'}")
            print("-" * 80)
            
            results = []
            for symbol in symbols:
                try:
                    result = await check_single_token(symbol, detailed=False)
                    results.append(result)
                    
                    if result.get('status') == 'ok':
                        mexc_price = result['mexc_price']
                        dex_price = result['dex_price']
                        spread = result['spread']
                        
                        status_color = Fore.GREEN if spread < 20 else Fore.YELLOW if spread < 50 else Fore.RED
                        status_text = "ОК" if spread < 20 else "Высокий" if spread < 50 else "Критич"
                        
                        print(f"{symbol:<12} ${mexc_price:<14.6f} ${dex_price:<14.6f} {spread:<7.2f}% {status_color}{status_text}{Style.RESET_ALL}")
                    else:
                        print(f"{symbol:<12} {'❌ Ошибка':<40}")
                        
                except Exception as e:
                    print(f"{symbol:<12} {'❌ Исключение':<40}")
            
            # Ищем арбитражные возможности
            opportunities = [r for r in results if r.get('status') == 'ok' and r.get('spread', 0) > 7.5]
            
            if opportunities:
                print(f"\n{Fore.GREEN}🎯 НАЙДЕНЫ ВОЗМОЖНОСТИ:")
                for opp in opportunities:
                    direction = "LONG MEXC" if opp['mexc_price'] < opp['dex_price'] else "SHORT MEXC"
                    print(f"   {opp['symbol']}: {opp['spread']:.2f}% ({direction})")
            
            print(f"\n⏰ Следующее обновление через {interval} сек... (Ctrl+C для выхода)")
            
            await asyncio.sleep(interval)
            
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}⏹️ Мониторинг остановлен{Style.RESET_ALL}")

def parse_args():
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(description='Быстрая проверка соответствия токенов')
    parser.add_argument('symbols', nargs='?', 
                       help='Токен или список токенов через запятую (например: BTC/USDT или "BTC/USDT,ETH/USDT")')
    parser.add_argument('--live', action='store_true',
                       help='Режим мониторинга в реальном времени')
    parser.add_argument('--detailed', '-d', action='store_true',
                       help='Детальная информация о токенах')
    parser.add_argument('--interval', '-i', type=int, default=5,
                       help='Интервал обновления в live режиме (сек)')
    
    return parser.parse_args()

async def main():
    """Главная функция"""
    args = parse_args()
    
    # Проверка API ключей
    if not os.getenv('MEXC_API_KEY'):
        print(f"{Fore.RED}❌ MEXC_API_KEY не найден в .env файле{Style.RESET_ALL}")
        print("Создайте .env файл и добавьте ваши API ключи")
        return
    
    print(f"{Fore.CYAN}🔍 БЫСТРАЯ ПРОВЕРКА ТОКЕНОВ")
    print("Автор: 24vasilekk")
    print("=" * 50)
    
    # Определяем список токенов для проверки
    if args.symbols:
        if ',' in args.symbols:
            symbols = [s.strip() for s in args.symbols.split(',')]
        else:
            symbols = [args.symbols.strip()]
    else:
        # По умолчанию проверяем несколько популярных
        symbols = ['BTC/USDT', 'ETH/USDT', 'PEPE/USDT', 'DINO/USDT']
        print("Токены не указаны, проверяем по умолчанию:")
        print(f"Используйте: python {sys.argv[0]} \"BTC/USDT,ETH/USDT\" для своего списка")
    
    if args.live:
        # Режим реального времени
        await live_monitoring(symbols, args.interval)
    else:
        # Разовая проверка
        for symbol in symbols:
            await check_single_token(symbol, detailed=args.detailed)
        
        print(f"\n{Fore.GREEN}✅ Проверка завершена!")
        print(f"\n{Fore.CYAN}💡 Полезные команды:")
        print(f"   python {sys.argv[0]} --live                    # Мониторинг в реальном времени")
        print(f"   python {sys.argv[0]} PEPE/USDT --detailed      # Детальная проверка")
        print(f"   python validate_token_matching.py             # Полная валидация{Style.RESET_ALL}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}⏹️ Программа прервана{Style.RESET_ALL}")
    except Exception as e:
        print(f"\n{Fore.RED}❌ Критическая ошибка: {e}{Style.RESET_ALL}")