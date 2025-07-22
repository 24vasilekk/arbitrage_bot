#!/usr/bin/env python3
"""
Инструмент проверки соответствия токенов между MEXC и DexScreener
Автор: 24vasilekk
Путь: validate_token_matching.py (в корне проекта)

Проверяет:
1. Существование токенов на обеих платформах
2. Правильность сопоставления цен
3. Разумность спредов
4. Контрактные адреса для верификации

Запуск:
python validate_token_matching.py
"""

import asyncio
import sys
import os
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from colorama import init, Fore, Style
from typing import Dict, List, Optional, Tuple

# Инициализация цветного вывода
init()

# Добавляем корневую папку в PYTHONPATH
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Загрузка переменных окружения
load_dotenv()

# Токены для детальной проверки
VALIDATION_TOKENS = [
    "BTC/USDT", "ETH/USDT", "BNB/USDT",  # Стабильные для калибровки
    "PEPE/USDT", "DINO/USDT", "GOG/USDT", "ZEUS/USDT",  # Новые
    "FART/USDT", "LABUBU/USDT", "HOUSE/USDT"  # Экзотичные
]

async def get_mexc_token_info(symbol: str) -> Optional[Dict]:
    """Получение детальной информации о токене с MEXC"""
    try:
        from src.exchanges.mexc_client import MEXCClient
        
        mexc_client = MEXCClient()
        
        # Получаем тикер
        ticker = await mexc_client.get_ticker(symbol)
        if not ticker:
            return None
            
        # Получаем информацию о рынке
        market_info = mexc_client.exchange.markets.get(symbol, {})
        
        result = {
            'symbol': symbol,
            'price': ticker['price'],
            'bid': ticker['bid'],
            'ask': ticker['ask'],
            'exchange': 'MEXC',
            'market_info': {
                'base': market_info.get('base', ''),
                'quote': market_info.get('quote', ''),
                'active': market_info.get('active', False),
                'type': market_info.get('type', ''),
                'id': market_info.get('id', ''),
                'precision': market_info.get('precision', {}),
                'limits': market_info.get('limits', {})
            },
            'timestamp': datetime.now().isoformat()
        }
        
        mexc_client.close_connection()
        return result
        
    except Exception as e:
        print(f"❌ Ошибка получения данных MEXC для {symbol}: {e}")
        return None

async def get_dex_token_info(symbol: str) -> Optional[Dict]:
    """Получение детальной информации о токене с DexScreener"""
    try:
        from src.exchanges.dex_client import DEXClient
        
        async with DEXClient() as dex_client:
            # Получаем базовые данные о цене
            price_data = await dex_client.get_dex_price(symbol)
            if not price_data:
                return None
            
            # Получаем детальную информацию о токене через прямой API
            import aiohttp
            
            base_token = symbol.split('/')[0].upper()
            url = f"https://api.dexscreener.com/latest/dex/search"
            params = {'q': base_token}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        pairs = data.get('pairs', [])
                        
                        # Ищем лучшие пары с USDT/USDC
                        best_pairs = []
                        for pair in pairs:
                            quote_symbol = pair.get('quoteToken', {}).get('symbol', '').upper()
                            base_symbol = pair.get('baseToken', {}).get('symbol', '').upper()
                            
                            if (quote_symbol in ['USDT', 'USDC'] and 
                                base_symbol == base_token):
                                best_pairs.append(pair)
                        
                        # Сортируем по ликвидности
                        best_pairs.sort(key=lambda x: x.get('liquidity', {}).get('usd', 0), reverse=True)
                        
                        if best_pairs:
                            top_pair = best_pairs[0]
                            
                            return {
                                'symbol': symbol,
                                'price': price_data['price'],
                                'exchange': 'DexScreener',
                                'pair_info': {
                                    'dex_id': top_pair.get('dexId', ''),
                                    'pair_address': top_pair.get('pairAddress', ''),
                                    'base_token': {
                                        'address': top_pair.get('baseToken', {}).get('address', ''),
                                        'name': top_pair.get('baseToken', {}).get('name', ''),
                                        'symbol': top_pair.get('baseToken', {}).get('symbol', '')
                                    },
                                    'quote_token': {
                                        'address': top_pair.get('quoteToken', {}).get('address', ''),
                                        'name': top_pair.get('quoteToken', {}).get('name', ''),
                                        'symbol': top_pair.get('quoteToken', {}).get('symbol', '')
                                    },
                                    'liquidity_usd': top_pair.get('liquidity', {}).get('usd', 0),
                                    'volume_24h': top_pair.get('volume', {}).get('h24', 0),
                                    'price_change_24h': top_pair.get('priceChange', {}).get('h24', 0),
                                    'chain_id': top_pair.get('chainId', ''),
                                    'dex_name': top_pair.get('dexId', '').upper()
                                },
                                'all_pairs_count': len(best_pairs),
                                'total_liquidity': sum(p.get('liquidity', {}).get('usd', 0) for p in best_pairs[:5]),
                                'timestamp': datetime.now().isoformat()
                            }
            
            return None
        
    except Exception as e:
        print(f"❌ Ошибка получения данных DEX для {symbol}: {e}")
        return None

