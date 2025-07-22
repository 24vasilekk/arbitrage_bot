"""
Тестирование подключений к MEXC и DEX источникам
"""

import asyncio
import ccxt
import aiohttp
import os
from dotenv import load_dotenv
from colorama import init, Fore, Style

# Инициализация цветного вывода
init()

load_dotenv()

async def test_mexc():
    """Тест подключения к MEXC Futures"""
    print(f"{Fore.YELLOW}🔄 Тестирование MEXC Futures...{Style.RESET_ALL}")
    
    mexc = ccxt.mexc({
        'apiKey': os.getenv('MEXC_API_KEY'),
        'secret': os.getenv('MEXC_SECRET'),
        'sandbox': True,  # Тестовая сеть
        'enableRateLimit': True,
        'options': {'defaultType': 'swap'}  # Фьючерсы
    })
    
    try:
        # Загрузка рынков
        markets = mexc.load_markets()
        print(f"{Fore.GREEN}✅ Рынки загружены: {len(markets)} торговых пар{Style.RESET_ALL}")
        
        # Тест баланса
        balance = mexc.fetch_balance()
        usdt_balance = balance.get('USDT', {}).get('free', 0)
        print(f"{Fore.GREEN}✅ Баланс USDT: {usdt_balance}{Style.RESET_ALL}")
        
        # Тест получения тикера
        ticker = mexc.fetch_ticker('BTC/USDT')
        btc_price = ticker['last']
        print(f"{Fore.GREEN}✅ BTC/USDT цена: ${btc_price:,.2f}{Style.RESET_ALL}")
        
        # Тест позиций
        positions = mexc.fetch_positions()
        open_positions = [p for p in positions if p['contracts'] != 0]
        print(f"{Fore.GREEN}✅ Открытых позиций: {len(open_positions)}{Style.RESET_ALL}")
        
        return True
        
    except Exception as e:
        print(f"{Fore.RED}❌ Ошибка MEXC: {e}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}🔧 Проверьте:{Style.RESET_ALL}")
        print("   1. Правильность API ключей в .env")
        print("   2. Разрешения фьючерсов включены")  
        print("   3. IP адрес добавлен в белый список")
        return False
        
    finally:
        mexc.close()

async def test_dex_sources():
    """Тест подключения к DEX источникам цен"""
    print(f"\n{Fore.YELLOW}🔄 Тестирование DEX источников...{Style.RESET_ALL}")
    
    async with aiohttp.ClientSession() as session:
        success_count = 0
        
        # Тест CoinGecko
        try:
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {"ids": "bitcoin,ethereum,binancecoin", "vs_currencies": "usd"}
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"{Fore.GREEN}✅ CoinGecko подключен:{Style.RESET_ALL}")
                    print(f"   BTC: ${data.get('bitcoin', {}).get('usd', 'N/A'):,}")
                    print(f"   ETH: ${data.get('ethereum', {}).get('usd', 'N/A'):,}")
                    print(f"   BNB: ${data.get('binancecoin', {}).get('usd', 'N/A'):,}")
                    success_count += 1
                else:
                    print(f"{Fore.RED}❌ CoinGecko: HTTP {response.status}{Style.RESET_ALL}")
                    
        except Exception as e:
            print(f"{Fore.RED}❌ CoinGecko ошибка: {e}{Style.RESET_ALL}")
        
        # Тест DexScreener
        try:
            url = "https://api.dexscreener.com/latest/dex/tokens/0xA0b86a33E6417c3c7fD4819C6B0Ea73e3BDD6b62"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    pairs_count = len(data.get('pairs', []))
                    print(f"{Fore.GREEN}✅ DexScreener подключен: {pairs_count} пар найдено{Style.RESET_ALL}")
                    success_count += 1
                else:
                    print(f"{Fore.RED}❌ DexScreener: HTTP {response.status}{Style.RESET_ALL}")
                    
        except Exception as e:
            print(f"{Fore.RED}❌ DexScreener ошибка: {e}{Style.RESET_ALL}")
        
        # Тест общедоступного API Binance для сравнения
        try:
            url = "https://api.binance.com/api/v3/ticker/price"
            params = {"symbols": '["BTCUSDT","ETHUSDT","BNBUSDT"]'}
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"{Fore.GREEN}✅ Binance API (для сравнения) подключен:{Style.RESET_ALL}")
                    for item in data:
                        symbol = item['symbol']
                        price = float(item['price'])
                        print(f"   {symbol}: ${price:,.2f}")
                    success_count += 1
                else:
                    print(f"{Fore.RED}❌ Binance API: HTTP {response.status}{Style.RESET_ALL}")
                    
        except Exception as e:
            print(f"{Fore.RED}❌ Binance API ошибка: {e}{Style.RESET_ALL}")
            
        return success_count >= 2  # Минимум 2 источника должны работать

async def test_arbitrage_logic():
    """Тест базовой логики арбитража"""
    print(f"\n{Fore.YELLOW}🔄 Тестирование логики арбитража...{Style.RESET_ALL}")
    
    # Симуляция цен
    mexc_price = 45000.0
    dex_price = 48500.0
    
    # Расчет спреда
    spread_percent = abs(mexc_price - dex_price) / mexc_price * 100
    
    print(f"📊 Симуляция цен:")
    print(f"   MEXC: ${mexc_price:,.2f}")
    print(f"   DEX:  ${dex_price:,.2f}")
    print(f"   Спред: {spread_percent:.2f}%")
    
    min_spread = float(os.getenv('MIN_SPREAD_PERCENT', 7.5))
    
    if spread_percent >= min_spread:
        direction = "LONG на MEXC" if mexc_price < dex_price else "SHORT на MEXC"
        print(f"{Fore.GREEN}✅ Арбитражная возможность найдена!{Style.RESET_ALL}")
        print(f"   Направление: {direction}")
        print(f"   Потенциальная прибыль: ~{spread_percent - 0.5:.1f}%")
    else:
        print(f"{Fore.YELLOW}⚠️  Спред {spread_percent:.2f}% меньше минимального {min_spread}%{Style.RESET_ALL}")
    
    return True

async def test_all_connections():
    """Запуск всех тестов"""
    print(f"{Fore.CYAN}🚀 Тестирование всех подключений...{Style.RESET_ALL}")
    print("=" * 60)
    
    # Проверка переменных окружения
    if not os.getenv('MEXC_API_KEY'):
        print(f"{Fore.RED}❌ MEXC_API_KEY не найден в .env файле{Style.RESET_ALL}")
        return False
    
    if not os.getenv('MEXC_SECRET'):
        print(f"{Fore.RED}❌ MEXC_SECRET не найден в .env файле{Style.RESET_ALL}")
        return False
    
    print(f"{Fore.GREEN}✅ Переменные окружения загружены{Style.RESET_ALL}")
    
    # Запуск тестов
    mexc_ok = await test_mexc()
    dex_ok = await test_dex_sources()
    arbitrage_ok = await test_arbitrage_logic()
    
    print("\n" + "=" * 60)
    
    if mexc_ok and dex_ok and arbitrage_ok:
        print(f"{Fore.GREEN}🎉 ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!{Style.RESET_ALL}")
        print(f"{Fore.GREEN}✅ Бот готов к работе{Style.RESET_ALL}")
        return True
    else:
        print(f"{Fore.RED}❌ Некоторые тесты не прошли{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}🔧 Проверьте настройки и попробуйте снова{Style.RESET_ALL}")
        return False

if __name__ == "__main__":
    asyncio.run(test_all_connections())