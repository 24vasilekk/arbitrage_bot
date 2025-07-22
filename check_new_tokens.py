#!/usr/bin/env python3
"""
Скрипт для проверки новых токенов перед запуском бота
Автор: 24vasilekk
Путь: check_new_tokens.py (в корне проекта)

Запуск:
python check_new_tokens.py
"""

import asyncio
import sys
import os
import json
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

# Новые токены для проверки
NEW_TOKENS = [
    "DIS/USDT", "UPTOP/USDT", "IRIS/USDT", "DUPE/USDT", "TAG/USDT",
    "STARTUP/USDT", "GOG/USDT", "TGT/USDT", "AURASOL/USDT", "DINO/USDT",
    "ALTCOIN/USDT", "PEPE/USDT", "ECHO/USDT", "MANYU/USDT", 
    "APETH/USDT", "LABUBU/USDT", "FART/USDT", "ELDE/USDT", "GP/USDT",
    "HOUSE/USDT", "ZEUS/USDT", "BR/USDT", "VSN/USDT", "RION/USDT", "DEVVE/USDT"
]

# Стабильные токены для диверсификации
STABLE_TOKENS = [
    "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "ADA/USDT",
    "XRP/USDT", "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "MATIC/USDT",
    "UNI/USDT", "LTC/USDT", "ATOM/USDT", "NEAR/USDT", "SHIB/USDT"
]

async def check_mexc_availability():
    """Проверка доступности токенов на MEXC"""
    print(f"{Fore.YELLOW}🔍 Проверка доступности токенов на MEXC...{Style.RESET_ALL}")
    
    try:
        from src.exchanges.mexc_client import MEXCClient
        
        mexc_client = MEXCClient()
        
        # Получаем список всех рынков MEXC
        markets = mexc_client.exchange.markets
        available_markets = list(markets.keys())
        
        print(f"{Fore.GREEN}✅ MEXC подключен. Всего рынков: {len(available_markets)}{Style.RESET_ALL}")
        
        available_tokens = []
        missing_tokens = []
        
        all_tokens = NEW_TOKENS + STABLE_TOKENS
        
        for token in all_tokens:
            if token in markets:
                available_tokens.append(token)
                market_info = markets[token]
                min_amount = market_info.get('limits', {}).get('amount', {}).get('min', 'N/A')
                print(f"  {Fore.GREEN}✅{Style.RESET_ALL} {token:<15} - доступен (мин. размер: {min_amount})")
            else:
                missing_tokens.append(token)
                print(f"  {Fore.RED}❌{Style.RESET_ALL} {token:<15} - НЕ найден")
                
                # Поиск похожих названий
                base_name = token.split('/')[0].lower()
                similar = [market for market in available_markets 
                          if base_name in market.lower()]
                if similar:
                    print(f"     {Fore.CYAN}💡 Похожие: {', '.join(similar[:3])}{Style.RESET_ALL}")
        
        print(f"\n{Fore.CYAN}📊 MEXC Итого: {len(available_tokens)}/{len(all_tokens)} токенов доступны{Style.RESET_ALL}")
        
        if missing_tokens:
            print(f"\n{Fore.YELLOW}⚠️ Токены НЕ найденные на MEXC ({len(missing_tokens)}):{Style.RESET_ALL}")
            for i, token in enumerate(missing_tokens, 1):
                print(f"   {i:2d}. {token}")
        
        mexc_client.close_connection()
        return available_tokens
        
    except ImportError as e:
        print(f"{Fore.RED}❌ Ошибка импорта MEXC клиента: {e}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}🔧 Убедитесь, что все файлы на месте{Style.RESET_ALL}")
        return []
    except Exception as e:
        print(f"{Fore.RED}❌ Ошибка проверки MEXC: {e}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}🔧 Проверьте API ключи в .env файле{Style.RESET_ALL}")
        return []