async def validate_token_pair(symbol: str) -> Dict:
    """Валидация пары токенов между MEXC и DEX"""
    print(f"\n🔍 Проверяем {symbol}...")
    
    # Получаем данные с обеих платформ
    mexc_info, dex_info = await asyncio.gather(
        get_mexc_token_info(symbol),
        get_dex_token_info(symbol),
        return_exceptions=True
    )
    
    # Проверяем на ошибки
    if isinstance(mexc_info, Exception):
        mexc_info = None
    if isinstance(dex_info, Exception):
        dex_info = None
    
    validation_result = {
        'symbol': symbol,
        'mexc_available': mexc_info is not None,
        'dex_available': dex_info is not None,
        'both_available': mexc_info is not None and dex_info is not None,
        'mexc_info': mexc_info,
        'dex_info': dex_info,
        'validation_status': 'unknown',
        'price_comparison': {},
        'warnings': [],
        'recommendations': []
    }
    
    if not mexc_info:
        validation_result['warnings'].append(f"❌ {symbol} не найден на MEXC")
        validation_result['validation_status'] = 'mexc_missing'
        
    if not dex_info:
        validation_result['warnings'].append(f"❌ {symbol} не найден в DexScreener")
        validation_result['validation_status'] = 'dex_missing'
    
    if mexc_info and dex_info:
        # Сравниваем цены
        mexc_price = mexc_info['price']
        dex_price = dex_info['price']
        
        # Проверка разумности цен
        price_ratio = max(mexc_price, dex_price) / min(mexc_price, dex_price)
        spread_percent = abs(mexc_price - dex_price) / mexc_price * 100
        
        validation_result['price_comparison'] = {
            'mexc_price': mexc_price,
            'dex_price': dex_price,
            'price_ratio': price_ratio,
            'spread_percent': spread_percent,
            'reasonable_spread': spread_percent < 50  # Флаг разумности спреда
        }
        
        # Определяем статус валидации
        if price_ratio > 10:  # Цены отличаются в 10+ раз
            validation_result['validation_status'] = 'price_mismatch'
            validation_result['warnings'].append(f"🚨 ПОДОЗРИТЕЛЬНАЯ разница цен: {price_ratio:.1f}x")
        elif spread_percent > 100:  # Спред больше 100%
            validation_result['validation_status'] = 'extreme_spread'
            validation_result['warnings'].append(f"⚠️ ЭКСТРЕМАЛЬНЫЙ спред: {spread_percent:.1f}%")
        elif spread_percent > 50:  # Спред больше 50%
            validation_result['validation_status'] = 'high_spread'
            validation_result['warnings'].append(f"⚠️ Высокий спред: {spread_percent:.1f}%")
        else:
            validation_result['validation_status'] = 'ok'
        
        # Анализируем токен подробнее
        if dex_info.get('pair_info'):
            pair_info = dex_info['pair_info']
            
            # Проверяем ликвидность
            liquidity = pair_info.get('liquidity_usd', 0)
            if liquidity < 10000:
                validation_result['warnings'].append(f"⚠️ Низкая ликвидность: ${liquidity:,.0f}")
            
            # Проверяем название токена
            dex_name = pair_info.get('base_token', {}).get('name', '')
            dex_symbol = pair_info.get('base_token', {}).get('symbol', '')
            
            # Выводим детали
            print(f"  📊 MEXC: ${mexc_price:.8f}")
            print(f"  📊 DEX:  ${dex_price:.8f} ({dex_name} на {pair_info.get('dex_name', 'Unknown')})")
            print(f"  📈 Спред: {spread_percent:.2f}%")
            print(f"  💧 Ликвидность: ${liquidity:,.0f}")
            
            if validation_result['validation_status'] == 'ok':
                print(f"  ✅ Токены корректно сопоставлены")
            else:
                for warning in validation_result['warnings']:
                    print(f"  {warning}")
    
    return validation_result

