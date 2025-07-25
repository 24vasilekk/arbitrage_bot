"""
Клиент для получения цен ТОЛЬКО с DexScreener
Автор: 24vasilekk
Путь: src/exchanges/dex_client.py
ОБНОВЛЕН: Только новые токены, убраны стабильные
"""

import aiohttp
import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from ..utils.logger import get_logger

class DEXClient:
    """Клиент для получения цен ТОЛЬКО с DexScreener"""
    
    def __init__(self):
        self.logger = get_logger("dex_client")
        self.session = None
        self._price_cache = {}
        self._cache_ttl = 1  # Кеш на 1 секунду для быстрых обновлений
        
        # Маппинг токенов для поиска в DexScreener - ТОЛЬКО НОВЫЕ ТОКЕНЫ
        self.token_search_mapping = {
            # НОВЫЕ ТОКЕНЫ (25 шт.)
            'DIS/USDT': 'DIS',
            'UPTOP/USDT': 'UPTOP', 
            'IRIS/USDT': 'IRIS',
            'DUPE/USDT': 'DUPE',
            'TAG/USDT': 'TAG',
            'STARTUP/USDT': 'STARTUP',
            'GOG/USDT': 'GOG',
            'TGT/USDT': 'TGT',
            'AURASOL/USDT': 'AURASOL',
            'DINO/USDT': 'DINO',
            'ALTCOIN/USDT': 'ALTCOIN',
            'PEPE/USDT': 'PEPE',
            'ECHO/USDT': 'ECHO',
            'MANYU/USDT': 'MANYU',
            'APETH/USDT': 'APETH',
            'LABUBU/USDT': 'LABUBU',
            'FART/USDT': 'FART',
            'ELDE/USDT': 'ELDE',
            'GP/USDT': 'GP',
            'HOUSE/USDT': 'HOUSE',
            'ZEUS/USDT': 'ZEUS',
            'BR/USDT': 'BR',
            'VSN/USDT': 'VSN',
            'RION/USDT': 'RION',
            'DEVVE/USDT': 'DEVVE'
        }
    
    def add_new_token(self, symbol: str, search_term: str = None):
        """
        ДОБАВЛЕНИЕ НОВОГО ТОКЕНА В СПИСОК
        
        Использование:
        dex_client.add_new_token('NEWTOKEN/USDT', 'NEWTOKEN')
        """
        if search_term is None:
            search_term = symbol.split('/')[0].upper()
        
        self.token_search_mapping[symbol] = search_term
        self.logger.info(f"✅ Добавлен новый токен: {symbol} -> {search_term}")
    
    def remove_token(self, symbol: str):
        """
        УДАЛЕНИЕ ТОКЕНА ИЗ СПИСКА
        
        Использование:
        dex_client.remove_token('OLDTOKEN/USDT')
        """
        if symbol in self.token_search_mapping:
            del self.token_search_mapping[symbol]
            self.logger.info(f"🗑️ Удален токен: {symbol}")
        else:
            self.logger.warning(f"⚠️ Токен {symbol} не найден в списке")
    
    def list_all_tokens(self) -> List[str]:
        """Получить список всех токенов"""
        return list(self.token_search_mapping.keys())
    
    def update_token_mapping(self, new_mapping: Dict[str, str]):
        """
        МАССОВОЕ ОБНОВЛЕНИЕ ТОКЕНОВ
        
        Использование:
        new_tokens = {
            'TOKEN1/USDT': 'TOKEN1',
            'TOKEN2/USDT': 'TOKEN2'
        }
        dex_client.update_token_mapping(new_tokens)
        """
        self.token_search_mapping.update(new_mapping)
        self.logger.info(f"🔄 Обновлено токенов: {len(new_mapping)}")
    
    async def __aenter__(self):
        """Async context manager вход"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),  # Увеличен таймаут
            headers={'User-Agent': 'ArbitrageBot/2.0'}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager выход"""
        if self.session:
            await self.session.close()
    
    def _is_cache_valid(self, symbol: str) -> bool:
        """Проверка валидности кеша для символа"""
        if symbol not in self._price_cache:
            return False
            
        cache_time = self._price_cache[symbol].get('timestamp', 0)
        return datetime.now().timestamp() - cache_time < self._cache_ttl
    
    async def _fetch_dexscreener_price(self, symbol: str) -> Optional[float]:
        """Получение цены с DexScreener"""
        if not self.session:
            return None
            
        try:
            # Получаем токен из маппинга
            search_token = self.token_search_mapping.get(symbol)
            if not search_token:
                base_token = symbol.split('/')[0].upper()
                search_token = base_token
                self.logger.warning(f"⚠️ Токен {symbol} не в маппинге, используем {search_token}")
            
            # Поиск по токену
            url = "https://api.dexscreener.com/latest/dex/search"
            params = {'q': search_token}
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    pairs = data.get('pairs', [])
                    
                    if pairs:
                        # Ищем лучшие пары с USDT/USDC и высокой ликвидностью
                        quality_pairs = []
                        for pair in pairs:
                            quote_symbol = pair.get('quoteToken', {}).get('symbol', '').upper()
                            base_symbol = pair.get('baseToken', {}).get('symbol', '').upper()
                            liquidity = pair.get('liquidity', {}).get('usd', 0)
                            volume_24h = pair.get('volume', {}).get('h24', 0)
                            
                            # Фильтрация для новых токенов (более мягкие требования)
                            if (quote_symbol in ['USDT', 'USDC'] and 
                                base_symbol == search_token and 
                                liquidity > 1000 and    # Снижен лимит для новых токенов
                                volume_24h > 100):      # Снижен лимит объема
                                
                                quality_pairs.append({
                                    'pair': pair,
                                    'score': liquidity * 0.7 + volume_24h * 0.3  # Весовая оценка
                                })
                        
                        if quality_pairs:
                            # Берем 3 лучших пары и усредняем
                            best_pairs = sorted(quality_pairs, 
                                              key=lambda x: x['score'], 
                                              reverse=True)[:3]
                            
                            prices = []
                            for item in best_pairs:
                                price = item['pair'].get('priceUsd')
                                if price:
                                    prices.append(float(price))
                            
                            if prices:
                                # Медианная цена для устойчивости к выбросам
                                prices.sort()
                                if len(prices) == 1:
                                    final_price = prices[0]
                                elif len(prices) == 2:
                                    final_price = sum(prices) / 2
                                else:
                                    final_price = prices[len(prices)//2]  # Медиана
                                
                                self.logger.debug(f"🔍 DexScreener {symbol}: ${final_price:.8f} "
                                               f"(из {len(prices)} пар)")
                                return final_price
                        else:
                            self.logger.warning(f"⚠️ {symbol}: Нет качественных пар (требуется ликвидность >$1k)")
                
                elif response.status == 429:
                    self.logger.warning(f"⚠️ DexScreener rate limit для {symbol}")
                    await asyncio.sleep(1)  # Увеличена пауза при rate limit
                    
        except asyncio.TimeoutError:
            self.logger.warning(f"⏰ DexScreener timeout для {symbol}")
        except Exception as e:
            self.logger.debug(f"❌ DexScreener ошибка для {symbol}: {e}")
        
        return None
    
    async def get_dex_price(self, symbol: str) -> Optional[Dict]:
        """Получение цены ТОЛЬКО с DexScreener"""
        # Проверяем кеш (1 секунда)
        if self._is_cache_valid(symbol):
            cached_data = self._price_cache[symbol]
            self.logger.debug(f"💾 Кеш {symbol}: ${cached_data['price']:.8f}")
            return cached_data
        
        if not self.session:
            await self.__aenter__()
        
        try:
            # Получаем цену с DexScreener с увеличенным таймаутом
            price = await asyncio.wait_for(
                self._fetch_dexscreener_price(symbol),
                timeout=25.0  # Увеличен таймаут для новых токенов
            )
            
            if price and price > 0:
                # Кешируем результат
                result = {
                    'symbol': symbol,
                    'price': price,
                    'sources': ['DexScreener'],
                    'source_count': 1,
                    'timestamp': datetime.now().timestamp()
                }
                
                self._price_cache[symbol] = result
                
                self.logger.debug(f"💱 DEX цена {symbol}: ${price:.8f}")
                return result
            else:
                self.logger.warning(f"⚠️ Не удалось получить цену для {symbol}")
                return None
                
        except asyncio.TimeoutError:
            self.logger.warning(f"⏰ Таймаут получения цены для {symbol}")
            return None
        except Exception as e:
            self.logger.error(f"❌ Ошибка получения DEX цены для {symbol}: {e}")
            return None
    
    async def get_multiple_dex_prices(self, symbols: List[str]) -> Dict[str, Dict]:
        """Получение цен для нескольких символов параллельно"""
        if not self.session:
            await self.__aenter__()
        
        # Уменьшаем semaphore для новых токенов чтобы не перегружать API
        semaphore = asyncio.Semaphore(5)  # Меньше одновременных запросов
        
        async def get_price_with_semaphore(symbol):
            async with semaphore:
                return symbol, await self.get_dex_price(symbol)
        
        # Запускаем задачи
        tasks = [get_price_with_semaphore(symbol) for symbol in symbols]
        
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Собираем результаты
            prices = {}
            successful = 0
            
            for result in results:
                if isinstance(result, tuple) and len(result) == 2:
                    symbol, price_data = result
                    if isinstance(price_data, dict) and not isinstance(price_data, Exception):
                        prices[symbol] = price_data
                        successful += 1
            
            self.logger.info(f"📊 Получено DEX цен: {successful}/{len(symbols)}")
            return prices
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка получения множественных DEX цен: {e}")
            return {}
    
    def clear_cache(self):
        """Очистка кеша цен"""
        self._price_cache.clear()
        self.logger.debug("🧹 Кеш DEX цен очищен")
    
    async def close(self):
        """Закрытие клиента"""
        if self.session:
            await self.session.close()
            self.logger.info("🔌 DEX клиент закрыт")