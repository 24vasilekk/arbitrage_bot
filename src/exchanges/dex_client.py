"""
Клиент для получения цен с DEX бирж и агрегаторов
Автор: 24vasilekk
Путь: src/exchanges/dex_client.py
ОБНОВЛЕН: Добавлены новые монеты
"""

import aiohttp
import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from ..utils.logger import get_logger

class DEXClient:
    """Клиент для получения цен с DEX источников"""
    
    def __init__(self):
        self.logger = get_logger("dex_client")
        self.session = None
        self._price_cache = {}
        self._cache_ttl = 10  # Кеш на 10 секунд
        
        # ОБНОВЛЕННЫЙ маппинг символов для разных API
        self.coingecko_mapping = {
            # НОВЫЕ ДОБАВЛЕННЫЕ МОНЕТЫ
            'DIS/USDT': 'dis-protocol',           # DIS Protocol
            'UPTOP/USDT': 'uptop',                # UPTOP
            'IRIS/USDT': 'iris-network',          # IRISnet
            'DUPE/USDT': 'dupe',                  # DUPE
            'TAG/USDT': 'tag-protocol',           # TAG Protocol
            'STARTUP/USDT': 'startup',            # Startup
            'GOG/USDT': 'guild-of-guardians',     # Guild of Guardians
            'TGT/USDT': 'target',                 # Target
            'AURASOL/USDT': 'aurasol',            # AuraSol
            'DINO/USDT': 'dinoswap',              # DinoSwap
            'ALTCOIN/USDT': 'altcoin',            # AltCoin
            'PEPE/USDT': 'pepe',                  # PEPE (вместо PepeOnTron)
            'ECHO/USDT': 'echo-protocol',         # Echo Protocol
            'MANYU/USDT': 'manyu',                # Manyu
            'APETH/USDT': 'apeth',                # apETH
            'LABUBU/USDT': 'labubu',              # Labubu
            'FART/USDT': 'fartcoin',              # FartBoy/FartCoin
            'ELDE/USDT': 'elde',                  # ELDE
            'GP/USDT': 'gp-token',                # GP Token
            'HOUSE/USDT': 'house',                # House
            'ZEUS/USDT': 'zeus',                  # Zeus (вместо ZeusETH)
            'BR/USDT': 'br-token',                # BR Token
            'VSN/USDT': 'vision-network',         # Vision Network
            'RION/USDT': 'rion',                  # RION
            'DEVVE/USDT': 'devve',                # DEVVE
            
            # СТАБИЛЬНЫЕ МОНЕТЫ (проверенные ID)
            'BTC/USDT': 'bitcoin',
            'ETH/USDT': 'ethereum',
            'BNB/USDT': 'binancecoin',
            'SOL/USDT': 'solana',
            'ADA/USDT': 'cardano',
            'XRP/USDT': 'ripple',
            'DOGE/USDT': 'dogecoin',
            'AVAX/USDT': 'avalanche-2',
            'LINK/USDT': 'chainlink',
            'MATIC/USDT': 'matic-network',
            'UNI/USDT': 'uniswap',
            'LTC/USDT': 'litecoin',
            'ATOM/USDT': 'cosmos',
            'NEAR/USDT': 'near',
            'SHIB/USDT': 'shiba-inu'
        }
    
    async def __aenter__(self):
        """Async context manager вход"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15),  # Увеличен таймаут
            headers={'User-Agent': 'ArbitrageBot/1.0'}
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
    
    async def _fetch_coingecko_price(self, symbol: str) -> Optional[float]:
        """Получение цены с CoinGecko"""
        if not self.session:
            return None
            
        coingecko_id = self.coingecko_mapping.get(symbol)
        if not coingecko_id:
            self.logger.debug(f"⚠️ Символ {symbol} не найден в CoinGecko mapping")
            return None
        
        try:
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {
                'ids': coingecko_id,
                'vs_currencies': 'usd'
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    price = data.get(coingecko_id, {}).get('usd')
                    
                    if price:
                        self.logger.debug(f"🔍 CoinGecko {symbol}: ${price:.6f}")
                        return float(price)
                elif response.status == 429:
                    self.logger.warning(f"⚠️ CoinGecko rate limit для {symbol}")
                else:
                    self.logger.warning(f"⚠️ CoinGecko API error {response.status} для {symbol}")
                    
        except asyncio.TimeoutError:
            self.logger.warning(f"⏰ CoinGecko timeout для {symbol}")
        except Exception as e:
            self.logger.error(f"❌ Ошибка CoinGecko для {symbol}: {e}")
        
        return None
    
    async def _fetch_binance_spot_price(self, symbol: str) -> Optional[float]:
        """Получение цены с Binance Spot для сравнения"""
        if not self.session:
            return None
            
        try:
            # Преобразуем символ для Binance API
            binance_symbol = symbol.replace('/', '').upper()
            
            url = "https://api.binance.com/api/v3/ticker/price"
            params = {'symbol': binance_symbol}
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    price = data.get('price')
                    
                    if price:
                        price = float(price)
                        self.logger.debug(f"🔍 Binance Spot {symbol}: ${price:.6f}")
                        return price
                elif response.status == 400:
                    # Символ не существует на Binance - это нормально
                    self.logger.debug(f"⚠️ {symbol} не найден на Binance")
                else:
                    self.logger.warning(f"⚠️ Binance API error {response.status} для {symbol}")
                    
        except asyncio.TimeoutError:
            self.logger.warning(f"⏰ Binance timeout для {symbol}")
        except Exception as e:
            self.logger.debug(f"❌ Ошибка Binance для {symbol}: {e}")
        
        return None
    
    async def _fetch_dexscreener_price(self, symbol: str) -> Optional[float]:
        """Получение средней цены с DexScreener (реальные DEX данные)"""
        if not self.session:
            return None
            
        try:
            # Получаем базовую монету из символа
            base_token = symbol.split('/')[0].upper()
            
            # Поиск по символу токена
            url = f"https://api.dexscreener.com/latest/dex/search"
            params = {'q': base_token}
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    pairs = data.get('pairs', [])
                    
                    if pairs:
                        # Берем пары с USDT/USDC и хорошей ликвидностью
                        stable_pairs = []
                        for pair in pairs:
                            quote_symbol = pair.get('quoteToken', {}).get('symbol', '').upper()
                            base_symbol = pair.get('baseToken', {}).get('symbol', '').upper()
                            liquidity = pair.get('liquidity', {}).get('usd', 0)
                            
                            if (quote_symbol in ['USDT', 'USDC'] and 
                                base_symbol == base_token and 
                                liquidity > 50000):  # Минимум $50k ликвидности
                                stable_pairs.append(pair)
                        
                        if stable_pairs:
                            # Средняя цена по топ-5 парам
                            top_pairs = sorted(stable_pairs, 
                                             key=lambda x: x.get('liquidity', {}).get('usd', 0),
                                             reverse=True)[:5]
                            
                            prices = []
                            for pair in top_pairs:
                                price = pair.get('priceUsd')
                                if price:
                                    prices.append(float(price))
                            
                            if prices:
                                avg_price = sum(prices) / len(prices)
                                self.logger.debug(f"🔍 DexScreener {symbol}: ${avg_price:.6f} "
                                               f"(из {len(prices)} пар)")
                                return avg_price
                elif response.status == 429:
                    self.logger.warning(f"⚠️ DexScreener rate limit для {symbol}")
                else:
                    self.logger.warning(f"⚠️ DexScreener API error {response.status} для {symbol}")
                    
        except asyncio.TimeoutError:
            self.logger.warning(f"⏰ DexScreener timeout для {symbol}")
        except Exception as e:
            self.logger.debug(f"❌ Ошибка DexScreener для {symbol}: {e}")
        
        return None
    
    async def _fetch_dexscreener_by_name(self, symbol: str) -> Optional[float]:
        """
        Fallback метод: поиск цены по названию токена в DexScreener
        Используется для токенов, не найденных в CoinGecko
        """
        if not self.session:
            return None
            
        try:
            base_token = symbol.split('/')[0].upper()
            
            # Альтернативные названия для поиска
            search_terms = [
                base_token,
                base_token.lower(),
                f"${base_token}",
            ]
            
            for term in search_terms:
                url = f"https://api.dexscreener.com/latest/dex/search"
                params = {'q': term}
                
                try:
                    async with self.session.get(url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            pairs = data.get('pairs', [])
                            
                            # Ищем точные совпадения
                            exact_matches = []
                            for pair in pairs:
                                base_symbol = pair.get('baseToken', {}).get('symbol', '').upper()
                                quote_symbol = pair.get('quoteToken', {}).get('symbol', '').upper()
                                liquidity = pair.get('liquidity', {}).get('usd', 0)
                                
                                if (base_symbol == base_token and 
                                    quote_symbol in ['USDT', 'USDC'] and 
                                    liquidity > 10000):  # Минимум $10k ликвидности
                                    exact_matches.append(pair)
                            
                            if exact_matches:
                                # Берем пару с наибольшей ликвидностью
                                best_pair = max(exact_matches, 
                                              key=lambda x: x.get('liquidity', {}).get('usd', 0))
                                price = best_pair.get('priceUsd')
                                
                                if price:
                                    price = float(price)
                                    self.logger.info(f"🎯 DexScreener fallback {symbol}: ${price:.6f}")
                                    return price
                        
                        # Пауза между запросами
                        await asyncio.sleep(0.5)
                        
                except Exception as e:
                    continue
                        
        except Exception as e:
            self.logger.debug(f"❌ DexScreener fallback ошибка для {symbol}: {e}")
        
        return None
    
    async def get_dex_price(self, symbol: str) -> Optional[Dict]:
        """Получение агрегированной цены DEX с нескольких источников"""
        # Проверяем кеш
        if self._is_cache_valid(symbol):
            cached_data = self._price_cache[symbol]
            self.logger.debug(f"💾 Кеш {symbol}: ${cached_data['price']:.6f}")
            return cached_data
        
        if not self.session:
            await self.__aenter__()
        
        # Получаем цены из разных источников параллельно
        tasks = [
            self._fetch_coingecko_price(symbol),
            self._fetch_binance_spot_price(symbol),
            self._fetch_dexscreener_price(symbol)
        ]
        
        try:
            # Запускаем с таймаутом
            prices = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=12.0
            )
            
            # Фильтруем успешные результаты
            valid_prices = []
            sources = []
            
            for i, price in enumerate(prices):
                if isinstance(price, (int, float)) and price > 0:
                    valid_prices.append(price)
                    sources.append(['CoinGecko', 'Binance', 'DexScreener'][i])
            
            # Если ничего не нашли, пробуем fallback
            if not valid_prices:
                self.logger.debug(f"🔄 Пробуем fallback для {symbol}")
                fallback_price = await self._fetch_dexscreener_by_name(symbol)
                if fallback_price:
                    valid_prices.append(fallback_price)
                    sources.append('DexScreener-Fallback')
            
            if not valid_prices:
                self.logger.warning(f"⚠️ Не удалось получить цену для {symbol}")
                return None
            
            # Вычисляем взвешенную среднюю
            if len(valid_prices) == 1:
                final_price = valid_prices[0]
            else:
                # Если есть CoinGecko - даем ему больший вес
                weights = []
                for source in sources:
                    if 'CoinGecko' in source:
                        weights.append(0.5)
                    elif 'Binance' in source:
                        weights.append(0.3)
                    else:
                        weights.append(0.2)
                
                # Нормализуем веса
                total_weight = sum(weights)
                weights = [w / total_weight for w in weights]
                
                final_price = sum(p * w for p, w in zip(valid_prices, weights))
            
            # Кешируем результат
            result = {
                'symbol': symbol,
                'price': final_price,
                'sources': sources,
                'source_count': len(valid_prices),
                'timestamp': datetime.now().timestamp()
            }
            
            self._price_cache[symbol] = result
            
            self.logger.debug(f"💱 DEX цена {symbol}: ${final_price:.6f} "
                            f"(источников: {len(valid_prices)}: {', '.join(sources)})")
            
            return result
            
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
        
        # Ограничиваем количество одновременных запросов
        semaphore = asyncio.Semaphore(5)
        
        async def get_price_with_semaphore(symbol):
            async with semaphore:
                return symbol, await self.get_dex_price(symbol)
        
        # Запускаем задачи с ограничением
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
                    else:
                        self.logger.debug(f"⚠️ Не удалось получить цену для {symbol}")
                elif isinstance(result, Exception):
                    self.logger.error(f"❌ Ошибка при получении цены: {result}")
            
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
    
    async def check_token_availability(self, symbols: List[str]) -> Dict[str, bool]:
        """Проверка доступности токенов в различных источниках"""
        self.logger.info(f"🔍 Проверка доступности {len(symbols)} токенов...")
        
        availability = {}
        
        for symbol in symbols:
            self.logger.info(f"🔄 Проверяем {symbol}...")
            
            # Пробуем получить цену
            price_data = await self.get_dex_price(symbol)
            
            if price_data and price_data.get('price', 0) > 0:
                availability[symbol] = True
                sources = price_data.get('sources', [])
                self.logger.info(f"✅ {symbol}: доступен (источники: {', '.join(sources)})")
            else:
                availability[symbol] = False
                self.logger.warning(f"❌ {symbol}: недоступен")
            
            # Пауза между проверками
            await asyncio.sleep(1)
        
        available_count = sum(availability.values())
        self.logger.info(f"📊 Итого доступно: {available_count}/{len(symbols)} токенов")
        
        return availability