async def generate_validation_report():
    """Генерация полного отчета валидации"""
    print(f"{Fore.CYAN}🔍 ПРОВЕРКА СООТВЕТСТВИЯ ТОКЕНОВ MEXC vs DEX")
    print("=" * 60)
    print("Проверяем правильность сопоставления монет...")
    print("=" * 60)
    
    # Проверка API ключей
    if not os.getenv('MEXC_API_KEY'):
        print(f"{Fore.RED}❌ MEXC_API_KEY не найден в .env файле{Style.RESET_ALL}")
        return
    
    validation_results = []
    
    # Проверяем каждый токен
    for symbol in VALIDATION_TOKENS:
        result = await validate_token_pair(symbol)
        validation_results.append(result)
        
        # Пауза между запросами
        await asyncio.sleep(1)
    
    # Анализируем результаты
    print(f"\n{Fore.CYAN}📊 РЕЗУЛЬТАТЫ ВАЛИДАЦИИ:")
    print("=" * 60)
    
    ok_tokens = []
    problematic_tokens = []
    missing_tokens = []
    
    for result in validation_results:
        symbol = result['symbol']
        status = result['validation_status']
        
        if status == 'ok':
            ok_tokens.append(result)
            print(f"✅ {symbol:<12} - Корректно сопоставлен")
        elif status in ['mexc_missing', 'dex_missing']:
            missing_tokens.append(result)
            print(f"❌ {symbol:<12} - Отсутствует на одной из платформ")
        else:
            problematic_tokens.append(result)
            status_text = {
                'price_mismatch': 'Подозрительная разница цен',
                'extreme_spread': 'Экстремальный спред',  
                'high_spread': 'Высокий спред'
            }.get(status, 'Проблемы')
            print(f"⚠️  {symbol:<12} - {status_text}")
    
    # Сохраняем детальный отчет
    report_data = {
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'total_checked': len(validation_results),
            'ok_tokens': len(ok_tokens),
            'problematic_tokens': len(problematic_tokens),
            'missing_tokens': len(missing_tokens)
        },
        'validation_results': validation_results
    }
    
    reports_dir = Path("logs/validation")
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    report_file = reports_dir / f"token_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n{Fore.GREEN}📄 Детальный отчет сохранен: {report_file}{Style.RESET_ALL}")
    
    # Рекомендации
    print(f"\n{Fore.YELLOW}💡 РЕКОМЕНДАЦИИ:")
    print("=" * 60)
    
    if ok_tokens:
        print(f"{Fore.GREEN}✅ БЕЗОПАСНЫЕ токены для торговли ({len(ok_tokens)} шт.):{Style.RESET_ALL}")
        for result in ok_tokens:
            symbol = result['symbol']
            spread = result['price_comparison'].get('spread_percent', 0)
            print(f"   {symbol} (текущий спред: {spread:.2f}%)")
    
    if problematic_tokens:
        print(f"\n{Fore.YELLOW}⚠️ ПРОБЛЕМНЫЕ токены - требуют внимания ({len(problematic_tokens)} шт.):{Style.RESET_ALL}")
        for result in problematic_tokens:
            symbol = result['symbol']
            warnings = result.get('warnings', [])
            print(f"   {symbol}:")
            for warning in warnings:
                print(f"     {warning}")
    
    if missing_tokens:
        print(f"\n{Fore.RED}❌ НЕДОСТУПНЫЕ токены - исключить из торговли ({len(missing_tokens)} шт.):{Style.RESET_ALL}")
        for result in missing_tokens:
            symbol = result['symbol']
            print(f"   {symbol}")
    
    # Итоговая рекомендация
    safe_percentage = len(ok_tokens) / len(validation_results) * 100
    
    print(f"\n{Fore.CYAN}🎯 ИТОГОВАЯ ОЦЕНКА:")
    print(f"Безопасных токенов: {safe_percentage:.1f}%")
    
    if safe_percentage >= 80:
        print(f"{Fore.GREEN}🟢 ОТЛИЧНО - можно запускать бота{Style.RESET_ALL}")
    elif safe_percentage >= 60:
        print(f"{Fore.YELLOW}🟡 ПРИЕМЛЕМО - но мониторьте внимательно{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}🔴 ОПАСНО - много проблемных токенов{Style.RESET_ALL}")
    
    return validation_results

