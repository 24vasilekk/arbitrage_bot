"""
Клиент для получения цен с DEX бирж и агрегаторов
Автор: 24vasilekk
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
        
        # Маппинг символов для разных API
        self.coingecko_mapping = {
            'BTC/USDT': 'bitcoin',
            'ETH/USDT': 'ethereum',
            'BNB/USDT': 'binancecoin',
            'ADA/USDT': 'cardano',
            'SOL/USDT': 'solana',
            'XRP/USDT': 'ripple',
            'DOT/USDT': 'polkadot',
            'DOGE/USDT': 'dogecoin',
            'AVAX/USDT': 'avalanche-2',
            'LINK/USDT': 'chainlink',
            'MATIC/USDT': 'matic-network',
            'UNI/USDT': 'uniswap',
            'AAVE/USDT': 'aave',
            'COMP/USDT': 'compound-governance-token',
            'MKR/USDT': 'maker',
            'SNX/USDT': 'havven',
            'SUSHI/USDT': 'sushi',
            'YFI/USDT': 'yearn-finance',
            '1INCH/USDT': '1inch',
            'CRV/USDT': 'curve-dao-token',
            'LTC/USDT': 'litecoin',
            'BCH/USDT': 'bitcoin-cash',
            'FIL/USDT': 'filecoin',
            'TRX/USDT': 'tron',
            'ETC/USDT': 'ethereum-classic',
            'XLM/USDT': 'stellar',
            'VET/USDT': 'vechain',
            'ICP/USDT': 'internet-computer',
            'ATOM/USDT': 'cosmos',
            'NEAR/USDT': 'near',
            'SHIB/USDT': 'shiba-inu',
            'APE/USDT': 'apecoin',
            'SAND/USDT': 'the-sandbox',
            'MANA/USDT': 'decentraland',
            'AXS/USDT': 'axie-infinity',
            'GALA/USDT': 'gala',
            'ENJ/USDT': 'enjincoin',
            'CHZ/USDT': 'chiliz',
            'BAT/USDT': 'basic-attention-token',
            'ZRX/USDT': '0x'
        }
    
    async def __aenter__(self):
        """Async context manager вход"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10),
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
            self.logger.warning(f"⚠️ Символ {symbol} не найден в CoinGecko mapping")
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
                        self.logger.debug(f"🔍 CoinGecko {symbol}: ${price:.4f}")
                        return float(price)
                else:
                    self.logger.warning(f"⚠️ CoinGecko API error {response.status}")
                    
        except Exception as e:
            self.logger.error(f"❌ Ошибка CoinGecko для {symbol}: {e}")
        
        return None
    
    async def _fetch_binance_spot_price(self, symbol: str) -> Optional[float]:
        """Получение цены с Binance Spot для сравнения (не DEX, но полезно)"""
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
                        self.logger.debug(f"🔍 Binance Spot {symbol}: ${price:.4f}")
                        return price
                else:
                    self.logger.warning(f"⚠️ Binance API error {response.status}")
                    
        except Exception as e:
            self.logger.error(f"❌ Ошибка Binance для {symbol}: {e}")
        
        return None
    
    async def _fetch_dexscreener_price(self, symbol: str) -> Optional[float]:
        """Получение средней цены с DexScreener (реальные DEX данные)"""
        if not self.session:
            return None
            
        try:
            # Получаем базовую монету из символа
            base_token = symbol.split('/')[0].upper()
            
            url = f"https://api.dexscreener.com/latest/dex/search"
            params = {'q': base_token}
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    pairs = data.get('pairs', [])
                    
                    if pairs:
                        # Берем пары с USDT и высокой ликвидностью
                        usdt_pairs = [p for p in pairs if 
                                    'USDT' in p.get('quoteToken', {}).get('symbol', '') and
                                    p.get('liquidity', {}).get('usd', 0) > 100000]
                        
                        if usdt_pairs:
                            # Средняя цена по топ-5 парам
                            top_pairs = sorted(usdt_pairs, 
                                             key=lambda x: x.get('liquidity', {}).get('usd', 0),
                                             reverse=True)[:5]
                            
                            prices = []
                            for pair in top_pairs:
                                price = pair.get('priceUsd')
                                if price:
                                    prices.append(float(price))
                            
                            if prices:
                                avg_price = sum(prices) / len(prices)
                                self.logger.debug(f"🔍 DexScreener {symbol}: ${avg_price:.4f} "
                                               f"(из {len(prices)} пар)")
                                return avg_price
                else:
                    self.logger.warning(f"⚠️ DexScreener API error {response.status}")
                    
        except Exception as e:
            self.logger.error(f"❌ Ошибка DexScreener для {symbol}: {e}")
        
        return None
    
    async def get_dex_price(self, symbol: str) -> Optional[Dict]:
        """Получение агрегированной цены DEX с нескольких источников"""
        # Проверяем кеш
        if self._is_cache_valid(symbol):
            cached_data = self._price_cache[symbol]
            self.logger.debug(f"💾 Кеш {symbol}: ${cached_data['price']:.4f}")
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
            prices = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Фильтруем успешные результаты
            valid_prices = []
            sources = []
            
            for i, price in enumerate(prices):
                if isinstance(price, (int, float)) and price > 0:
                    valid_prices.append(price)
                    sources.append(['CoinGecko', 'Binance', 'DexScreener'][i])
            
            if not valid_prices:
                self.logger.warning(f"⚠️ Не удалось получить цену для {symbol}")
                return None
            
            # Вычисляем взвешенную среднюю (CoinGecko имеет больший вес)
            weights = [0.5, 0.2, 0.3]  # CoinGecko, Binance, DexScreener
            weighted_price = 0
            total_weight = 0
            
            for i, price in enumerate(valid_prices):
                weight = weights[i] if i < len(weights) else 0.1
                weighted_price += price * weight
                total_weight += weight
            
            final_price = weighted_price / total_weight
            
            # Кешируем результат
            result = {
                'symbol': symbol,
                'price': final_price,
                'sources': sources,
                'source_count': len(valid_prices),
                'timestamp': datetime.now().timestamp()
            }
            
            self._price_cache[symbol] = result
            
            self.logger.debug(f"💱 DEX цена {symbol}: ${final_price:.4f} "
                            f"(источников: {len(valid_prices)})")
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка получения DEX цены для {symbol}: {e}")
            return None
    
    async def get_multiple_dex_prices(self, symbols: List[str]) -> Dict[str, Dict]:
        """Получение цен для нескольких символов параллельно"""
        if not self.session:
            await self.__aenter__()
        
        # Запускаем задачи параллельно для всех символов
        tasks = {symbol: self.get_dex_price(symbol) for symbol in symbols}
        
        try:
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)
            
            # Собираем результаты
            prices = {}
            for i, symbol in enumerate(tasks.keys()):
                result = results[i]
                if isinstance(result, dict) and not isinstance(result, Exception):
                    prices[symbol] = result
                else:
                    self.logger.warning(f"⚠️ Не удалось получить цену для {symbol}")
            
            self.logger.info(f"📊 Получено DEX цен: {len(prices)}/{len(symbols)}")
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