async def check_dex_prices():
    """Проверка доступности цен через DEX источники"""
    print(f"\n{Fore.YELLOW}🔍 Проверка цен через DEX источники...{Style.RESET_ALL}")
    
    try:
        from src.exchanges.dex_client import DEXClient
        
        successful = []
        failed = []
        price_info = {}
        
        async with DEXClient() as dex_client:
            all_tokens = NEW_TOKENS + STABLE_TOKENS
            
            for i, token in enumerate(all_tokens, 1):
                print(f"  🔄 {i:2d}/{len(all_tokens)} Проверяем {token}...", end="")
                
                try:
                    price_data = await dex_client.get_dex_price(token)
                    
                    if price_data and price_data.get('price', 0) > 0:
                        price = price_data['price']
                        sources = price_data.get('sources', [])
                        source_count = len(sources)
                        
                        price_info[token] = {
                            'price': price,
                            'sources': sources,
                            'source_count': source_count
                        }
                        
                        print(f" {Fore.GREEN}✅ ${price:.6f} ({source_count} источников){Style.RESET_ALL}")
                        successful.append(token)
                    else:
                        print(f" {Fore.RED}❌ цена не получена{Style.RESET_ALL}")
                        failed.append(token)
                        
                    # Пауза между запросами чтобы не получить rate limit
                    if i % 5 == 0:
                        await asyncio.sleep(2)
                    else:
                        await asyncio.sleep(0.5)
                        
                except Exception as e:
                    print(f" {Fore.RED}❌ ошибка: {str(e)[:50]}...{Style.RESET_ALL}")
                    failed.append(token)
        
        print(f"\n{Fore.CYAN}📊 DEX Итого: {len(successful)}/{len(all_tokens)} токенов{Style.RESET_ALL}")
        
        if failed:
            print(f"\n{Fore.YELLOW}⚠️ Токены БЕЗ DEX цен ({len(failed)}):{Style.RESET_ALL}")
            for i, token in enumerate(failed, 1):
                print(f"   {i:2d}. {token}")
        
        return successful, price_info
        
    except ImportError as e:
        print(f"{Fore.RED}❌ Ошибка импорта DEX клиента: {e}{Style.RESET_ALL}")
        return [], {}
    except Exception as e:
        print(f"{Fore.RED}❌ Ошибка проверки DEX: {e}{Style.RESET_ALL}")
        return [], {}

def generate_working_config(mexc_available, dex_available, price_info):
    """Генерация рабочей конфигурации с проверенными токенами"""
    
    # Находим токены, доступные в обеих системах
    working_new_tokens = list(set(mexc_available) & set(dex_available) & set(NEW_TOKENS))
    working_stable_tokens = list(set(mexc_available) & set(dex_available) & set(STABLE_TOKENS))
    
    print(f"\n{Fore.GREEN}✅ Полностью рабочих НОВЫХ токенов: {len(working_new_tokens)}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}✅ Полностью рабочих СТАБИЛЬНЫХ токенов: {len(working_stable_tokens)}{Style.RESET_ALL}")
    
    # Сортируем новые токены по качеству источников данных
    working_new_tokens_sorted = sorted(working_new_tokens, 
        key=lambda x: price_info.get(x, {}).get('source_count', 0), 
        reverse=True)
    
    # Объединяем все рабочие токены
    all_working_tokens = working_new_tokens_sorted + working_stable_tokens
    
    # Ограничиваем до 40 токенов
    final_tokens = all_working_tokens[:40]
    
    # Генерируем конфигурацию
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    config_content = f'''# Автогенерированная конфигурация с проверенными токенами
# Дата генерации: {timestamp}
# Проверено: {len(working_new_tokens)} новых + {len(working_stable_tokens)} стабильных токенов

trading:
  # Основные параметры (НЕ ИЗМЕНЯЙТЕ БЕЗ ПОНИМАНИЯ!)
  min_spread_percent: 7.5
  target_spread_percent: 1.5
  max_position_size: 100
  test_mode: true  # ОБЯЗАТЕЛЬНО для начала!
  
  # ПРОВЕРЕННЫЕ ТОКЕНЫ ({len(final_tokens)} шт.)
  symbols:
'''
    
    # Добавляем новые токены с информацией о качестве
    if working_new_tokens_sorted:
        config_content += f'    # НОВЫЕ ТОКЕНЫ ({len(working_new_tokens_sorted)} шт.) - отсортированы по качеству данных\n'
        for token in working_new_tokens_sorted:
            sources = price_info.get(token, {}).get('source_count', 0)
            price = price_info.get(token, {}).get('price', 0)
            config_content += f'    - "{token}"  # ${price:.6f}, источников: {sources}\n'
    
    # Добавляем стабильные токены
    if working_stable_tokens:
        config_content += f'\n    # СТАБИЛЬНЫЕ ТОКЕНЫ ({len(working_stable_tokens)} шт.)\n'
        for token in working_stable_tokens:
            price = price_info.get(token, {}).get('price', 0)
            config_content += f'    - "{token}"  # ${price:.2f}\n'
    
    # Сохраняем в файл
    config_dir = Path("config")
    config_dir.mkdir(exist_ok=True)
    
    config_file = config_dir / "working_tokens.yaml"
    
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(config_content)
        
        print(f"\n{Fore.GREEN}💾 Рабочая конфигурация сохранена: {config_file}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}📋 Всего токенов в конфиге: {len(final_tokens)}{Style.RESET_ALL}")
        
        return final_tokens, str(config_file)
        
    except Exception as e:
        print(f"{Fore.RED}❌ Ошибка сохранения конфигурации: {e}{Style.RESET_ALL}")
        return final_tokens, None