async def quick_price_comparison(symbols: List[str] = None):
    """Быстрое сравнение цен в реальном времени"""
    if not symbols:
        symbols = ["BTC/USDT", "ETH/USDT", "PEPE/USDT"]
    
    print(f"\n{Fore.CYAN}⚡ БЫСТРОЕ СРАВНЕНИЕ ЦЕН (в реальном времени):{Style.RESET_ALL}")
    print("=" * 70)
    print(f"{'Токен':<12} {'MEXC Цена':<15} {'DEX Цена':<15} {'Спред':<10} {'Статус'}")
    print("-" * 70)
    
    for symbol in symbols:
        try:
            # Быстро получаем цены
            mexc_info, dex_info = await asyncio.gather(
                get_mexc_token_info(symbol),
                get_dex_token_info(symbol),
                return_exceptions=True
            )
            
            if (not isinstance(mexc_info, Exception) and mexc_info and 
                not isinstance(dex_info, Exception) and dex_info):
                
                mexc_price = mexc_info['price']
                dex_price = dex_info['price']
                spread = abs(mexc_price - dex_price) / mexc_price * 100
                
                status = "✅ ОК" if spread < 20 else "⚠️ Высокий" if spread < 50 else "🚨 Критич"
                
                print(f"{symbol:<12} ${mexc_price:<14.6f} ${dex_price:<14.6f} {spread:<9.2f}% {status}")
            else:
                print(f"{symbol:<12} {'❌ Ошибка':<30}")
                
        except Exception as e:
            print(f"{symbol:<12} {'❌ Ошибка':<30}")

async def main():
    """Главная функция валидации"""
    try:
        print(f"{Fore.CYAN}🛡️ ИНСТРУМЕНТ ПРОВЕРКИ СООТВЕТСТВИЯ ТОКЕНОВ")
        print("Автор: 24vasilekk")
        print("=" * 60)
        
        # Быстрая проверка нескольких токенов
        await quick_price_comparison(["BTC/USDT", "ETH/USDT", "PEPE/USDT", "DINO/USDT"])
        
        print(f"\n{Fore.YELLOW}Запускаю полную валидацию...{Style.RESET_ALL}")
        
        # Полная валидация
        results = await generate_validation_report()
        
        print(f"\n{Fore.GREEN}✅ Валидация завершена!")
        print(f"📊 Используйте эти данные для настройки списка торговых пар{Style.RESET_ALL}")
        
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}⏹️ Валидация прервана пользователем{Style.RESET_ALL}")
    except Exception as e:
        print(f"\n{Fore.RED}❌ Критическая ошибка валидации: {e}{Style.RESET_ALL}")

if __name__ == "__main__":
    asyncio.run(main())