"""Polymarket CLOB API integration for live trading."""

import asyncio
import hashlib
import hmac
import json
import time
from datetime import datetime, UTC
from typing import Any, Optional

import aiohttp
import requests
from pathlib import Path


class PolymarketCLOBClient:
    """Polymarket CLOB API client for live trading."""
    
    BASE_URL = "https://clob.polymarket.com"
    
    def __init__(
        self,
        api_key: str,
        private_key: str,
        signature_type: str = "ECDSA",
    ) -> None:
        """
        Initialize Polymarket CLOB client.
        
        Args:
            api_key: Polymarket API key
            private_key: Private key for signing (hex format for ECDSA)
            signature_type: Signature algorithm (ECDSA or HMAC)
        """
        self.api_key = api_key
        self.private_key = private_key
        self.signature_type = signature_type
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    def _sign_request(self, method: str, path: str, body: str = "") -> dict:
        """
        Sign request for Polymarket API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path
            body: Request body (empty string for GET)
        
        Returns:
            Signature headers
        """
        if self.signature_type == "ECDSA":
            # ECDSA signing (more secure for production)
            from eth_account.messages import encode_defunct
            from eth_account import Account
            
            message = f"{method}{path}{body}{self.api_key}".encode()
            message_hash = encode_defunct(text=message.hex())
            
            try:
                # Private key should be in format: 0x...
                account = Account.from_key(self.private_key)
                signed = account.sign_message(message_hash)
                
                return {
                    "POLY-SIGNATURE": signed.signature.hex(),
                    "POLY-SIGNED-BY": account.address,
                    "POLY-API-KEY": self.api_key,
                }
            except Exception as e:
                raise ValueError(f"ECDSA signing failed: {e}")
        
        else:
            # HMAC signing (simpler, for testing)
            message = f"{method}{path}{body}{self.api_key}".encode()
            signature = hmac.new(
                self.private_key.encode(),
                message,
                hashlib.sha256,
            ).hexdigest()
            
            return {
                "POLY-SIGNATURE": signature,
                "POLY-API-KEY": self.api_key,
            }
    
    async def get_markets(self, tag: str = "BTC") -> list[dict]:
        """
        Get available markets.
        
        Args:
            tag: Market tag filter (e.g., "BTC")
        
        Returns:
            List of market objects
        """
        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")
        
        path = "/markets"
        headers = self._sign_request("GET", path)
        
        async with self.session.get(
            f"{self.BASE_URL}{path}",
            headers=headers,
            params={"tag": tag},
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("data", [])
            else:
                raise RuntimeError(f"Failed to get markets: {resp.status}")
    
    async def get_market(self, market_id: str) -> dict:
        """
        Get market details.
        
        Args:
            market_id: Market ID
        
        Returns:
            Market object
        """
        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")
        
        path = f"/markets/{market_id}"
        headers = self._sign_request("GET", path)
        
        async with self.session.get(
            f"{self.BASE_URL}{path}",
            headers=headers,
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                raise RuntimeError(f"Failed to get market: {resp.status}")
    
    async def get_order_book(self, market_id: str) -> dict:
        """
        Get order book for market.
        
        Args:
            market_id: Market ID
        
        Returns:
            Order book (bids and asks)
        """
        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")
        
        path = f"/markets/{market_id}/orderbook"
        headers = self._sign_request("GET", path)
        
        async with self.session.get(
            f"{self.BASE_URL}{path}",
            headers=headers,
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                raise RuntimeError(f"Failed to get order book: {resp.status}")
    
    async def create_order(
        self,
        market_id: str,
        side: str,  # "BUY" or "SELL"
        price: float,  # 0.00 to 1.00
        size: float,  # Amount in USDC
        client_order_id: Optional[str] = None,
    ) -> dict:
        """
        Create an order.
        
        Args:
            market_id: Market ID
            side: "BUY" or "SELL"
            price: Price between 0 and 1
            size: Order size in USDC
            client_order_id: Optional client order ID
        
        Returns:
            Order response
        """
        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")
        
        if not 0 <= price <= 1:
            raise ValueError(f"Price must be between 0 and 1, got {price}")
        
        path = "/orders"
        body_dict = {
            "market_id": market_id,
            "side": side,
            "price": price,
            "size": size,
            "client_order_id": client_order_id or f"order_{int(time.time()*1000)}",
        }
        body = json.dumps(body_dict)
        
        headers = self._sign_request("POST", path, body)
        headers["Content-Type"] = "application/json"
        
        async with self.session.post(
            f"{self.BASE_URL}{path}",
            headers=headers,
            data=body,
        ) as resp:
            response = await resp.json()
            
            if resp.status in (200, 201):
                return response
            else:
                raise RuntimeError(f"Failed to create order: {response}")
    
    async def cancel_order(self, order_id: str) -> dict:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID to cancel
        
        Returns:
            Cancellation response
        """
        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")
        
        path = f"/orders/{order_id}"
        headers = self._sign_request("DELETE", path)
        
        async with self.session.delete(
            f"{self.BASE_URL}{path}",
            headers=headers,
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                raise RuntimeError(f"Failed to cancel order: {resp.status}")
    
    async def get_orders(self, market_id: Optional[str] = None) -> list[dict]:
        """
        Get user's orders.
        
        Args:
            market_id: Optional market filter
        
        Returns:
            List of orders
        """
        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")
        
        path = "/orders"
        headers = self._sign_request("GET", path)
        
        params = {}
        if market_id:
            params["market_id"] = market_id
        
        async with self.session.get(
            f"{self.BASE_URL}{path}",
            headers=headers,
            params=params,
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("data", [])
            else:
                raise RuntimeError(f"Failed to get orders: {resp.status}")
    
    async def get_balances(self) -> dict:
        """
        Get account balances.
        
        Returns:
            Balance information
        """
        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")
        
        path = "/account/balances"
        headers = self._sign_request("GET", path)
        
        async with self.session.get(
            f"{self.BASE_URL}{path}",
            headers=headers,
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                raise RuntimeError(f"Failed to get balances: {resp.status}")


class PolymarketLiveTrader:
    """Live trading bot integrated with Polymarket CLOB."""
    
    def __init__(
        self,
        api_key: str,
        private_key: str,
        market_id: str,
        prediction_engine,  # BTC5mPaperTradingBot instance
        config_path: Path = Path("src/btc5m_bot/config.py"),
    ) -> None:
        """
        Initialize live trader.
        
        Args:
            api_key: Polymarket API key
            private_key: Private key for signing
            market_id: Market ID to trade
            prediction_engine: Prediction model/bot instance
            config_path: Path to config file
        """
        self.client = PolymarketCLOBClient(api_key, private_key)
        self.market_id = market_id
        self.prediction_engine = prediction_engine
        self.config_path = config_path
        
        # Trading state
        self.active_orders: dict[str, dict] = {}
        self.positions: dict[str, float] = {}  # market_id -> position_size
        self.daily_pnl = 0.0
        self.daily_notional = 0.0
    
    async def get_market_info(self) -> dict:
        """Get current market information."""
        async with self.client as client:
            return await client.get_market(self.market_id)
    
    async def get_order_book(self) -> dict:
        """Get current order book."""
        async with self.client as client:
            return await client.get_order_book(self.market_id)
    
    async def place_trade(
        self,
        direction: str,  # "UP" or "DOWN"
        size: float,  # USDC amount
        confidence: float,
    ) -> dict:
        """
        Place a trade on Polymarket.
        
        Args:
            direction: "UP" or "DOWN"
            size: Trade size in USDC
            confidence: Confidence level (0-1)
        
        Returns:
            Trade result
        """
        async with self.client as client:
            # Get order book to find best price
            book = await client.get_order_book(self.market_id)
            
            if not book:
                raise RuntimeError("Failed to get order book")
            
            # Determine side and price
            if direction == "UP":
                side = "BUY"
                # Buy at best ask price
                asks = book.get("asks", [])
                if asks:
                    price = float(asks[0][0])
                else:
                    price = 0.55  # Default bid price for YES
            else:  # DOWN
                side = "SELL"
                # Sell at best bid price
                bids = book.get("bids", [])
                if bids:
                    price = float(bids[0][0])
                else:
                    price = 0.45  # Default bid price for NO
            
            # Adjust price based on confidence
            price_adjustment = (confidence - 0.5) * 0.05
            adjusted_price = max(0.01, min(0.99, price + price_adjustment))
            
            # Place order
            result = await client.create_order(
                market_id=self.market_id,
                side=side,
                price=adjusted_price,
                size=size,
            )
            
            # Track order
            if "id" in result:
                self.active_orders[result["id"]] = {
                    "direction": direction,
                    "side": side,
                    "size": size,
                    "price": adjusted_price,
                    "confidence": confidence,
                    "timestamp": datetime.now(UTC),
                }
            
            return result
    
    async def cancel_all_orders(self) -> int:
        """
        Cancel all active orders.
        
        Returns:
            Number of orders cancelled
        """
        async with self.client as client:
            cancelled = 0
            orders = await client.get_orders(market_id=self.market_id)
            
            for order in orders:
                if order["status"] in ("OPEN", "PENDING"):
                    try:
                        await client.cancel_order(order["id"])
                        cancelled += 1
                    except Exception as e:
                        print(f"Failed to cancel order {order['id']}: {e}")
            
            return cancelled
    
    async def get_account_info(self) -> dict:
        """Get account information."""
        async with self.client as client:
            return await client.get_balances()
    
    async def run_trading_loop(
        self,
        interval_seconds: int = 60,
        max_cycles: Optional[int] = None,
    ) -> None:
        """
        Run live trading loop.
        
        Args:
            interval_seconds: Time between predictions
            max_cycles: Max cycles to run (None = infinite)
        """
        print("\n" + "="*70)
        print("🚀 POLYMARKET LIVE TRADING")
        print("="*70)
        print(f"Market ID: {self.market_id}")
        print(f"Cycle Interval: {interval_seconds}s")
        print()
        
        cycle = 0
        start_time = datetime.now(UTC)
        
        try:
            while True:
                cycle += 1
                
                if max_cycles and cycle > max_cycles:
                    print(f"\n✓ Reached max cycles: {max_cycles}")
                    break
                
                cycle_start = datetime.now(UTC)
                
                try:
                    # Get prediction from bot
                    prediction = self.prediction_engine.predict_next_move()
                    
                    if not prediction:
                        print(f"[{cycle:05d}] ⊘ No prediction available")
                        continue
                    
                    direction = prediction.get("direction", "UP")
                    probability = prediction.get("probability_up", 0.5)
                    confidence = prediction.get("confidence", 0.5)
                    
                    # Check if we should trade
                    if confidence < 0.55:
                        print(f"[{cycle:05d}] ⊘ Low confidence ({confidence*100:.1f}%), HOLD")
                        continue
                    
                    # Place trade
                    try:
                        result = await self.place_trade(
                            direction=direction,
                            size=10.0,  # $10 per trade
                            confidence=confidence,
                        )
                        
                        print(
                            f"[{cycle:05d}] ✓ ORDER: {direction} ${10.0:.2f} "
                            f"P={probability*100:.1f}% C={confidence*100:.1f}%"
                        )
                    except Exception as e:
                        print(f"[{cycle:05d}] ✗ Order failed: {e}")
                    
                    # Sleep until next cycle
                    elapsed = (datetime.now(UTC) - cycle_start).total_seconds()
                    remaining = max(0, interval_seconds - elapsed)
                    
                    if remaining > 0:
                        await asyncio.sleep(remaining)
                
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    print(f"[{cycle:05d}] ✗ Error: {e}")
                    await asyncio.sleep(interval_seconds)
        
        except KeyboardInterrupt:
            print("\n\n" + "="*70)
            print("⊘ Trading stopped by user")
            print("="*70)
        finally:
            # Cancel remaining orders
            try:
                cancelled = await self.cancel_all_orders()
                print(f"✓ Cancelled {cancelled} active orders")
            except Exception as e:
                print(f"Error cancelling orders: {e}")
            
            # Print summary
            duration = (datetime.now(UTC) - start_time).total_seconds()
            print(f"\nTrading session duration: {duration/60:.1f} minutes")
            print(f"Total cycles: {cycle}")


async def test_polymarket_connection(
    api_key: str,
    private_key: str,
) -> bool:
    """
    Test Polymarket API connection.
    
    Args:
        api_key: API key
        private_key: Private key
    
    Returns:
        True if connection successful
    """
    try:
        async with PolymarketCLOBClient(api_key, private_key) as client:
            # Try to get BTC markets
            markets = await client.get_markets(tag="BTC")
            
            if markets:
                print(f"✓ Connected to Polymarket")
                print(f"✓ Found {len(markets)} BTC markets:")
                
                for market in markets[:3]:
                    print(f"  - {market.get('question', 'N/A')[:50]}")
                    print(f"    ID: {market.get('id')}")
                
                return True
            else:
                print("✗ No markets found")
                return False
    
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return False


if __name__ == "__main__":
    print("""
Polymarket Live Trading Integration
═══════════════════════════════════

Configuration needed:
  1. Get API key and private key from https://polymarket.com
  2. Edit config.py with your credentials
  3. Choose a market ID to trade
  4. Run the trading bot

Example usage:
  async def main():
      async with PolymarketCLOBClient(api_key, private_key) as client:
          markets = await client.get_markets()
          print(markets)
  
  asyncio.run(main())
""")
