"""
Конфигурационный модуль для арбитражного бота
Автор: 24vasilekk
ОБНОВЛЕН: Агрессивные настройки, убраны лимиты
"""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Any
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

class Config:
    """Класс для управления конфигурацией бота"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.config_file = self.project_root / "config" / "settings.yaml"
        self._config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Загрузка конфигурации из YAML файла"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            print(f"⚠️ Файл конфигурации не найден: {self.config_file}")
            return self._default_config()
        except Exception as e:
            print(f"❌ Ошибка загрузки конфигурации: {e}")
            return self._default_config()
    
    def _default_config(self) -> Dict[str, Any]:
        """Конфигурация по умолчанию - АГРЕССИВНЫЕ НАСТРОЙКИ"""
        return {
            'trading': {
                'min_spread_percent': 7.5,
                'target_spread_percent': 1.5,
                'max_position_size': 5.10,      # Фиксированный размер
                'test_mode': True,
                'leverage': 2,                  # Плечо 2x
                'symbols': ['BTC/USDT', 'ETH/USDT', 'PEPE/USDT']
            },
            'risk_management': {
                'max_daily_loss': 999999,       # УБРАН лимит
                'stop_loss_percent': 50.0,      # АГРЕССИВНЫЙ стоп-лосс 50%
                'take_profit_percent': 20.0,    # Увеличен тейк-профит
                'max_positions': 10,            # Больше позиций
                'fixed_position_size': 5.10,    # Фиксированный размер
                'position_leverage': 2          # Плечо 2x
            },
            'monitoring': {
                'price_update_interval': 1,     # КАЖДУЮ СЕКУНДУ
                'max_price_age': 2
            }
        }
    
    # API ключи
    @property
    def mexc_api_key(self) -> str:
        return os.getenv('MEXC_API_KEY', '')
    
    @property
    def mexc_secret(self) -> str:
        return os.getenv('MEXC_SECRET', '')
    
    # Торговые настройки
    @property
    def test_mode(self) -> bool:
        env_test = os.getenv('TEST_MODE', 'true').lower()
        return env_test in ['true', '1', 'yes'] or self._config['trading'].get('test_mode', True)
    
    @property
    def min_spread_percent(self) -> float:
        return float(os.getenv('MIN_SPREAD_PERCENT', 
                             self._config['trading']['min_spread_percent']))
    
    @property
    def target_spread_percent(self) -> float:
        return float(os.getenv('TARGET_SPREAD_PERCENT', 
                             self._config['trading']['target_spread_percent']))
    
    @property
    def max_position_size(self) -> float:
        """ФИКСИРОВАННЫЙ размер позиции $5.10"""
        return float(os.getenv('FIXED_POSITION_SIZE', 
                             self._config['trading'].get('max_position_size', 5.10)))
    
    @property 
    def fixed_position_size(self) -> float:
        """Фиксированный размер позиции"""
        return float(self._config['risk_management'].get('fixed_position_size', 5.10))
    
    @property
    def leverage(self) -> int:
        """Кредитное плечо"""
        return int(self._config['trading'].get('leverage', 2))
    
    @property
    def symbols(self) -> List[str]:
        """Список торговых пар для мониторинга"""
        return self._config['trading']['symbols']
    
    @property
    def price_update_interval(self) -> int:
        """Интервал обновления цен - КАЖДУЮ СЕКУНДУ"""
        return self._config['monitoring']['price_update_interval']
    
    @property
    def max_daily_loss(self) -> float:
        """УБРАН лимит потерь"""
        return float('inf')  # Без лимитов
    
    @property
    def stop_loss_percent(self) -> float:
        """АГРЕССИВНЫЙ стоп-лосс 50%"""
        return self._config['risk_management']['stop_loss_percent']
    
    @property
    def take_profit_percent(self) -> float:
        """Увеличенный тейк-профит"""
        return self._config['risk_management']['take_profit_percent']
    
    @property
    def max_positions(self) -> int:
        """Максимальное количество позиций - увеличено"""
        return self._config['risk_management']['max_positions']
    
    def validate(self) -> bool:
        """Валидация конфигурации"""
        if not self.mexc_api_key or not self.mexc_secret:
            print("❌ MEXC API ключи не настроены")
            return False
            
        if self.min_spread_percent <= 0:
            print("❌ Минимальный спред должен быть больше 0")
            return False
            
        if not self.symbols:
            print("❌ Не настроены торговые пары")
            return False
            
        return True

# Глобальный экземпляр конфигурации
config = Config()