def save_check_report(mexc_available, dex_available, price_info, working_tokens):
    """Сохранение детального отчета проверки"""
    try:
        reports_dir = Path("logs/reports")
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        report_data = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'mexc_available': len(mexc_available),
                'dex_available': len(dex_available),
                'working_tokens': len(working_tokens),
                'total_checked': len(NEW_TOKENS) + len(STABLE_TOKENS)
            },
            'mexc_tokens': mexc_available,
            'dex_tokens': dex_available,
            'working_tokens': working_tokens,
            'price_info': price_info,
            'new_tokens_checked': NEW_TOKENS,
            'stable_tokens_checked': STABLE_TOKENS
        }
        
        report_file = reports_dir / f"token_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"{Fore.GREEN}📄 Детальный отчет сохранен: {report_file}{Style.RESET_ALL}")
        
    except Exception as e:
        print(f"{Fore.YELLOW}⚠️ Не удалось сохранить отчет: {e}{Style.RESET_ALL}")

def print_recommendations(working_tokens, config_file):
    """Вывод рекомендаций по использованию"""
    print(f"\n{Fore.CYAN}=" * 60)
    print("🎯 РЕЗУЛЬТАТ ПРОВЕРКИ И РЕКОМЕНДАЦИИ")
    print("=" * 60)
    
    working_new = [t for t in working_tokens if t in NEW_TOKENS]
    working_stable = [t for t in working_tokens if t in STABLE_TOKENS]
    
    print(f"{Fore.GREEN}✅ Новых рабочих токенов: {len(working_new)}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}✅ Стабильных рабочих токенов: {len(working_stable)}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}🎉 Всего готовых к торговле: {len(working_tokens)}{Style.RESET_ALL}")
    
    if len(working_tokens) >= 10:
        status_emoji = "🟢"
        status_text = "ОТЛИЧНО - можно запускать бота"
    elif len(working_tokens) >= 5:
        status_emoji = "🟡"
        status_text = "НЕПЛОХО - можно тестировать"
    else:
        status_emoji = "🔴"
        status_text = "МАЛО токенов - нужно разбираться с проблемами"
    
    print(f"\n{status_emoji} Статус: {status_text}")
    
    print(f"\n{Fore.YELLOW}💡 РЕКОМЕНДАЦИИ ПО ЗАПУСКУ:{Style.RESET_ALL}")
    
    if config_file:
        print("1. 📝 ИСПОЛЬЗУЙТЕ СГЕНЕРИРОВАННУЮ КОНФИГУРАЦИЮ:")
        print(f"   cp {config_file} config/settings.yaml")
    
    print("\n2. 🧪 НАЧНИТЕ С ТЕСТОВОГО РЕЖИМА:")
    if len(working_tokens) >= 5:
        sample_tokens = working_tokens[:5]
        print(f"   python run.py --test-mode --symbols \"{','.join(sample_tokens)}\"")
    
    print("\n3. ⚙️ НАСТРОЙКИ БЕЗОПАСНОСТИ:")
    print("   - Убедитесь: TEST_MODE=true в .env")
    print("   - Установите: MAX_POSITION_SIZE=10-50 для начала")
    print("   - Мониторьте логи на предмет ошибок")
    
    print("\n4. 🚀 ПЕРЕХОД К БОЕВОМУ РЕЖИМУ (ТОЛЬКО ПОСЛЕ ТЕСТОВ):")
    print("   - Убедитесь в стабильной работе 24+ часа")
    print("   - Проверьте все логи на ошибки")
    print("   - Используйте небольшие суммы!")
    
    if working_new:
        print(f"\n{Fore.CYAN}🆕 ЛУЧШИЕ НОВЫЕ ТОКЕНЫ для тестирования:{Style.RESET_ALL}")
        for i, token in enumerate(working_new[:5], 1):
            print(f"   {i}. {token}")

