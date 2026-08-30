"""Backtesting framework to validate 80%+ accuracy on historical data."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .data_engine import PriceDataStore, resample_1m_to_5m
from .feature_extractor import FeatureExtractor
from .predictor import HybridPredictorWithRules
from .execution import Order


class BacktestEngine:
    """Backtest trading strategy on historical data."""
    
    def __init__(
        self,
        db_path: Path = Path("data/paperbot.sqlite3"),
        model_path: str | None = None,
    ) -> None:
        self.store = PriceDataStore(db_path)
        self.feature_extractor = FeatureExtractor(min_samples=30)
        self.predictor = HybridPredictorWithRules()
        
        if model_path and Path(model_path).exists():
            self.predictor.load_model(model_path)
        
        self.results = []
        self.stats = {
            "total_predictions": 0,
            "correct_predictions": 0,
            "up_predictions": 0,
            "down_predictions": 0,
            "up_correct": 0,
            "down_correct": 0,
        }
    
    def backtest(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        interval: int = 5,  # Test every N candles
    ) -> dict[str, Any]:
        """
        Run backtest on historical data.
        
        Args:
            start_date: Backtest start date
            end_date: Backtest end date
            interval: Test every N 1-minute candles (5 = every 5 minutes)
        
        Returns:
            Backtest results dictionary
        """
        print(f"\n🔍 Starting backtest (interval={interval}m)...")
        
        # Get all 1m data
        all_klines_1m = self.store.get_klines(interval="1m", limit=100000)
        
        if not all_klines_1m:
            print("✗ No data available for backtest")
            return {}
        
        # Filter by date if provided
        if start_date or end_date:
            filtered = []
            for k in all_klines_1m:
                open_time = datetime.fromtimestamp(k["open_time"] / 1000, UTC)
                
                if start_date and open_time < start_date:
                    continue
                if end_date and open_time > end_date:
                    break
                
                filtered.append(k)
            
            all_klines_1m = filtered
        
        print(f"✓ Loaded {len(all_klines_1m)} 1-minute candles")
        
        # Resample to 5m
        all_klines_5m = resample_1m_to_5m(all_klines_1m)
        print(f"✓ Resampled to {len(all_klines_5m)} 5-minute candles")
        
        # Run predictions
        for i in range(interval, len(all_klines_1m) - interval):
            # Get data up to current point
            klines_1m = all_klines_1m[:i]
            klines_5m = all_klines_5m[:i // 5] if i >= 5 else []
            
            # Skip if not enough data
            if len(klines_1m) < 30:
                continue
            
            # Get actual future move
            current_close = klines_1m[-1]["close"]
            future_close = klines_1m[i + interval]["close"]
            actual_direction = "UP" if future_close > current_close else "DOWN"
            
            # Extract features and predict
            try:
                features = self.feature_extractor.extract_all_features(
                    klines_1m=klines_1m,
                    klines_5m=klines_5m,
                    current_price=current_close,
                )
                
                price_history = [k["close"] for k in klines_1m]
                prediction = self.predictor.predict(features, price_history)
                
                # Check if prediction was correct
                predicted_direction = prediction.get("direction", "UP")
                is_correct = predicted_direction == actual_direction
                
                result = {
                    "index": i,
                    "timestamp": datetime.fromtimestamp(klines_1m[-1]["open_time"] / 1000, UTC).isoformat(),
                    "predicted_direction": predicted_direction,
                    "actual_direction": actual_direction,
                    "is_correct": is_correct,
                    "probability_up": prediction.get("probability_up", 0.5),
                    "confidence": prediction.get("confidence", 0.5),
                    "price": current_close,
                    "future_price": future_close,
                    "pnl": (future_close - current_close) if predicted_direction == actual_direction else -(current_close - future_close),
                }
                
                self.results.append(result)
                
                # Update stats
                self.stats["total_predictions"] += 1
                if is_correct:
                    self.stats["correct_predictions"] += 1
                
                if predicted_direction == "UP":
                    self.stats["up_predictions"] += 1
                    if is_correct:
                        self.stats["up_correct"] += 1
                else:
                    self.stats["down_predictions"] += 1
                    if is_correct:
                        self.stats["down_correct"] += 1
            
            except Exception as e:
                continue
            
            # Progress indicator
            if self.stats["total_predictions"] % 1000 == 0:
                accuracy = (
                    self.stats["correct_predictions"] / self.stats["total_predictions"] * 100
                    if self.stats["total_predictions"] > 0
                    else 0
                )
                print(f"  Progress: {self.stats['total_predictions']} predictions, "
                      f"Accuracy: {accuracy:.2f}%")
        
        return self._calculate_summary()
    
    def _calculate_summary(self) -> dict[str, Any]:
        """Calculate backtest summary statistics."""
        stats = self.stats
        
        total = stats["total_predictions"]
        if total == 0:
            return {}
        
        accuracy = stats["correct_predictions"] / total * 100
        up_accuracy = stats["up_correct"] / stats["up_predictions"] * 100 if stats["up_predictions"] > 0 else 0
        down_accuracy = stats["down_correct"] / stats["down_predictions"] * 100 if stats["down_predictions"] > 0 else 0
        
        # Calculate PnL stats
        pnl_values = [r["pnl"] for r in self.results if r.get("pnl") is not None]
        total_pnl = sum(pnl_values) if pnl_values else 0
        avg_pnl = total_pnl / len(pnl_values) if pnl_values else 0
        
        # Win rate (positive PnL trades)
        wins = sum(1 for p in pnl_values if p > 0)
        win_rate = wins / len(pnl_values) * 100 if pnl_values else 0
        
        # Sharpe ratio
        if len(pnl_values) > 1:
            mean_pnl = sum(pnl_values) / len(pnl_values)
            variance = sum((p - mean_pnl) ** 2 for p in pnl_values) / (len(pnl_values) - 1)
            std_pnl = variance ** 0.5
            sharpe = (mean_pnl / std_pnl * (252 * 288) ** 0.5) if std_pnl > 0 else 0  # Annualized
        else:
            sharpe = 0
        
        summary = {
            "total_predictions": total,
            "correct_predictions": stats["correct_predictions"],
            "accuracy_pct": accuracy,
            "up_predictions": stats["up_predictions"],
            "up_accuracy_pct": up_accuracy,
            "down_predictions": stats["down_predictions"],
            "down_accuracy_pct": down_accuracy,
            "total_pnl": total_pnl,
            "average_pnl": avg_pnl,
            "win_rate_pct": win_rate,
            "sharpe_ratio": sharpe,
            "predictions_per_day": total / (len(self.results) / 288) if self.results else 0,  # 288 = 5m intervals per day
        }
        
        return summary
    
    def print_summary(self, summary: dict[str, Any]) -> None:
        """Print backtest summary."""
        if not summary:
            print("No results to display")
            return
        
        print("\n" + "="*70)
        print("📊 BACKTEST SUMMARY")
        print("="*70)
        print(f"Total Predictions: {summary['total_predictions']:,}")
        print(f"Correct Predictions: {summary['correct_predictions']:,}")
        print()
        print(f"📈 OVERALL ACCURACY: {summary['accuracy_pct']:.2f}%")
        print(f"   Target: 80%+ ({'✓ PASS' if summary['accuracy_pct'] >= 80 else '✗ FAIL'})")
        print()
        print(f"Direction Breakdown:")
        print(f"  UP Predictions: {summary['up_predictions']:,} ({summary['up_predictions']/summary['total_predictions']*100:.1f}%)")
        print(f"  UP Accuracy: {summary['up_accuracy_pct']:.2f}%")
        print(f"  DOWN Predictions: {summary['down_predictions']:,} ({summary['down_predictions']/summary['total_predictions']*100:.1f}%)")
        print(f"  DOWN Accuracy: {summary['down_accuracy_pct']:.2f}%")
        print()
        print(f"💰 PROFITABILITY:")
        print(f"  Total PnL: ${summary['total_pnl']:.2f}")
        print(f"  Average PnL/Trade: ${summary['average_pnl']:.4f}")
        print(f"  Win Rate: {summary['win_rate_pct']:.2f}%")
        print(f"  Sharpe Ratio: {summary['sharpe_ratio']:.2f}")
        print()
        print(f"📊 VOLUME:")
        print(f"  Predictions/Day: {summary['predictions_per_day']:.0f}")
        print(f"  Expected Volume/Day: {summary['predictions_per_day']:,.0f} trades")
        print("="*70 + "\n")
    
    def save_results(self, output_path: Path) -> None:
        """Save detailed backtest results to JSON."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w") as f:
            json.dump(
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "summary": self._calculate_summary(),
                    "results": self.results,
                },
                f,
                indent=2,
            )
        
        print(f"✓ Results saved to {output_path}")


