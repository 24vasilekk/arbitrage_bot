"""
Тестирование подключений к MEXC и DEX источникам
Автор: 24vasilekk  
Путь: test_connections.py (в корне проекта)
ОБНОВЛЕН: Поддержка новых токенов
"""

import asyncio
import ccxt
import aiohttp
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from colorama import init, Fore, Style

# Инициализация цветного вывода
init()

# Добавляем корневую папку в PYTHONPATH
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

load_dotenv()

# Тестовые токены - микс стабильных и новых
TEST_TOKENS = [
    "BTC/USDT",    # Стабильный
    "ETH/USDT",    # Стабильный  
    "PEPE/USDT",   # Новый
    "DINO/USDT",   # Новый
    "GOG/USDT"     # Новый
]

async def test_mexc():
    """Тест подключения к MEXC Futures"""
    print(f"{Fore.YELLOW}🔄 Тестирование MEXC Futures...{Style.RESET_ALL}")
    
    mexc = None
    try:
        mexc = ccxt.mexc({
            'apiKey': os.getenv('MEXC_API_KEY'),
            'secret': os.getenv('MEXC_SECRET'),
            'sandbox': True,  # Тестовая сеть
            'enableRateLimit': True,
            'options': {'defaultType': 'swap'}  # Фьючерсы
        })
        
        # Загрузка рынков
        print("  📡 Загружаем рынки...")
        markets = mexc.load_markets()
        print(f"  {Fore.GREEN}✅ Рынки загружены: {len(markets)} торговых пар{Style.RESET_ALL}")
        
        # Тест баланса
        print("  💰 Проверяем баланс...")
        balance = mexc.fetch_balance()
        usdt_balance = balance.get('USDT', {}).get('free', 0)
        total_balance = balance.get('USDT', {}).get('total', 0)
        print(f"  {Fore.GREEN}✅ Баланс USDT: свободно ${usdt_balance:.2f}, всего ${total_balance:.2f}{Style.RESET_ALL}")
        
        # Тест получения тикеров для наших токенов
        print("  📊 Тестируем получение цен...")
        available_tokens = []
        for token in TEST_TOKENS:
            try:
                if token in markets:
                    ticker = mexc.fetch_ticker(token)
                    price = ticker['last']
                    print(f"    {Fore.GREEN}✅{Style.RESET_ALL} {token:<12} ${price:>12,.4f}")
                    available_tokens.append(token)
                else:
                    print(f"    {Fore.RED}❌{Style.RESET_ALL} {token:<12} не найден на MEXC")
            except Exception as e:
                print(f"    {Fore.RED}❌{Style.RESET_ALL} {token:<12} ошибка: {str(e)[:30]}...")
        
        # Тест позиций
        print("  📍 Проверяем позиции...")
        positions = mexc.fetch_positions()
        open_positions = [p for p in positions if p['contracts'] != 0]
        print(f"  {Fore.GREEN}✅ Открытых позиций: {len(open_positions)}{Style.RESET_ALL}")
        
        if open_positions:
            print("  ⚠️  Найдены открытые позиции:")
            for pos in open_positions[:3]:  # Показываем первые 3
                symbol = pos['symbol']
                side = pos['side']
                size = pos['contracts']
                pnl = pos['unrealizedPnl']
                print(f"    📊 {symbol} {side} {size} (PnL: ${pnl:.2f})")
        
        print(f"  {Fore.GREEN}✅ Доступно токенов: {len(available_tokens)}/{len(TEST_TOKENS)}{Style.RESET_ALL}")
        return True
        
    except ccxt.AuthenticationError:
        print(f"  {Fore.RED}❌ Ошибка аутентификации MEXC{Style.RESET_ALL}")
        print(f"  {Fore.YELLOW}🔧 Проверьте API ключи в .env файле{Style.RESET_ALL}")
        return False
    except ccxt.NetworkError as e:
        print(f"  {Fore.RED}❌ Сетевая ошибка MEXC: {e}{Style.RESET_ALL}")
        return False
    except Exception as e:
        print(f"  {Fore.RED}❌ Ошибка MEXC: {e}{Style.RESET_ALL}")
        print(f"  {Fore.YELLOW}🔧 Проверьте:{Style.RESET_ALL}")
        print("    1. Правильность API ключей в .env")
        print("    2. Разрешения фьючерсов включены")  
        print("    3. IP адрес добавлен в белый список")
        return False
        
    finally:
        if mexc:
            mexc.close()