async def main():
    """Основная функция проверки"""
    print(f"{Fore.CYAN}🚀 ПРОВЕРКА НОВЫХ ТОКЕНОВ ДЛЯ АРБИТРАЖНОГО БОТА")
    print("=" * 60)
    print("Автор: 24vasilekk")
    print("Email: 24vasilekk@gmail.com")
    print("=" * 60)
    
    # Проверка переменных окружения
    if not os.getenv('MEXC_API_KEY'):
        print(f"{Fore.RED}❌ MEXC_API_KEY не найден в .env файле{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}🔧 Создайте .env из .env.example и добавьте API ключи{Style.RESET_ALL}")
        return
    
    if not os.getenv('MEXC_SECRET'):
        print(f"{Fore.RED}❌ MEXC_SECRET не найден в .env файле{Style.RESET_ALL}")
        return
    
    print(f"{Fore.GREEN}✅ API ключи найдены{Style.RESET_ALL}")
    
    start_time = datetime.now()
    
    # Проверяем MEXC
    mexc_available = await check_mexc_availability()
    
    # Проверяем DEX источники
    dex_available, price_info = await check_dex_prices()
    
    # Генерируем рабочую конфигурацию
    working_tokens = list(set(mexc_available) & set(dex_available))
    config_file = None
    
    if working_tokens:
        working_tokens, config_file = generate_working_config(
            mexc_available, dex_available, price_info)
    
    # Сохраняем детальный отчет
    save_check_report(mexc_available, dex_available, price_info, working_tokens)
    
    # Выводим рекомендации
    print_recommendations(working_tokens, config_file)
    
    # Финальная статистика
    end_time = datetime.now()
    duration = end_time - start_time
    
    print(f"\n{Fore.CYAN}⏱️  Время проверки: {duration.total_seconds():.1f} секунд")
    print(f"📊 Проверено токенов: {len(NEW_TOKENS + STABLE_TOKENS)}")
    print(f"🎯 Готовых к работе: {len(working_tokens)}")
    print(f"✅ Проверка завершена!{Style.RESET_ALL}")
    
    print(f"\n{Fore.GREEN}▶️  СЛЕДУЮЩИЙ ШАГ - ЗАПУСК ТЕСТИРОВАНИЯ:{Style.RESET_ALL}")
    if working_tokens:
        test_tokens = working_tokens[:3]  # Берем топ-3 для тестирования
        print(f"python run.py --test-mode --symbols \"{','.join(test_tokens)}\"")
    
    print(f"{Style.RESET_ALL}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}⏹️  Проверка прервана пользователем{Style.RESET_ALL}")
    except Exception as e:
        print(f"\n{Fore.RED}❌ Критическая ошибка: {e}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}🔧 Проверьте установку зависимостей: pip install -r requirements.txt{Style.RESET_ALL}")