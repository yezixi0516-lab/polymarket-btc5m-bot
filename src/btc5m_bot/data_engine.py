"""Real-time BTC data pipeline from Binance WebSocket."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import sqlite3
from pathlib import Path


class DataSourceError(RuntimeError):
    """Remote data source error."""


def utc_now() -> datetime:
    return datetime.now(UTC)


def parse_iso_time(value: str | int | float | None) -> datetime | None:
    """Parse ISO or Unix timestamp."""
    if not value:
        return None
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
        timestamp = float(value)
        # Binance uses milliseconds
        if timestamp > 100_000_000_000:
            timestamp /= 1000
        return datetime.fromtimestamp(timestamp, UTC)
    if not isinstance(value, str):
        raise ValueError("Unsupported timestamp format")
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


class BinanceDataProvider:
    """Fetch historical BTC data from Binance REST API."""
    
    def __init__(self) -> None:
        self.base_url = "https://api.binance.com/api/v3"
        self.timeout = 12
    
    def _http_get(self, endpoint: str, params: dict[str, str] | None = None) -> Any:
        """Make HTTP GET request."""
        full_url = f"{self.base_url}{endpoint}"
        if params:
            full_url += f"?{urlencode(params)}"
        
        request = Request(
            full_url,
            headers={
                "Accept": "application/json",
                "User-Agent": "btc5m-paperbot/0.1"
            }
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise DataSourceError(f"Binance API error: {exc}") from exc
    
    def get_klines(
        self, 
        symbol: str = "BTCUSDT",
        interval: str = "1m",
        limit: int = 1000,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Fetch historical klines (candlesticks).
        
        Args:
            symbol: Trading pair (default: BTCUSDT)
            interval: Time interval (1m, 5m, etc.)
            limit: Number of candles to fetch (max 1000)
            start_time: Start time in milliseconds
            end_time: End time in milliseconds
        
        Returns:
            List of candle data
        """
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": str(limit),
        }
        if start_time:
            params["startTime"] = str(start_time)
        if end_time:
            params["endTime"] = str(end_time)
        
        response = self._http_get("/klines", params)
        if not isinstance(response, list):
            raise DataSourceError("Unexpected Binance klines format")
        
        klines = []
        for raw in response:
            try:
                kline = {
                    "open_time": int(raw[0]),
                    "open": float(raw[1]),
                    "high": float(raw[2]),
                    "low": float(raw[3]),
                    "close": float(raw[4]),
                    "volume": float(raw[5]),
                    "close_time": int(raw[6]),
                    "quote_asset_volume": float(raw[7]),
                    "number_of_trades": int(raw[8]),
                    "taker_buy_base_asset_volume": float(raw[9]),
                    "taker_buy_quote_asset_volume": float(raw[10]),
                }
                klines.append(kline)
            except (IndexError, ValueError, TypeError):
                continue
        
        return klines
    
    def fetch_historical_data(
        self,
        days_back: int = 30,
        symbol: str = "BTCUSDT",
        interval: str = "1m",
    ) -> list[dict[str, Any]]:
        """
        Fetch historical BTC data for the past N days.
        
        Args:
            days_back: Number of days of history to fetch
            symbol: Trading pair
            interval: Time interval
        
        Returns:
            List of all klines
        """
        all_klines = []
        now_ms = int(time.time() * 1000)
        
        # Binance 1m candle is ~1 minute, 5m is ~5 minutes
        if interval == "1m":
            ms_per_candle = 60 * 1000
        elif interval == "5m":
            ms_per_candle = 5 * 60 * 1000
        else:
            ms_per_candle = 60 * 1000
        
        # Start from N days ago
        start_ms = now_ms - (days_back * 24 * 60 * 60 * 1000)
        
        # Fetch in chunks (max 1000 per request)
        current_start = start_ms
        while current_start < now_ms:
            try:
                print(f"Fetching data from {datetime.fromtimestamp(current_start/1000, UTC)}")
                klines = self.get_klines(
                    symbol=symbol,
                    interval=interval,
                    limit=1000,
                    start_time=current_start,
                    end_time=now_ms,
                )
                if not klines:
                    break
                
                all_klines.extend(klines)
                
                # Move to next chunk (start after last candle)
                current_start = klines[-1]["close_time"] + 1
                
                # Rate limiting
                time.sleep(0.1)
            except DataSourceError as e:
                print(f"Error fetching data: {e}")
                break
        
        return all_klines