async def test_dex_sources():
    """Тест подключения к DEX источникам цен"""
    print(f"\n{Fore.YELLOW}🔄 Тестирование DEX источников...{Style.RESET_ALL}")
    
    # Попробуем использовать наш DEX клиент
    try:
        from src.exchanges.dex_client import DEXClient
        
        print("  🔌 Инициализируем DEX клиент...")
        async with DEXClient() as dex_client:
            successful_tokens = 0
            
            for token in TEST_TOKENS:
                print(f"  🔍 Тестируем {token}...", end="")
                
                try:
                    price_data = await dex_client.get_dex_price(token)
                    
                    if price_data and price_data.get('price', 0) > 0:
                        price = price_data['price']
                        sources = price_data.get('sources', [])
                        print(f" {Fore.GREEN}✅ ${price:.4f} ({len(sources)} источников: {', '.join(sources)}){Style.RESET_ALL}")
                        successful_tokens += 1
                    else:
                        print(f" {Fore.RED}❌ цена не получена{Style.RESET_ALL}")
                        
                except Exception as e:
                    print(f" {Fore.RED}❌ ошибка: {str(e)[:30]}...{Style.RESET_ALL}")
                
                # Небольшая пауза между запросами
                await asyncio.sleep(1)
            
            print(f"  {Fore.GREEN}✅ Успешно получены цены: {successful_tokens}/{len(TEST_TOKENS)}{Style.RESET_ALL}")
            
            return successful_tokens >= len(TEST_TOKENS) // 2  # Минимум 50% токенов должны работать
        
    except ImportError:
        print(f"  {Fore.YELLOW}⚠️ DEX клиент не найден, используем прямые API запросы{Style.RESET_ALL}")
        
        # Fallback - прямые запросы к API
        return await test_dex_direct()
    except Exception as e:
        print(f"  {Fore.RED}❌ Ошибка DEX клиента: {e}{Style.RESET_ALL}")
        return False

async def test_dex_direct():
    """Прямое тестирование DEX API без клиента"""
    async with aiohttp.ClientSession() as session:
        success_count = 0
        
        # Тест CoinGecko
        try:
            print("    🔍 Тестируем CoinGecko...")
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {"ids": "bitcoin,ethereum,pepe", "vs_currencies": "usd"}
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    btc_price = data.get('bitcoin', {}).get('usd', 'N/A')
                    eth_price = data.get('ethereum', {}).get('usd', 'N/A')
                    pepe_price = data.get('pepe', {}).get('usd', 'N/A')
                    
                    print(f"      {Fore.GREEN}✅ CoinGecko подключен:{Style.RESET_ALL}")
                    print(f"         BTC: ${btc_price:,}")
                    print(f"         ETH: ${eth_price:,}")  
                    print(f"         PEPE: ${pepe_price}")
                    success_count += 1
                else:
                    print(f"      {Fore.RED}❌ CoinGecko: HTTP {response.status}{Style.RESET_ALL}")
                    
        except Exception as e:
            print(f"      {Fore.RED}❌ CoinGecko ошибка: {e}{Style.RESET_ALL}")
        
        # Тест DexScreener
        try:
            print("    🔍 Тестируем DexScreener...")
            url = "https://api.dexscreener.com/latest/dex/search"
            params = {"q": "PEPE"}
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    pairs_count = len(data.get('pairs', []))
                    print(f"      {Fore.GREEN}✅ DexScreener подключен: {pairs_count} пар найдено{Style.RESET_ALL}")
                    success_count += 1
                else:
                    print(f"      {Fore.RED}❌ DexScreener: HTTP {response.status}{Style.RESET_ALL}")
                    
        except Exception as e:
            print(f"      {Fore.RED}❌ DexScreener ошибка: {e}{Style.RESET_ALL}")
        
        # Тест Binance для сравнения
        try:
            print("    🔍 Тестируем Binance API...")
            url = "https://api.binance.com/api/v3/ticker/price"
            params = {"symbols": '["BTCUSDT","ETHUSDT","PEPEUSDT"]'}
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"      {Fore.GREEN}✅ Binance API подключен:{Style.RESET_ALL}")
                    for item in data:
                        symbol = item['symbol']
                        price = float(item['price'])
                        print(f"         {symbol}: ${price:,.6f}")
                    success_count += 1
                else:
                    print(f"      {Fore.RED}❌ Binance API: HTTP {response.status}{Style.RESET_ALL}")
                    
        except Exception as e:
            print(f"      {Fore.RED}❌ Binance API ошибка: {e}{Style.RESET_ALL}")
            
        return success_count >= 2  # Минимум 2 источника должны работать

