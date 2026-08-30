"""High-frequency order execution engine for 1000+/day trading volume."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, asdict
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass
class Order:
    """Represents a single trade order."""
    order_id: str
    timestamp: datetime
    market_id: str
    side: str  # "UP" or "DOWN"
    size: float  # in USD
    predicted_probability: float
    confidence: float
    entry_price: float | None = None
    status: str = "PENDING"  # PENDING, FILLED, REJECTED, CANCELED
    filled_at: datetime | None = None
    pnl: float | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        if self.filled_at:
            data["filled_at"] = self.filled_at.isoformat()
        return data


class OrderExecutor:
    """Execute orders with minimal latency for high-frequency trading."""
    
    def __init__(
        self,
        min_confidence: float = 0.55,
        min_edge: float = 0.05,
        max_order_size_usd: float = 10.0,
        rate_limit_per_minute: int = 200,
    ) -> None:
        """
        Initialize order executor.
        
        Args:
            min_confidence: Minimum confidence to place order (0-1)
            min_edge: Minimum edge between prediction and market price
            max_order_size_usd: Maximum size per order in USD
            rate_limit_per_minute: Max orders per minute (for Polymarket CLOB)
        """
        self.min_confidence = min_confidence
        self.min_edge = min_edge
        self.max_order_size_usd = max_order_size_usd
        self.rate_limit_per_minute = rate_limit_per_minute
        
        self.orders: dict[str, Order] = {}
        self.order_history: list[Order] = []
        self.last_order_time = 0.0
        self.orders_this_minute = 0
        self.minute_start = time.time()
    
    def should_trade(
        self,
        prediction: dict[str, Any],
        market_data: dict[str, Any],
    ) -> bool:
        """
        Determine if we should place an order based on prediction and market conditions.
        
        Args:
            prediction: Output from predictor with probability and confidence
            market_data: Current market data (bid/ask prices, etc.)
        
        Returns:
            True if trade conditions are met
        """
        # Check confidence threshold
        confidence = prediction.get("confidence", 0.5)
        if confidence < self.min_confidence:
            return False
        
        # Check probability edge
        prob_up = prediction.get("probability_up", 0.5)
        prob_down = 1 - prob_up
        
        market_bid_up = market_data.get("bid_up", 0.5)
        market_ask_up = market_data.get("ask_up", 0.5)
        market_bid_down = market_data.get("bid_down", 0.5)
        market_ask_down = market_data.get("ask_down", 0.5)
        
        # Check edge for UP position
        if prob_up > 0.5:
            edge_up = prob_up - market_ask_up
            if edge_up < self.min_edge:
                return False
        else:
            edge_down = prob_down - market_ask_down
            if edge_down < self.min_edge:
                return False
        
        return True
    
    def create_order(
        self,
        market_id: str,
        prediction: dict[str, Any],
        market_data: dict[str, Any],
        dynamic_sizing: bool = True,
    ) -> Order | None:
        """
        Create and submit an order.
        
        Args:
            market_id: Polymarket market ID
            prediction: Prediction result with probability and confidence
            market_data: Market data with bid/ask prices
            dynamic_sizing: Use Kelly Criterion for position sizing
        
        Returns:
            Order object if created, None otherwise
        """
        # Check rate limiting
        if not self._check_rate_limit():
            return None
        
        # Check trading conditions
        if not self.should_trade(prediction, market_data):
            return None
        
        # Determine side
        prob_up = prediction.get("probability_up", 0.5)
        side = "UP" if prob_up > 0.5 else "DOWN"
        
        # Determine size
        if dynamic_sizing:
            size = self._kelly_size(prediction)
        else:
            size = min(self.max_order_size_usd, 5.0)  # Default 5 USD per order
        
        # Get entry price
        if side == "UP":
            entry_price = market_data.get("ask_up", 0.5)
        else:
            entry_price = market_data.get("ask_down", 0.5)
        
        # Create order
        order = Order(
            order_id=str(uuid4()),
            timestamp=datetime.now(UTC),
            market_id=market_id,
            side=side,
            size=size,
            predicted_probability=prob_up,
            confidence=prediction.get("confidence", 0.5),
            entry_price=entry_price,
        )
        
        # Store order
        self.orders[order.order_id] = order
        self.order_history.append(order)
        
        return order
    
    def fill_order(
        self,
        order_id: str,
        fill_price: float | None = None,
        filled_at: datetime | None = None,
    ) -> bool:
        """
        Mark an order as filled.
        
        Args:
            order_id: Order ID to fill
            fill_price: Actual fill price (if different from entry)
            filled_at: Fill timestamp
        
        Returns:
            True if order was filled
        """
        if order_id not in self.orders:
            return False
        
        order = self.orders[order_id]
        order.status = "FILLED"
        order.filled_at = filled_at or datetime.now(UTC)
        
        if fill_price:
            order.entry_price = fill_price
        
        return True
    
    def settle_order(
        self,
        order_id: str,
        outcome: str,  # "WIN" or "LOSS"
        payout: float = 0.0,
    ) -> bool:
        """
        Settle a completed order after market resolution.
        
        Args:
            order_id: Order ID to settle
            outcome: "WIN" or "LOSS"
            payout: Actual payout value
        
        Returns:
            True if settled successfully
        """
        if order_id not in self.orders:
            return False
        
        order = self.orders[order_id]
        
        if outcome == "WIN":
            order.pnl = payout - order.size
        else:
            order.pnl = -order.size
        
        return True
    
    def get_open_orders(self) -> list[Order]:
        """Get all open orders."""
        return [o for o in self.orders.values() if o.status == "PENDING"]
    
    def get_filled_orders(self) -> list[Order]:
        """Get all filled orders."""
        return [o for o in self.orders.values() if o.status == "FILLED"]
    
    def get_stats(self) -> dict[str, Any]:
        """Get trading statistics."""
        filled = self.get_filled_orders()
        settled = [o for o in filled if o.pnl is not None]
        
        total_orders = len(self.order_history)
        filled_orders = len(filled)
        settled_orders = len(settled)
        
        if filled_orders > 0:
            fill_rate = filled_orders / total_orders
        else:
            fill_rate = 0.0
        
        if settled_orders > 0:
            wins = sum(1 for o in settled if o.pnl > 0)
            win_rate = wins / settled_orders
            avg_pnl = sum(o.pnl or 0 for o in settled) / settled_orders
        else:
            win_rate = 0.0
            avg_pnl = 0.0
        
        return {
            "total_orders": total_orders,
            "filled_orders": filled_orders,
            "settled_orders": settled_orders,
            "fill_rate": fill_rate,
            "win_rate": win_rate,
            "average_pnl": avg_pnl,
            "total_pnl": sum(o.pnl or 0 for o in settled),
        }
    
    # ==================== HELPER METHODS ====================
    
    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits."""
        current_time = time.time()
        
        # Reset minute counter if needed
        if current_time - self.minute_start >= 60:
            self.minute_start = current_time
            self.orders_this_minute = 0
        
        # Check limit
        if self.orders_this_minute >= self.rate_limit_per_minute:
            return False
        
        # Check minimum time between orders (to avoid API throttling)
        if current_time - self.last_order_time < 0.3:  # At least 300ms between orders
            return False
        
        # Update counters
        self.last_order_time = current_time
        self.orders_this_minute += 1
        
        return True
    
    def _kelly_size(self, prediction: dict[str, Any]) -> float:
        """
        Calculate order size using Kelly Criterion.
        
        Kelly formula: f* = (p * b - q) / b
        where:
            p = probability of win
            q = probability of loss (1 - p)
            b = odds (payout - 1)
        
        Args:
            prediction: Prediction with probability
        
        Returns:
            Suggested position size in USD
        """
        prob_win = prediction.get("probability_up", 0.5)
        confidence = prediction.get("confidence", 0.5)
        
        # Assume 2:1 payout (0.5 USD investment → 1 USD if correct)
        b = 1.0  # Binary outcome
        
        # Kelly fraction
        if prob_win > 0.5:
            kelly_fraction = (prob_win - (1 - prob_win)) / b
        else:
            kelly_fraction = ((1 - prob_win) - prob_win) / b
        
        # Kelly fraction is risky; use fractional Kelly (25-50%)
        fractional_kelly = kelly_fraction * 0.25
        fractional_kelly = max(0, min(0.1, fractional_kelly))  # Cap at 10% of bankroll
        
        # Base bankroll is 1000 USD (paper trading starting cash)
        bankroll = 1000
        base_size = bankroll * fractional_kelly
        
        # Confidence-weighted sizing
        size = base_size * (0.5 + confidence * 0.5)  # Scale by confidence
        
        # Respect maximum
        size = min(size, self.max_order_size_usd)
        
        return max(1.0, size)  # Minimum 1 USD per order


