"""
Challenge Monitor Service for real-time price tracking and status updates.

This service monitors active challenges via WebSocket connections to Binance
and updates challenge statuses when target prices are reached.
"""

import asyncio
import logging
from typing import Dict, List
from datetime import datetime

from services.binance_ws_client import (
    get_binance_ws_client,
    PriceUpdate,
    start_binance_ws_client,
    stop_binance_ws_client,
)
from services.challenge_service import ChallengeService
from services.database import get_db_client
from models.challenge import ChallengeStatus, ChallengeBase

logger = logging.getLogger(__name__)


class ChallengeMonitorService:
    """
    Service that monitors active challenges and updates their status
    when target prices are hit via real-time WebSocket price feeds.
    """

    def __init__(self):
        self._active_challenges: Dict[str, dict] = {}
        self._lock = asyncio.Lock()
        self._challenge_service = None
        self._ws_client = None

    def _get_challenge_service(self) -> ChallengeService:
        """Lazy initialization of challenge service"""
        if self._challenge_service is None:
            db_client = get_db_client()
            self._challenge_service = ChallengeService(db_client)
        return self._challenge_service

    async def start(self):
        """Start the challenge monitor service"""
        logger.info("Starting Challenge Monitor Service...")
        
        # Start the WebSocket client
        await start_binance_ws_client()
        self._ws_client = get_binance_ws_client()
        
        # Load and monitor existing active challenges
        await self._load_active_challenges()
        
        logger.info("Challenge Monitor Service started")

    async def stop(self):
        """Stop the challenge monitor service"""
        logger.info("Stopping Challenge Monitor Service...")
        
        async with self._lock:
            self._active_challenges.clear()
        
        await stop_binance_ws_client()
        self._ws_client = None
        logger.info("Challenge Monitor Service stopped")

    async def _load_active_challenges(self):
        """Load active challenges from database and start monitoring them"""
        try:
            service = self._get_challenge_service()
            challenges = await service.get_active_challenges_raw()
            
            for challenge in challenges:
                await self._monitor_challenge(challenge)
                
            logger.info(f"Loaded and monitoring {len(challenges)} active challenges")
            
        except Exception as e:
            logger.error(f"Error loading active challenges: {e}")

    async def _monitor_challenge(self, challenge: ChallengeBase):
        """
        Start monitoring a challenge for price targets.
        
        Args:
            challenge: Challenge data dictionary
        """
        challenge_id = challenge["id"]
        ticker = challenge["ticker"]
        target = challenge["target"]
        direction = challenge["direction"]
        
        # Get trading pair from database
        symbol = challenge.get("trading_pair")
        
        async with self._lock:
            self._active_challenges[challenge_id] = {
                "challenge_id": challenge_id,
                "ticker": ticker,
                "trading_pair": symbol,
                "target": target,
                "direction": direction,
                "created_at": challenge.get("created_at"),
            }
        
        # Subscribe to price updates using the trading pair from database
        logger.info(f"Subscribing to price updates for symbol: {symbol}")
        await self._ws_client.subscribe(
            symbol=symbol,
            callback=lambda price_update, cid=challenge_id: self._on_price_update(cid, price_update)
        )
        
        logger.info(f"Started monitoring challenge {challenge_id}: {symbol} -> {target} ({direction})")

    async def _on_price_update(self, challenge_id: int, price_update: PriceUpdate):
        """
        Handle price update from WebSocket.
        
        Args:
            challenge_id: The challenge being monitored
            price_update: Price update data
        """
        try:
            async with self._lock:
                challenge_data = self._active_challenges.get(challenge_id)
                if not challenge_data:
                    return  # Challenge no longer active
                
                target = challenge_data["target"]
                direction = challenge_data["direction"]
                current_price = price_update.price
            
            # Check if target is hit
            target_hit = False
            
            if direction == "UP":
                # Target hit when price goes above or equals target
                if current_price >= target:
                    target_hit = True
            else:  # direction == "DOWN"
                # Target hit when price goes below or equals target
                if current_price <= target:
                    target_hit = True
            
            if target_hit:
                logger.info(f"Target hit for challenge {challenge_id}: "
                          f"price={current_price}, target={target}")
                await self._complete_challenge(challenge_id, current_price)
                
        except Exception as e:
            logger.error(f"Error processing price update for challenge {challenge_id}: {e}")

    async def _complete_challenge(self, challenge_id: int, hit_price: float):
        """
        Complete a challenge when target is hit.
        
        Args:
            challenge_id: The challenge to complete
            hit_price: The price at which target was hit
        """
        challenge_data = None
        try:
            async with self._lock:
                challenge_data = self._active_challenges.pop(challenge_id, None)
                if not challenge_data:
                    return  # Already completed or removed
            
            # Update challenge status in database
            service = self._get_challenge_service()
            await service.update_challenge_status(
                challenge_id=challenge_id,
                new_status=ChallengeStatus.RESOLVED,
                end_price=hit_price
            )
            
            # Unsubscribe from price updates for this symbol
            symbol = challenge_data.get("trading_pair")
            if symbol:
                await self._ws_client.unsubscribe(symbol)
            
            logger.info(f"Challenge {challenge_id} completed successfully at price {hit_price}")
            
        except Exception as e:
            logger.error(f"Error completing challenge {challenge_id}: {e}")
            # Re-add to active challenges if update failed
            if challenge_data:
                async with self._lock:
                    self._active_challenges[challenge_id] = challenge_data

    async def add_challenge(self, challenge: dict):
        """
        Add a new challenge to monitor.
        Called when a new challenge is created.
        
        Args:
            challenge: Challenge data dictionary
        """
        await self._monitor_challenge(challenge)
        logger.info(f"Added new challenge {challenge['id']} to monitor")

    async def remove_challenge(self, challenge_id: int):
        """
        Remove a challenge from monitoring.
        Called when a challenge is cancelled or completed externally.
        
        Args:
            challenge_id: The challenge to remove
        """
        async with self._lock:
            challenge_data = self._active_challenges.pop(challenge_id, None)
        
        if challenge_data:
            symbol = challenge_data.get("trading_pair")
            if symbol:
                await self._ws_client.unsubscribe(symbol)
            logger.info(f"Removed challenge {challenge_id} from monitoring")

    def get_active_challenges(self) -> List[dict]:
        """Get list of currently monitored active challenges"""
        return list(self._active_challenges.values())


# Global monitor service instance
_challenge_monitor: ChallengeMonitorService | None = None


def get_challenge_monitor() -> ChallengeMonitorService:
    """Get or create the global challenge monitor service"""
    global _challenge_monitor
    if _challenge_monitor is None:
        _challenge_monitor = ChallengeMonitorService()
    return _challenge_monitor


async def start_challenge_monitor():
    """Start the global challenge monitor service"""
    monitor = get_challenge_monitor()
    await monitor.start()


async def stop_challenge_monitor():
    """Stop the global challenge monitor service"""
    global _challenge_monitor
    if _challenge_monitor:
        await _challenge_monitor.stop()
        _challenge_monitor = None


async def monitor_new_challenge(challenge: dict):
    """
    Add a newly created challenge to the monitor.
    Call this when creating a new challenge.
    """
    monitor = get_challenge_monitor()
    await monitor.add_challenge(challenge)


async def stop_monitoring_challenge(challenge_id: int):
    """
    Stop monitoring a challenge.
    Call this when cancelling or deleting a challenge.
    """
    monitor = get_challenge_monitor()
    await monitor.remove_challenge(challenge_id)