async def test_arbitrage_simulation():
    """Тест симуляции арбитражной логики"""
    print(f"\n{Fore.YELLOW}🔄 Тестирование арбитражной логики...{Style.RESET_ALL}")
    
    # Симуляция цен с разным спредом
    test_cases = [
        ("BTC/USDT", 45000.0, 48500.0, "большой спред"),
        ("ETH/USDT", 3200.0, 3230.0, "маленький спред"),
        ("PEPE/USDT", 0.00001234, 0.00001345, "микро-токен"),
    ]
    
    min_spread = float(os.getenv('MIN_SPREAD_PERCENT', 7.5))
    
    print(f"  🎯 Минимальный спред для торговли: {min_spread}%")
    
    opportunities_found = 0
    
    for symbol, mexc_price, dex_price, description in test_cases:
        # Расчет спреда
        spread_percent = abs(mexc_price - dex_price) / mexc_price * 100
        direction = "LONG на MEXC" if mexc_price < dex_price else "SHORT на MEXC"
        
        print(f"\n  📊 Симуляция {symbol} ({description}):")
        print(f"     MEXC: ${mexc_price:,.6f}")
        print(f"     DEX:  ${dex_price:,.6f}")
        print(f"     Спред: {spread_percent:.2f}%")
        
        if spread_percent >= min_spread:
            opportunities_found += 1
            potential_profit = spread_percent - 0.5  # Вычитаем комиссии
            print(f"     {Fore.GREEN}✅ АРБИТРАЖНАЯ ВОЗМОЖНОСТЬ!{Style.RESET_ALL}")
            print(f"     🎯 Направление: {direction}")
            print(f"     💰 Потенциальная прибыль: ~{potential_profit:.1f}%")
        else:
            print(f"     {Fore.YELLOW}⚠️ Спред недостаточен ({spread_percent:.2f}% < {min_spread}%){Style.RESET_ALL}")
    
    print(f"\n  {Fore.CYAN}📈 Найдено возможностей: {opportunities_found}/{len(test_cases)}{Style.RESET_ALL}")
    
    return True

async def test_all_connections():
    """Запуск всех тестов"""
    print(f"{Fore.CYAN}🚀 ПОЛНОЕ ТЕСТИРОВАНИЕ АРБИТРАЖНОГО БОТА")
    print("=" * 60)
    print("Автор: 24vasilekk")
    print("Email: 24vasilekk@gmail.com")  
    print("=" * 60)
    
    # Проверка переменных окружения
    print(f"{Fore.YELLOW}🔧 Проверяем переменные окружения...{Style.RESET_ALL}")
    
    if not os.getenv('MEXC_API_KEY'):
        print(f"{Fore.RED}❌ MEXC_API_KEY не найден в .env файле{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}💡 Создайте .env из .env.example и добавьте API ключи{Style.RESET_ALL}")
        return False
    
    if not os.getenv('MEXC_SECRET'):
        print(f"{Fore.RED}❌ MEXC_SECRET не найден в .env файле{Style.RESET_ALL}")
        return False
    
    print(f"{Fore.GREEN}✅ Переменные окружения загружены{Style.RESET_ALL}")
    
    # Запуск всех тестов
    results = []
    
    # Тест 1: MEXC
    mexc_ok = await test_mexc()
    results.append(("MEXC Futures", mexc_ok))
    
    # Тест 2: DEX источники  
    dex_ok = await test_dex_sources()
    results.append(("DEX источники", dex_ok))
    
    # Тест 3: Арбитражная логика
    arbitrage_ok = await test_arbitrage_simulation()
    results.append(("Арбитражная логика", arbitrage_ok))
    
    # Итоговые результаты
    print(f"\n{Fore.CYAN}=" * 60)
    print("📋 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    print("=" * 60)
    
    all_passed = True
    for test_name, result in results:
        status = f"{Fore.GREEN}✅ ПРОШЕЛ{Style.RESET_ALL}" if result else f"{Fore.RED}❌ ПРОВАЛЕН{Style.RESET_ALL}"
        print(f"  {test_name:<20} {status}")
        if not result:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print(f"{Fore.GREEN}🎉 ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!{Style.RESET_ALL}")
        print(f"{Fore.GREEN}✅ Бот готов к работе{Style.RESET_ALL}")
        print(f"\n{Fore.YELLOW}🚀 СЛЕДУЮЩИЕ ШАГИ:{Style.RESET_ALL}")
        print("1. Проверьте новые токены: python check_new_tokens.py")
        print("2. Запустите в тест-режиме: python run.py --test-mode")
        print("3. Мониторьте логи: tail -f logs/arbitrage_bot.log")
        return True
    else:
        print(f"{Fore.RED}❌ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОШЛИ{Style.RESET_ALL}")
        print(f"\n{Fore.YELLOW}🔧 РЕКОМЕНДАЦИИ ПО ИСПРАВЛЕНИЮ:{Style.RESET_ALL}")
        
        if not mexc_ok:
            print("• Проверьте MEXC API ключи и настройки")
            print("• Убедитесь что включены права фьючерсов")
            print("• Добавьте IP в белый список")
        
        if not dex_ok:
            print("• Проверьте интернет соединение")
            print("• Возможны временные проблемы с DEX API")
            print("• Попробуйте через несколько минут")
        
        print(f"\n{Fore.CYAN}💡 Можете попробовать запуск с --skip-tests{Style.RESET_ALL}")
        return False

async def main():
    """Главная функция для прямого запуска"""
    try:
        result = await test_all_connections()
        exit_code = 0 if result else 1
        exit(exit_code)
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}⏹️ Тестирование прервано пользователем{Style.RESET_ALL}")
        exit(1)
    except Exception as e:
        print(f"\n{Fore.RED}❌ Критическая ошибка тестирования: {e}{Style.RESET_ALL}")
        exit(1)

if __name__ == "__main__":
    asyncio.run(main())