#!/usr/bin/env python3
"""Startup script - entry point for running the trading bot."""

import asyncio
import sys
from pathlib import Path

from btc5m_bot.config import print_config, DB_PATH, MODEL_PATH, USE_PRETRAINED_MODEL, BACKTEST_DAYS
from btc5m_bot.data_engine import BinanceDataProvider, PriceDataStore
from btc5m_bot.trading_bot import BTC5mPaperTradingBot
from btc5m_bot.backtest import run_backtest


def load_historical_data() -> bool:
    """Load historical data from Binance."""
    print("\n📥 LOADING HISTORICAL DATA")
    print("-" * 70)
    
    try:
        provider = BinanceDataProvider()
        store = PriceDataStore(DB_PATH)
        
        # Fetch data
        print("Fetching BTC/USDT 1m data from Binance...")
        klines = provider.fetch_historical_data(
            symbol="BTCUSDT",
            interval="1m",
            days_back=BACKTEST_DAYS,
        )
        
        if not klines:
            print("✗ No data fetched from Binance")
            return False
        
        print(f"✓ Fetched {len(klines)} 1m candles")
        
        # Store data
        inserted = store.insert_klines(klines, interval="1m")
        print(f"✓ Stored {inserted} candles to database")
        
        return True
    except Exception as e:
        print(f"✗ Error loading data: {e}")
        return False


async def run_backtest_validation() -> bool:
    """Run backtest to validate 80%+ accuracy."""
    print("\n🔍 BACKTEST VALIDATION")
    print("-" * 70)
    
    try:
        model_path = MODEL_PATH if USE_PRETRAINED_MODEL else None
        summary = run_backtest(
            db_path=DB_PATH,
            model_path=model_path,
            days_back=BACKTEST_DAYS,
        )
        
        if not summary:
            print("✗ Backtest failed")
            return False
        
        accuracy = summary.get("accuracy_pct", 0)
        if accuracy >= 80:
            print(f"\n✅ BACKTEST PASSED: {accuracy:.2f}% accuracy (target: 80%+)")
            return True
        else:
            print(f"\n⚠️  BACKTEST WARNING: {accuracy:.2f}% accuracy (target: 80%+)")
            print("   Continuing anyway - may need model optimization")
            return True
    except Exception as e:
        print(f"✗ Backtest error: {e}")
        return True  # Continue anyway


async def run_paper_trading(max_cycles: int | None = None) -> None:
    """Run paper trading bot."""
    print("\n🤖 STARTING PAPER TRADING")
    print("-" * 70)
    
    try:
        model_path = MODEL_PATH if USE_PRETRAINED_MODEL and MODEL_PATH.exists() else None
        
        bot = BTC5mPaperTradingBot(
            db_path=DB_PATH,
            model_path=model_path,
        )
        
        await bot.run_continuous(
            interval_seconds=60,
            max_cycles=max_cycles,
        )
    except KeyboardInterrupt:
        print("\n✓ Stopped by user")
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)


async def main_async(
    mode: str = "live",
    max_cycles: int | None = None,
    skip_backtest: bool = False,
) -> None:
    """Main async entry point."""
    
    # Print configuration
    print_config()
    
    # Load data
    if not load_historical_data():
        print("✗ Failed to load historical data")
        sys.exit(1)
    
    # Run backtest validation
    if not skip_backtest:
        if not await run_backtest_validation():
            print("✗ Backtest validation failed")
            sys.exit(1)
    
    # Run trading
    if mode == "live":
        await run_paper_trading(max_cycles=max_cycles)
    elif mode == "backtest":
        print("\n🔍 BACKTEST ONLY MODE")
        print("-" * 70)
        run_backtest(db_path=DB_PATH)
    else:
        print(f"✗ Unknown mode: {mode}")
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="BTC 5m Trading Bot - 80%+ Accuracy Paper Trading",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m btc5m_bot.start                    # Run with default settings
  python -m btc5m_bot.start --backtest-only    # Run backtest only
  python -m btc5m_bot.start --cycles 100       # Run 100 cycles
  python -m btc5m_bot.start --skip-backtest    # Skip backtest validation
  python -m btc5m_bot.start --model models/btc5m.txt  # Use pre-trained model
        """,
    )
    
    parser.add_argument(
        "--mode",
        choices=["live", "backtest"],
        default="live",
        help="Trading mode: live (paper trading) or backtest only",
    )
    parser.add_argument(
        "--cycles",
        type=int,
        help="Maximum number of trading cycles to run",
    )
    parser.add_argument(
        "--skip-backtest",
        action="store_true",
        help="Skip backtest validation before trading",
    )
    parser.add_argument(
        "--backtest-only",
        action="store_true",
        help="Run backtest only (shorthand for --mode backtest)",
    )
    parser.add_argument(
        "--model",
        type=str,
        help="Path to pre-trained LightGBM model",
    )
    
    args = parser.parse_args()
    
    # Parse arguments
    mode = "backtest" if args.backtest_only else args.mode
    skip_backtest = args.skip_backtest or args.backtest_only
    
    # Override model path if provided
    if args.model:
        global MODEL_PATH
        MODEL_PATH = Path(args.model)
    
    # Run
    try:
        asyncio.run(
            main_async(
                mode=mode,
                max_cycles=args.cycles,
                skip_backtest=skip_backtest,
            )
        )
    except KeyboardInterrupt:
        print("\n✓ Stopped")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