def run_backtest(
    db_path: Path = Path("data/paperbot.sqlite3"),
    model_path: str | None = None,
    output_path: Path = Path("backtest_results.json"),
    days_back: int = 7,
) -> dict[str, Any]:
    """
    Run full backtest and print results.
    
    Args:
        db_path: Path to price database
        model_path: Path to pre-trained model
        output_path: Path to save results
        days_back: Days to backtest
    
    Returns:
        Summary dictionary
    """
    engine = BacktestEngine(db_path=db_path, model_path=model_path)
    
    # Calculate date range
    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=days_back)
    
    # Run backtest
    summary = engine.backtest(start_date=start_date, end_date=end_date, interval=5)
    
    # Print results
    engine.print_summary(summary)
    
    # Save results
    engine.save_results(output_path)
    
    return summary


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Backtest BTC 5m Trading Strategy")
    parser.add_argument("--db", type=str, default="data/paperbot.sqlite3", help="Database path")
    parser.add_argument("--model", type=str, help="Model path")
    parser.add_argument("--output", type=str, default="backtest_results.json", help="Output path")
    parser.add_argument("--days", type=int, default=7, help="Days to backtest")
    
    args = parser.parse_args()
    
    run_backtest(
        db_path=Path(args.db),
        model_path=args.model,
        output_path=Path(args.output),
        days_back=args.days,
    )