class PriceDataStore:
    """Local SQLite storage for price data."""
    
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(db_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._create_schema()
    
    def close(self) -> None:
        self.connection.close()
    
    def _create_schema(self) -> None:
        """Create price data tables."""
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS klines_1m (
                open_time INTEGER PRIMARY KEY,
                symbol TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                quote_asset_volume REAL NOT NULL,
                number_of_trades INTEGER,
                taker_buy_base_asset_volume REAL,
                taker_buy_quote_asset_volume REAL,
                fetched_at TEXT NOT NULL
            );
            
            CREATE TABLE IF NOT EXISTS klines_5m (
                open_time INTEGER PRIMARY KEY,
                symbol TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                quote_asset_volume REAL,
                number_of_trades INTEGER,
                taker_buy_base_asset_volume REAL,
                taker_buy_quote_asset_volume REAL,
                fetched_at TEXT NOT NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_klines_1m_symbol ON klines_1m(symbol, open_time);
            CREATE INDEX IF NOT EXISTS idx_klines_5m_symbol ON klines_5m(symbol, open_time);
        """)
        self.connection.commit()
    
    def insert_klines(
        self,
        klines: list[dict[str, Any]],
        symbol: str = "BTCUSDT",
        interval: str = "1m",
    ) -> int:
        """Insert klines into database."""
        table_name = f"klines_{interval}"
        now = utc_now().isoformat()
        
        inserted = 0
        for kline in klines:
            try:
                self.connection.execute(
                    f"""
                    INSERT OR IGNORE INTO {table_name}
                    (open_time, symbol, open, high, low, close, volume, quote_asset_volume,
                     number_of_trades, taker_buy_base_asset_volume, taker_buy_quote_asset_volume, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        kline["open_time"],
                        symbol,
                        kline["open"],
                        kline["high"],
                        kline["low"],
                        kline["close"],
                        kline["volume"],
                        kline.get("quote_asset_volume"),
                        kline.get("number_of_trades"),
                        kline.get("taker_buy_base_asset_volume"),
                        kline.get("taker_buy_quote_asset_volume"),
                        now,
                    ),
                )
                inserted += 1
            except sqlite3.Error:
                continue
        
        self.connection.commit()
        return inserted
    
    def get_klines(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "1m",
        limit: int = 300,
        before_time: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get recent klines from database."""
        table_name = f"klines_{interval}"
        
        if before_time is None:
            query = f"""
                SELECT * FROM {table_name}
                WHERE symbol = ?
                ORDER BY open_time DESC
                LIMIT ?
            """
            rows = self.connection.execute(query, (symbol, limit)).fetchall()
        else:
            query = f"""
                SELECT * FROM {table_name}
                WHERE symbol = ? AND open_time < ?
                ORDER BY open_time DESC
                LIMIT ?
            """
            rows = self.connection.execute(query, (symbol, before_time, limit)).fetchall()
        
        return [dict(row) for row in reversed(rows)]
    
    def get_latest_kline(self, symbol: str = "BTCUSDT", interval: str = "1m") -> dict[str, Any] | None:
        """Get the most recent kline."""
        table_name = f"klines_{interval}"
        row = self.connection.execute(
            f"SELECT * FROM {table_name} WHERE symbol = ? ORDER BY open_time DESC LIMIT 1",
            (symbol,),
        ).fetchone()
        return dict(row) if row else None
    
    def get_kline_count(self, symbol: str = "BTCUSDT", interval: str = "1m") -> int:
        """Get number of klines stored."""
        table_name = f"klines_{interval}"
        row = self.connection.execute(
            f"SELECT COUNT(*) FROM {table_name} WHERE symbol = ?",
            (symbol,),
        ).fetchone()
        return int(row[0]) if row else 0


def resample_1m_to_5m(klines_1m: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Resample 1-minute klines to 5-minute klines.
    
    Args:
        klines_1m: List of 1-minute candlesticks
    
    Returns:
        List of 5-minute candlesticks
    """
    if not klines_1m:
        return []
    
    klines_5m = []
    current_5m = None
    
    for kline in klines_1m:
        # Determine which 5m bucket this 1m belongs to
        timestamp_ms = kline["open_time"]
        bucket_start = (timestamp_ms // (5 * 60 * 1000)) * (5 * 60 * 1000)
        
        if current_5m is None or current_5m["open_time"] != bucket_start:
            # Start new 5m candle
            if current_5m is not None:
                klines_5m.append(current_5m)
            
            current_5m = {
                "open_time": bucket_start,
                "open": kline["open"],
                "high": kline["high"],
                "low": kline["low"],
                "close": kline["close"],
                "volume": kline["volume"],
                "quote_asset_volume": kline.get("quote_asset_volume", 0),
                "number_of_trades": kline.get("number_of_trades", 0),
                "taker_buy_base_asset_volume": kline.get("taker_buy_base_asset_volume", 0),
                "taker_buy_quote_asset_volume": kline.get("taker_buy_quote_asset_volume", 0),
            }
        else:
            # Update current 5m candle
            current_5m["high"] = max(current_5m["high"], kline["high"])
            current_5m["low"] = min(current_5m["low"], kline["low"])
            current_5m["close"] = kline["close"]
            current_5m["volume"] += kline["volume"]
            current_5m["quote_asset_volume"] += kline.get("quote_asset_volume", 0)
            current_5m["number_of_trades"] += kline.get("number_of_trades", 0)
            current_5m["taker_buy_base_asset_volume"] += kline.get("taker_buy_base_asset_volume", 0)
            current_5m["taker_buy_quote_asset_volume"] += kline.get("taker_buy_quote_asset_volume", 0)
    
    if current_5m is not None:
        klines_5m.append(current_5m)
    
    return klines_5m
