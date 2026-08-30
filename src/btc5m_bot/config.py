"""Configuration and startup scripts for BTC 5m trading bot."""

import os
from pathlib import Path


# ==================== PATHS ====================
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models"
LOGS_DIR = PROJECT_ROOT / "logs"

# Create directories
DATA_DIR.mkdir(exist_ok=True)
MODELS_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# ==================== DATABASE ====================
DB_PATH = DATA_DIR / "paperbot.sqlite3"
DB_BACKUP_PATH = DATA_DIR / "paperbot_backup.sqlite3"

# ==================== MODEL ====================
MODEL_PATH = MODELS_DIR / "btc5m_model.txt"  # LightGBM model path
USE_PRETRAINED_MODEL = False  # Set to True if model exists

# ==================== TRADING PARAMETERS ====================

# Prediction thresholds
MIN_CONFIDENCE = 0.55  # Minimum confidence to place order (0-1)
MIN_EDGE = 0.05  # Minimum edge between prediction and market price (5%)

# Order sizing
MAX_ORDER_SIZE_USD = 10.0  # Maximum per order
STARTING_CAPITAL_USD = 1000.0  # Paper trading starting capital
USE_KELLY_SIZING = True  # Dynamic position sizing using Kelly Criterion
KELLY_FRACTION = 0.25  # Fractional Kelly (25% of pure Kelly)

# Rate limiting
RATE_LIMIT_PER_MINUTE = 200  # Max orders per minute (Polymarket CLOB limit)
MIN_TIME_BETWEEN_ORDERS_MS = 300  # Minimum 300ms between orders

# ==================== RISK MANAGEMENT ====================
MAX_DAILY_NOTIONAL_USD = 25000.0  # Max total notional exposure per day
MAX_DAILY_LOSS_USD = 500.0  # Stop trading if loss exceeds this
MAX_OPEN_POSITIONS = 50  # Max concurrent open orders
STOP_LOSS_PCT = 0.05  # Stop loss at 5%

# ==================== DATA ====================
BINANCE_BASE_URL = "https://api.binance.com/api/v3"
DATA_FETCH_INTERVAL_MINUTES = 1  # Fetch new data every 1 minute
HISTORICAL_DATA_DAYS = 30  # Load 30 days of historical data for features
FEATURE_LOOKBACK_MINUTES = 300  # Look back 300 minutes (5 hours) for features
MIN_SAMPLES_FOR_PREDICTION = 30  # Minimum 1m candles needed

# ==================== TRADING SCHEDULE ====================
TRADING_CYCLE_INTERVAL_SECONDS = 60  # Run trading cycle every 60 seconds
EXPECTED_TRADES_PER_DAY = (24 * 60 * 60) / TRADING_CYCLE_INTERVAL_SECONDS  # ~1440 trades/day
EXPECTED_TRADES_PER_MINUTE = 1.0 / (TRADING_CYCLE_INTERVAL_SECONDS / 60)

# ==================== BACKTEST PARAMETERS ====================
BACKTEST_DAYS = 7  # Backtest on last 7 days of data
BACKTEST_INTERVAL_MINUTES = 5  # Test prediction every 5 minutes
BACKTEST_OUTPUT_PATH = DATA_DIR / "backtest_results.json"

# ==================== POLYMARKET API ====================
POLYMARKET_API_BASE = "https://clob.polymarket.com"
POLYMARKET_MARKETS = {
    "btc_5m_up": "market_id_here",  # Replace with actual market ID
}

# ==================== LOGGING ====================
LOG_FILE = LOGS_DIR / "trading_bot.log"
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT = "[%(asctime)s] %(levelname)s - %(message)s"

# ==================== FEATURE CONFIGURATION ====================
ENABLED_FEATURES = {
    "momentum": True,        # ROC, MACD
    "volatility": True,      # Historical vol, ATR
    "mean_reversion": True,  # RSI, Bollinger Bands
    "volume": True,          # Volume momentum, taker buy ratio
    "microstructure": True,  # Close position, wicks
    "multi_timeframe": True, # 1m vs 5m alignment
}

# ==================== SIGNAL WEIGHTS (must sum to 1.0) ====================
SIGNAL_WEIGHTS = {
    "macd_momentum": 0.15,
    "rsi_mean_reversion": 0.12,
    "bollinger_mean_reversion": 0.10,
    "volume_divergence": 0.08,
    "price_action": 0.12,
    "volatility_regime": 0.08,
    "multi_timeframe": 0.10,
    "trend_strength": 0.10,
    "close_position": 0.07,
    "order_flow": 0.08,
}

# Normalize weights to sum to 1.0
_total_weight = sum(SIGNAL_WEIGHTS.values())
SIGNAL_WEIGHTS = {k: v / _total_weight for k, v in SIGNAL_WEIGHTS.items()}

# ==================== ACCURACY TARGET ====================
ACCURACY_TARGET_PCT = 80.0  # Target 80%+ direction accuracy
WIN_RATE_TARGET_PCT = 55.0  # Target 55%+ win rate on profitable trades


def print_config() -> None:
    """Print current configuration."""
    print("\n" + "="*70)
    print("⚙️  CONFIGURATION")
    print("="*70)
    
    print("\n📁 PATHS")
    print(f"  Project Root: {PROJECT_ROOT}")
    print(f"  Data Directory: {DATA_DIR}")
    print(f"  Models Directory: {MODELS_DIR}")
    print(f"  Database: {DB_PATH}")
    
    print("\n🎯 TRADING PARAMETERS")
    print(f"  Min Confidence: {MIN_CONFIDENCE*100:.0f}%")
    print(f"  Min Edge: {MIN_EDGE*100:.0f}%")
    print(f"  Max Order Size: ${MAX_ORDER_SIZE_USD:.2f}")
    print(f"  Kelly Sizing: {'✓ Enabled' if USE_KELLY_SIZING else '✗ Disabled'}")
    print(f"  Starting Capital: ${STARTING_CAPITAL_USD:.2f}")
    
    print("\n⏱️  TRADING SCHEDULE")
    print(f"  Cycle Interval: {TRADING_CYCLE_INTERVAL_SECONDS}s")
    print(f"  Expected Trades/Day: {EXPECTED_TRADES_PER_DAY:.0f}")
    print(f"  Expected Trades/Min: {EXPECTED_TRADES_PER_MINUTE:.2f}")
    
    print("\n💰 RISK MANAGEMENT")
    print(f"  Max Daily Notional: ${MAX_DAILY_NOTIONAL_USD:.0f}")
    print(f"  Max Daily Loss: ${MAX_DAILY_LOSS_USD:.0f}")
    print(f"  Max Open Positions: {MAX_OPEN_POSITIONS}")
    print(f"  Stop Loss: {STOP_LOSS_PCT*100:.1f}%")
    
    print("\n📊 ACCURACY TARGETS")
    print(f"  Direction Accuracy: {ACCURACY_TARGET_PCT:.0f}%+")
    print(f"  Win Rate: {WIN_RATE_TARGET_PCT:.0f}%+")
    
    print("="*70 + "\n")


if __name__ == "__main__":
    print_config()
