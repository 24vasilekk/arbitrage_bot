#!/usr/bin/env python3
"""
Инструмент управления токенами для арбитражного бота
Автор: 24vasilekk
Путь: manage_tokens.py (в корне проекта)

Использование:
python manage_tokens.py --list                          # Показать все токены
python manage_tokens.py --add "NEWTOKEN/USDT"          # Добавить токен
python manage_tokens.py --remove "OLDTOKEN/USDT"       # Удалить токен
python manage_tokens.py --check "NEWTOKEN/USDT"        # Проверить токен
python manage_tokens.py --update-from-mexc             # Обновить из MEXC
"""

import asyncio
import sys
import os
import json
import argparse
import yaml
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

class TokenManager:
    """Менеджер для управления списком токенов"""
    
    def __init__(self):
        self.config_file = Path("config/settings.yaml")
        self.dex_client_file = Path("src/exchanges/dex_client.py")
        self.load_config()
    
    def load_config(self):
        """Загрузка текущей конфигурации"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
        except FileNotFoundError:
            print(f"❌ Конфигурация не найдена: {self.config_file}")
            self.config = {'trading': {'symbols': []}}
    
    def save_config(self):
        """Сохранение конфигурации"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, 
                         allow_unicode=True, sort_keys=False)
            print(f"✅ Конфигурация сохранена: {self.config_file}")
        except Exception as e:
            print(f"❌ Ошибка сохранения конфигурации: {e}")
    
    def get_tokens(self) -> list:
        """Получить список текущих токенов"""
        return self.config.get('trading', {}).get('symbols', [])
    
    def add_token(self, symbol: str, search_term: str = None) -> bool:
        """Добавить новый токен"""
        if not symbol.endswith('/USDT'):
            symbol += '/USDT'
        
        current_tokens = self.get_tokens()
        
        if symbol in current_tokens:
            print(f"⚠️ Токен {symbol} уже существует в списке")
            return False
        
        # Добавляем в конфигурацию
        current_tokens.append(symbol)
        self.config['trading']['symbols'] = current_tokens
        
        # Добавляем в DEX клиент
        if search_term is None:
            search_term = symbol.split('/')[0].upper()
        
        self.update_dex_client_mapping(symbol, search_term, action='add')
        
        print(f"✅ Добавлен токен: {symbol} -> {search_term}")
        return True
    
    def remove_token(self, symbol: str) -> bool:
        """Удалить токен"""
        if not symbol.endswith('/USDT'):
            symbol += '/USDT'
        
        current_tokens = self.get_tokens()
        
        if symbol not in current_tokens:
            print(f"⚠️ Токен {symbol} не найден в списке")
            return False
        
        # Удаляем из конфигурации
        current_tokens.remove(symbol)
        self.config['trading']['symbols'] = current_tokens
        
        # Удаляем из DEX клиента
        self.update_dex_client_mapping(symbol, action='remove')
        
        print(f"🗑️ Удален токен: {symbol}")
        return True
    
    def update_dex_client_mapping(self, symbol: str, search_term: str = None, action: str = 'add'):
        """Обновление маппинга в DEX клиенте"""
        try:
            with open(self.dex_client_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Находим секцию token_search_mapping
            start_marker = "self.token_search_mapping = {"
            end_marker = "}"
            
            start_idx = content.find(start_marker)
            if start_idx == -1:
                print("⚠️ Не найден token_search_mapping в DEX клиенте")
                return
            
            # Находим конец маппинга
            brace_count = 0
            end_idx = start_idx + len(start_marker)
            for i, char in enumerate(content[start_idx + len(start_marker):], start_idx + len(start_marker)):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    if brace_count == 0:
                        end_idx = i
                        break
                    brace_count -= 1
            
            # Извлекаем текущий маппинг
            mapping_section = content[start_idx:end_idx + 1]
            
            if action == 'add' and search_term:
                # Добавляем новый токен перед закрывающей скобкой
                new_line = f"            '{symbol}': '{search_term}',\n"
                insert_pos = mapping_section.rfind('}')
                updated_mapping = mapping_section[:insert_pos] + f"            '{symbol}': '{search_term}'\n        " + mapping_section[insert_pos:]
            
            elif action == 'remove':
                # Удаляем строку с токеном
                lines = mapping_section.split('\n')
                updated_lines = [line for line in lines if f"'{symbol}'" not in line]
                updated_mapping = '\n'.join(updated_lines)
            
            else:
                return
            
            # Обновляем файл
            new_content = content[:start_idx] + updated_mapping + content[end_idx + 1:]
            
            with open(self.dex_client_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            print(f"✅ Обновлен DEX клиент: {action} {symbol}")
            
        except Exception as e:
            print(f"❌ Ошибка обновления DEX клиента: {e}")
    
    def list_tokens(self):
        """Показать список всех токенов"""
        tokens = self.get_tokens()
        
        print(f"\n{Fore.CYAN}📊 ТЕКУЩИЙ СПИСОК ТОКЕНОВ ({len(tokens)} шт.):{Style.RESET_ALL}")
        print("=" * 50)
        
        for i, token in enumerate(tokens, 1):
            print(f"{i:2d}. {token}")
        
        if not tokens:
            print("📭 Список пуст")

async def check_token_availability(symbol: str):
    """Проверка доступности токена на MEXC и DexScreener"""
    print(f"\n🔍 Проверяем доступность {symbol}...")
    
    # Проверка MEXC
    try:
        import ccxt
        mexc = ccxt.mexc({
            'apiKey': os.getenv('MEXC_API_KEY'),
            'secret': os.getenv('MEXC_SECRET'),
            'sandbox': True,
            'enableRateLimit': True
        })
        
        markets = mexc.load_markets()
        mexc_available = symbol in markets
        
        if mexc_available:
            print(f"  ✅ MEXC: Доступен")
        else:
            print(f"  ❌ MEXC: НЕ найден")
        
        mexc.close()
        
    except Exception as e:
        print(f"  ❌ MEXC: Ошибка проверки - {e}")
        mexc_available = False
    
    # Проверка DexScreener
    try:
        from src.exchanges.dex_client import DEXClient
        
        async with DEXClient() as dex_client:
            price_data = await dex_client.get_dex_price(symbol)
            
            if price_data:
                price = price_data['price']
                print(f"  ✅ DEX: Доступен, цена ${price:.8f}")
                dex_available = True
            else:
                print(f"  ❌ DEX: НЕ найден или нет ликвидности")
                dex_available = False
                
    except Exception as e:
        print(f"  ❌ DEX: Ошибка проверки - {e}")
        dex_available = False
    
    # Итог
    if mexc_available and dex_available:
        print(f"  🎉 {Fore.GREEN}ГОТОВ К ТОРГОВЛЕ{Style.RESET_ALL}")
        return True
    elif mexc_available or dex_available:
        print(f"  ⚠️ {Fore.YELLOW}ЧАСТИЧНО ДОСТУПЕН{Style.RESET_ALL}")
        return False
    else:
        print(f"  🚨 {Fore.RED}НЕ ДОСТУПЕН{Style.RESET_ALL}")
        return False

async def update_from_mexc():
    """Обновление списка из доступных токенов MEXC"""
    print(f"\n🔄 Получение списка токенов с MEXC...")
    
    try:
        import ccxt
        mexc = ccxt.mexc({
            'apiKey': os.getenv('MEXC_API_KEY'),
            'secret': os.getenv('MEXC_SECRET'),
            'sandbox': True,
            'enableRateLimit': True
        })
        
        markets = mexc.load_markets()
        
        # Фильтруем только USDT пары
        usdt_pairs = [symbol for symbol in markets.keys() if symbol.endswith('/USDT')]
        
        print(f"📊 Найдено {len(usdt_pairs)} USDT пар на MEXC")
        
        # Показываем первые 50 для выбора
        print(f"\n{Fore.CYAN}🎯 ДОСТУПНЫЕ ДЛЯ ДОБАВЛЕНИЯ (первые 50):{Style.RESET_ALL}")
        for i, pair in enumerate(usdt_pairs[:50], 1):
            print(f"{i:2d}. {pair}")
        
        print(f"\n💡 Используйте: python manage_tokens.py --add \"SYMBOL/USDT\"")
        
        mexc.close()
        
    except Exception as e:
        print(f"❌ Ошибка получения данных MEXC: {e}")

def parse_args():
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(description='Управление токенами арбитражного бота')
    
    parser.add_argument('--list', action='store_true',
                       help='Показать все текущие токены')
    parser.add_argument('--add', metavar='SYMBOL',
                       help='Добавить новый токен (например: NEWTOKEN/USDT)')
    parser.add_argument('--remove', metavar='SYMBOL',
                       help='Удалить токен (например: OLDTOKEN/USDT)')
    parser.add_argument('--check', metavar='SYMBOL',
                       help='Проверить доступность токена')
    parser.add_argument('--search-term', metavar='TERM',
                       help='Поисковый термин для DexScreener (опционально)')
    parser.add_argument('--update-from-mexc', action='store_true',
                       help='Показать доступные токены с MEXC')
    
    return parser.parse_args()

async def main():
    """Главная функция"""
    args = parse_args()
    
    print(f"{Fore.CYAN}🔧 МЕНЕДЖЕР ТОКЕНОВ АРБИТРАЖНОГО БОТА")
    print("Автор: 24vasilekk")
    print("=" * 50)
    
    manager = TokenManager()
    
    if args.list:
        manager.list_tokens()
    
    elif args.add:
        symbol = args.add.upper()
        search_term = args.search_term
        
        if manager.add_token(symbol, search_term):
            manager.save_config()
            
            # Проверяем доступность
            await check_token_availability(symbol)
    
    elif args.remove:
        symbol = args.remove.upper()
        
        if manager.remove_token(symbol):
            manager.save_config()
    
    elif args.check:
        symbol = args.check.upper()
        await check_token_availability(symbol)
    
    elif args.update_from_mexc:
        await update_from_mexc()
    
    else:
        print("❌ Не указано действие. Используйте --help для справки")
        print("\n💡 Примеры использования:")
        print("   python manage_tokens.py --list")
        print("   python manage_tokens.py --add \"NEWTOKEN/USDT\"")
        print("   python manage_tokens.py --remove \"OLDTOKEN/USDT\"")
        print("   python manage_tokens.py --check \"PEPE/USDT\"")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}⏹️ Операция прервана{Style.RESET_ALL}")
    except Exception as e:
        print(f"\n{Fore.RED}❌ Ошибка: {e}{Style.RESET_ALL}")