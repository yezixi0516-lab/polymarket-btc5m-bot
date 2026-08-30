"""Advanced feature extraction for BTC price prediction."""

from __future__ import annotations

import math
from statistics import NormalDist
from typing import Any


class FeatureExtractor:
    """Extract 20+ advanced features from price data for high accuracy prediction."""
    
    def __init__(self, min_samples: int = 30) -> None:
        self.min_samples = min_samples
    
    def extract_all_features(
        self,
        klines_1m: list[dict[str, Any]],
        klines_5m: list[dict[str, Any]],
        current_price: float,
    ) -> dict[str, float]:
        """
        Extract all features from 1m and 5m price data.
        
        Args:
            klines_1m: List of 1-minute candles (most recent last)
            klines_5m: List of 5-minute candles (most recent last)
            current_price: Current BTC price
        
        Returns:
            Dictionary of all features
        """
        features = {}
        
        # Ensure minimum data
        if len(klines_1m) < self.min_samples:
            return self._empty_features()
        
        # Extract price series
        prices_1m = [k["close"] for k in klines_1m]
        prices_5m = [k["close"] for k in klines_5m] if klines_5m else []
        
        # 1-minute features (primary signal source)
        features.update(self._momentum_features(prices_1m))
        features.update(self._volatility_features(prices_1m))
        features.update(self._mean_reversion_features(prices_1m))
        features.update(self._volume_features(klines_1m))
        features.update(self._microstructure_features(klines_1m))
        
        # 5-minute features (confirm signal)
        if prices_5m:
            features.update(self._trend_features(prices_5m, prefix="5m_"))
        
        # Cross-timeframe features
        features.update(self._cross_timeframe_features(prices_1m, prices_5m))
        
        return features
    
    # ==================== MOMENTUM FEATURES ====================
    
    def _momentum_features(self, prices: list[float]) -> dict[str, float]:
        """Momentum and trend-following indicators."""
        features = {}
        
        if len(prices) < 3:
            return {"momentum_score": 0.5, "roc_5": 0.0, "roc_10": 0.0}
        
        # Rate of Change
        features["roc_5"] = (prices[-1] - prices[-5]) / prices[-5] if len(prices) >= 5 else 0.0
        features["roc_10"] = (prices[-1] - prices[-10]) / prices[-10] if len(prices) >= 10 else 0.0
        features["roc_20"] = (prices[-1] - prices[-20]) / prices[-20] if len(prices) >= 20 else 0.0
        
        # MACD (12, 26, 9)
        if len(prices) >= 26:
            ema_12 = self._ema(prices, 12)
            ema_26 = self._ema(prices, 26)
            macd_line = ema_12[-1] - ema_26[-1]
            signal_line = self._ema([ema_12[i] - ema_26[i] for i in range(len(prices))], 9)[-1]
            features["macd"] = macd_line
            features["macd_signal"] = signal_line
            features["macd_histogram"] = macd_line - signal_line
        else:
            features["macd"] = 0.0
            features["macd_signal"] = 0.0
            features["macd_histogram"] = 0.0
        
        # Simple momentum (last close - SMA)
        if len(prices) >= 10:
            sma_10 = sum(prices[-10:]) / 10
            features["price_sma_10_diff"] = (prices[-1] - sma_10) / sma_10
        else:
            features["price_sma_10_diff"] = 0.0
        
        if len(prices) >= 20:
            sma_20 = sum(prices[-20:]) / 20
            features["price_sma_20_diff"] = (prices[-1] - sma_20) / sma_20
        else:
            features["price_sma_20_diff"] = 0.0
        
        return features
    
    # ==================== VOLATILITY FEATURES ====================
    
    def _volatility_features(self, prices: list[float]) -> dict[str, float]:
        """Volatility and regime detection."""
        features = {}
        
        if len(prices) < 3:
            return {"volatility_10": 0.01, "atr": 0.0, "volatility_regime": 0.5}
        
        # Historical volatility
        returns = [math.log(prices[i] / prices[i-1]) for i in range(1, len(prices)) if prices[i-1] > 0]
        
        if len(returns) >= 10:
            vol_10 = self._sample_std(returns[-10:])
            features["volatility_10"] = vol_10
        else:
            features["volatility_10"] = 0.01
        
        if len(returns) >= 20:
            vol_20 = self._sample_std(returns[-20:])
            features["volatility_20"] = vol_20
        else:
            features["volatility_20"] = features.get("volatility_10", 0.01)
        
        # Volatility expansion/contraction (vol ratio)
        if features["volatility_20"] > 0:
            features["volatility_expansion"] = features["volatility_10"] / features["volatility_20"]
        else:
            features["volatility_expansion"] = 1.0
        
        # ATR (Average True Range)
        if len(prices) >= 14:
            tr_values = [abs(prices[i] - prices[i-1]) for i in range(1, len(prices))]
            features["atr"] = sum(tr_values[-14:]) / 14
        else:
            features["atr"] = 0.0
        
        return features
    
    # ==================== MEAN REVERSION FEATURES ====================
    
    def _mean_reversion_features(self, prices: list[float]) -> dict[str, float]:
        """Mean reversion and overbought/oversold indicators."""
        features = {}
        
        if len(prices) < 15:
            return {"rsi_14": 50.0, "bb_position": 0.5}
        
        # RSI (Relative Strength Index)
        rsi_14 = self._rsi(prices[-15:], 14)
        features["rsi_14"] = rsi_14
        features["rsi_overbought"] = 1.0 if rsi_14 > 70 else 0.0
        features["rsi_oversold"] = 1.0 if rsi_14 < 30 else 0.0
        
        # Bollinger Bands (20, 2)
        if len(prices) >= 20:
            bb_mean = sum(prices[-20:]) / 20
            bb_std = self._sample_std(prices[-20:])
            bb_upper = bb_mean + 2 * bb_std
            bb_lower = bb_mean - 2 * bb_std
            bb_range = bb_upper - bb_lower
            
            if bb_range > 0:
                bb_position = (prices[-1] - bb_lower) / bb_range
                features["bb_position"] = max(0, min(1, bb_position))  # 0 = at lower band, 1 = at upper band
            else:
                features["bb_position"] = 0.5
            
            features["bb_width"] = bb_range / bb_mean if bb_mean > 0 else 0.0
        else:
            features["bb_position"] = 0.5
            features["bb_width"] = 0.0
        
        return features
    
    # ==================== VOLUME FEATURES ====================
    
    def _volume_features(self, klines: list[dict[str, Any]]) -> dict[str, float]:
        """Volume-based features."""
        features = {}
        
        if len(klines) < 5:
            return {"volume_momentum": 0.0, "taker_buy_ratio": 0.5}
        
        volumes = [k["volume"] for k in klines]
        
        # Volume momentum
        if len(volumes) >= 5:
            vol_avg_5 = sum(volumes[-5:]) / 5
            vol_current = volumes[-1]
            if vol_avg_5 > 0:
                features["volume_momentum"] = (vol_current - vol_avg_5) / vol_avg_5
            else:
                features["volume_momentum"] = 0.0
        else:
            features["volume_momentum"] = 0.0
        
        # Taker buy ratio (if available)
        taker_buy_volumes = []
        taker_sell_volumes = []
        
        for k in klines[-10:]:
            taker_buy = k.get("taker_buy_base_asset_volume", 0)
            taker_sell = k.get("volume", 1) - taker_buy
            
            taker_buy_volumes.append(taker_buy)
            taker_sell_volumes.append(taker_sell)
        
        total_buy = sum(taker_buy_volumes)
        total_sell = sum(taker_sell_volumes)
        total = total_buy + total_sell
        
        if total > 0:
            features["taker_buy_ratio"] = total_buy / total
        else:
            features["taker_buy_ratio"] = 0.5
        
        return features
    
    # ==================== MICROSTRUCTURE FEATURES ====================
    
    def _microstructure_features(self, klines: list[dict[str, Any]]) -> dict[str, float]:
        """Order book and price action microstructure."""
        features = {}
        
        if len(klines) < 2:
            return {"wick_ratio": 0.5, "close_position": 0.5}
        
        # Close position (where close is within the candle range)
        latest = klines[-1]
        high = latest["high"]
        low = latest["low"]
        close = latest["close"]
        
        candle_range = high - low
        if candle_range > 0:
            close_pos = (close - low) / candle_range
            features["close_position"] = max(0, min(1, close_pos))  # 0 = closed at low, 1 = closed at high
        else:
            features["close_position"] = 0.5
        
        # Wick ratio (upper wick size)
        if candle_range > 0:
            upper_wick = high - close
            features["wick_ratio"] = upper_wick / candle_range
        else:
            features["wick_ratio"] = 0.5
        
        # Consecutive up/down candles
        closes = [k["close"] for k in klines[-5:]]
        up_count = sum(1 for i in range(1, len(closes)) if closes[i] > closes[i-1])
        features["consecutive_up"] = up_count / len(closes) if closes else 0.5
        
        return features
    
    # ==================== TREND FEATURES ====================
    
    def _trend_features(self, prices: list[float], prefix: str = "") -> dict[str, float]:
        """Longer-term trend features."""
        features = {}
        
        if len(prices) < 2:
            return {}
        
        # Trend direction (SMA-based)
        if len(prices) >= 5:
            sma_short = sum(prices[-3:]) / 3
            sma_long = sum(prices[-5:]) / 5
            features[f"{prefix}trend_direction"] = 1.0 if sma_short > sma_long else -1.0
        else:
            features[f"{prefix}trend_direction"] = 0.0
        
        return features
    
    # ==================== CROSS-TIMEFRAME FEATURES ====================
    
    def _cross_timeframe_features(
        self,
        prices_1m: list[float],
        prices_5m: list[float],
    ) -> dict[str, float]:
        """Features that combine multiple timeframes."""
        features = {}
        
        if not prices_5m or len(prices_1m) < 5:
            return {"timeframe_alignment": 0.5}
        
        # 1m trend vs 5m trend
        trend_1m = 1.0 if prices_1m[-1] > prices_1m[-2] else -1.0
        trend_5m = 1.0 if prices_5m[-1] > prices_5m[-2] else -1.0
        
        features["timeframe_alignment"] = 1.0 if trend_1m == trend_5m else -1.0
        
        return features
    
    # ==================== HELPER METHODS ====================
    
    def _ema(self, values: list[float], period: int) -> list[float]:
        """Calculate Exponential Moving Average."""
        if not values or period < 1:
            return values
        
        alpha = 2 / (period + 1)
        ema = [values[0]]
        
        for value in values[1:]:
            ema.append(alpha * value + (1 - alpha) * ema[-1])
        
        return ema
    
    def _rsi(self, values: list[float], period: int = 14) -> float:
        """Calculate Relative Strength Index."""
        if len(values) < 2:
            return 50.0
        
        changes = [values[i] - values[i-1] for i in range(1, len(values))]
        gains = sum(c for c in changes if c > 0)
        losses = sum(-c for c in changes if c < 0)
        
        if gains == 0 and losses == 0:
            return 50.0
        if losses == 0:
            return 100.0
        
        rs = gains / losses
        return 100 - (100 / (1 + rs))
    
    def _sample_std(self, values: list[float]) -> float:
        """Calculate sample standard deviation."""
        if len(values) < 2:
            return 0.0
        
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
        return math.sqrt(max(0, variance))
    
    def _empty_features(self) -> dict[str, float]:
        """Return default features when insufficient data."""
        return {
            # Momentum
            "roc_5": 0.0,
            "roc_10": 0.0,
            "roc_20": 0.0,
            "macd": 0.0,
            "macd_signal": 0.0,
            "macd_histogram": 0.0,
            "price_sma_10_diff": 0.0,
            "price_sma_20_diff": 0.0,
            # Volatility
            "volatility_10": 0.01,
            "volatility_20": 0.01,
            "volatility_expansion": 1.0,
            "atr": 0.0,
            # Mean Reversion
            "rsi_14": 50.0,
            "rsi_overbought": 0.0,
            "rsi_oversold": 0.0,
            "bb_position": 0.5,
            "bb_width": 0.0,
            # Volume
            "volume_momentum": 0.0,
            "taker_buy_ratio": 0.5,
            # Microstructure
            "wick_ratio": 0.5,
            "close_position": 0.5,
            "consecutive_up": 0.5,
            # Cross-timeframe
            "timeframe_alignment": 0.5,
            "5m_trend_direction": 0.0,
        }