class RiskManager:
    """Manage risk and position limits for high-frequency trading."""
    
    def __init__(
        self,
        max_daily_notional: float = 25000.0,
        max_daily_loss: float = 500.0,
        max_open_positions: int = 50,
        max_single_position: float = 100.0,
        stop_loss_pct: float = 0.05,
    ) -> None:
        """
        Initialize risk manager.
        
        Args:
            max_daily_notional: Max total notional per day
            max_daily_loss: Max loss before stopping trading
            max_open_positions: Max concurrent open positions
            max_single_position: Max size for single order
            stop_loss_pct: Stop loss percentage
        """
        self.max_daily_notional = max_daily_notional
        self.max_daily_loss = max_daily_loss
        self.max_open_positions = max_open_positions
        self.max_single_position = max_single_position
        self.stop_loss_pct = stop_loss_pct
        
        self.daily_notional = 0.0
        self.daily_loss = 0.0
        self.open_positions = 0
        self.last_reset = datetime.now(UTC)
    
    def can_trade(self, order_size: float, current_loss: float) -> bool:
        """Check if trading is allowed based on risk limits."""
        # Check daily notional
        if self.daily_notional + order_size > self.max_daily_notional:
            return False
        
        # Check daily loss
        if self.daily_loss + abs(current_loss) > self.max_daily_loss:
            return False
        
        # Check open positions
        if self.open_positions >= self.max_open_positions:
            return False
        
        # Check single position size
        if order_size > self.max_single_position:
            return False
        
        return True
    
    def record_trade(self, order: Order) -> None:
        """Record a trade for risk accounting."""
        self.daily_notional += order.size
        self.open_positions += 1
        
        # Reset daily counters if new day
        now = datetime.now(UTC)
        if (now - self.last_reset).days > 0:
            self.daily_notional = order.size
            self.daily_loss = 0.0
            self.open_positions = 1
            self.last_reset = now
    
    def record_settlement(self, order: Order) -> None:
        """Record order settlement."""
        if order.pnl is not None and order.pnl < 0:
            self.daily_loss += abs(order.pnl)
        
        self.open_positions = max(0, self.open_positions - 1)
    
    def get_risk_status(self) -> dict[str, Any]:
        """Get current risk status."""
        return {
            "daily_notional": self.daily_notional,
            "daily_notional_limit": self.max_daily_notional,
            "daily_notional_used_pct": (self.daily_notional / self.max_daily_notional) * 100,
            "daily_loss": self.daily_loss,
            "daily_loss_limit": self.max_daily_loss,
            "daily_loss_used_pct": (self.daily_loss / self.max_daily_loss) * 100,
            "open_positions": self.open_positions,
            "max_open_positions": self.max_open_positions,
            "trading_allowed": self.can_trade(self.max_single_position, 0),
        }
