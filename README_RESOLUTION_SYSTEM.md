# Challenge Resolution System

This document describes the automated challenge resolution system that handles challenge expiry and resolution dates.

## Overview

The system consists of three components working together:

1. **Challenge Model** (`models/challenge.py`) - Defines challenge data structure with `expiry`, `resolution_date`, and `final_price`
2. **Challenge Service** (`services/challenge_service.py`) - Database operations for challenge lifecycle
3. **Challenge Monitor Service** (`services/challenge_monitor_service.py`) - Real-time price monitoring and resolution
## Key Concepts

### Expiry Date (`expiry`)
- **Purpose**: When betting closes - no new positions can be created
- **Behavior**: Challenge continues monitoring price targets after expiry
- **Validation**: Frontend/API should reject new positions after expiry

### Resolution Date (`resolution_date`)
- **Purpose**: When the challenge officially ends
- **Behavior**: 
  - Challenges that hit their target before resolution_date are resolved immediately
  - Challenges that haven't hit their target by resolution_date are resolved with the current price
- **Triggered By**: pg_cron job running daily at midnight UTC

### Final Price (`final_price`)
- Set when a challenge is resolved (either by hitting target or reaching resolution_date)
- Stored in the database for historical record and winner calculation

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Challenge Lifecycle                      │
└─────────────────────────────────────────────────────────────────┘

    CREATED
       │
       ▼
    ┌─────────┐     Target Hit      ┌───────────┐
    │  OPEN   │ ──────────────────► │ RESOLVED  │
    │         │                     │(immediate)│
    │         │                     └───────────┘
    │         │                           ▲
    │         │                     resolution_date
    │         │                     reached
    │         │                           │
    │         └───────────────────────────┘
    │            (resolve with current price)
    │         
    │  Betting closes on `expiry`
    │  Monitoring continues until `resolution_date`
    │         
    └─────────┘
```

### WebSocket Subscription Management

The Challenge Monitor Service uses a **reference counting** mechanism to efficiently manage WebSocket subscriptions when multiple challenges share the same trading pair:

```
┌─────────────────────────────────────────────────────────────────┐
│              Symbol-to-Challenges Mapping (Reference Counting)   │
└─────────────────────────────────────────────────────────────────┘

    BTCUSDT ──────┬──► Challenge #1 (Target: $50,000 UP)
                  ├──► Challenge #2 (Target: $55,000 UP)
                  └──► Challenge #3 (Target: $45,000 DOWN)
    
    ETHUSDT ──────┬──► Challenge #4 (Target: $3,000 UP)
                  └──► Challenge #5 (Target: $2,500 DOWN)
    
    Subscribe Rules:
    - Subscribe to BTCUSDT when Challenge #1 is added
    - Reuse existing subscription for Challenges #2, #3
    - Subscribe to ETHUSDT when Challenge #4 is added
    - Reuse existing subscription for Challenge #5
    
    Unsubscribe Rules:
    - Challenge #1 resolved → Keep BTCUSDT subscription
    - Challenge #2 resolved → Keep BTCUSDT subscription  
    - Challenge #3 resolved → Unsubscribe BTCUSDT (last one)
    - Challenge #4 resolved → Keep ETHUSDT subscription
    - Challenge #5 resolved → Unsubscribe ETHUSDT (last one)
```

**Key Features:**
- **Single WebSocket per Symbol**: Multiple challenges sharing the same trading pair use a single WebSocket subscription
- **Fan-out Pattern**: One price update fans out to all challenges using that symbol
- **Smart Unsubscribe**: Only unsubscribes when the last challenge for that symbol is removed
- **Thread-safe**: Uses asyncio.Lock for concurrent access to shared mappings

## Database Schema

### Challenge Table
```sql
- expiry: date (when betting closes)
- resolution_date: date (when challenge ends)
- final_price: numeric (set when resolved)
- status: ChallengeStatus (OPEN, RESOLVED, CANCELLED)
```

## Automated Resolution (pg_cron)

The system uses PostgreSQL's pg_cron extension to trigger resolution:

### Daily Resolution Job
- **Schedule**: Every day at midnight UTC (`0 0 * * *`)
- **Action**: Calls `resolve_challenges_due_today()` function
- **Behavior**: Resolves all OPEN challenges where `resolution_date <= today`

### Manual Execution
```sql
-- Run resolution manually
SELECT resolve_challenges_due_today();
```

## Backend Services

### ChallengeService Methods

```python
# Get challenges ready for resolution
await service.get_expired_open_challenges(resolution_date)

# Update challenge status
await service.update_challenge_status(
    challenge_id=123,
    new_status=ChallengeStatus.RESOLVED,
    final_price=45000.00
)
```

### ChallengeMonitorService Methods

```python
# Handle expiry (betting closed, continue monitoring)
await monitor.handle_expired_challenges()

# Resolve challenges where resolution_date reached
await monitor.resolve_challenges_by_date()

# Add new challenge to monitor
await monitor.add_challenge(challenge_data)

# Remove challenge from monitoring
await monitor.remove_challenge(challenge_id)

# Get currently monitored active challenges
monitor.get_active_challenges()
```

### ChallengeMonitorService Internal Structure

```python
class ChallengeMonitorService:
    def __init__(self):
        self._active_challenges: Dict[int, dict] = {}
        # symbol -> set of challenge_ids using that symbol
        self._symbol_challenges: Dict[str, Set[int]] = {}
        self._lock = asyncio.Lock()
```

**Method Details:**

#### `_monitor_challenge(challenge)`
- Adds challenge to `_active_challenges`
- Updates `_symbol_challenges[symbol]` with challenge_id
- **Subscribes to WebSocket only if this is the FIRST challenge for that symbol**

#### `_on_price_update(symbol, price_update)`
- Receives price updates per symbol
- Fans out to all challenges using that symbol via `_process_price_update_for_challenge()`
- Processes challenges in parallel with `asyncio.gather()`

#### `_resolve_challenge_immediately(challenge_id, hit_price)`
- Removes challenge from `_active_challenges`
- Removes challenge_id from `_symbol_challenges[symbol]`
- **Unsubscribes from WebSocket only if this was the LAST challenge for that symbol**
- Updates database with RESOLVED status

#### `remove_challenge(challenge_id)`
- Removes challenge from monitoring
- **Unsubscribes only if no other challenges use the same symbol**

## API Usage

### Creating a Challenge
```python
from models.challenge import ChallengeBase

challenge = ChallengeBase(
    ticker="BTC",
    direction="UP",
    target=50000.00,
    entry=48000.00,
    trading_pair="BTCUSDT",
    creator="user_123",
    pot_size=1000.00,
    expiry="2026-06-15",        # Betting closes June 15
    resolution_date="2026-06-20"  # Challenge ends June 20
)
```

### Resolving Challenges (Manual Trigger)
```python
from services.challenge_monitor_service import get_challenge_monitor

monitor = get_challenge_monitor()
await monitor.resolve_challenges_by_date()
```

## Winner Calculation

After resolution, winners are determined by:

```python
# 1. Get all positions for the challenge
positions = await position_service.get_positions_by_challenge_id(challenge_id)

# 2. For immediate resolution (target hit):
#    - Users on the correct side (matching direction) win
#    - Users on the wrong side lose

# 3. For resolution_date resolution:
#    - If final_price >= target: UP bets win
#    - If final_price < target: DOWN bets win
```

## Setup Instructions

1. **Apply Migration**:
   ```bash
   # Run the SQL migration in Supabase SQL Editor
   # migrations/002_add_resolution_system.sql
   ```

2. **Verify pg_cron**:
   ```sql
   -- Check if pg_cron is enabled
   SELECT * FROM pg_extension WHERE extname = 'pg_cron';
   
   -- View scheduled jobs
   SELECT * FROM cron.job;
   ```

3. **Monitor Logs**:
   ```sql
   -- View recent cron job executions
   SELECT * FROM cron.job_run_details ORDER BY start_time DESC LIMIT 10;
   ```

## Troubleshooting

### pg_cron not running
- Check if extension is enabled: `SHOW shared_preload_libraries;`
- Verify job exists: `SELECT * FROM cron.job;`
- Check for errors: `SELECT * FROM cron.job_run_details WHERE succeeded = false;`

### Challenges not resolving
- Verify `resolution_date` is set correctly
- Check that `status = 'OPEN'`
- Review application logs for resolution errors

### Price not available at resolution
- The system logs a warning and keeps the challenge OPEN
- Ensure WebSocket client is connected
- Consider adding a fallback price source (REST API)

### Multiple challenges sharing same trading pair
- **Expected behavior**: Only one WebSocket subscription per symbol
- Check logs for: "Subscribing to price updates for symbol: {symbol}" (first challenge)
- Check logs for: "Unsubscribed from {symbol} - no more challenges using it" (last challenge removed)
- If challenges aren't receiving updates, verify `_symbol_challenges` mapping

## Testing

### Manual Test
```python
import asyncio
from services.challenge_monitor_service import get_challenge_monitor

async def test_resolution():
    monitor = get_challenge_monitor()
    await monitor.resolve_challenges_by_date()
    
asyncio.run(test_resolution())
```

### Test Multiple Challenges on Same Symbol
```python
import asyncio
from services.challenge_monitor_service import get_challenge_monitor

async def test_shared_symbol():
    monitor = get_challenge_monitor()
    
    # Add multiple challenges with same trading pair
    challenge1 = {"id": 1, "ticker": "BTC", "trading_pair": "BTCUSDT", "target": 50000, "direction": "UP"}
    challenge2 = {"id": 2, "ticker": "BTC", "trading_pair": "BTCUSDT", "target": 55000, "direction": "UP"}
    
    await monitor.add_challenge(challenge1)  # Should subscribe to BTCUSDT
    await monitor.add_challenge(challenge2)  # Should reuse subscription
    
    # Resolve first challenge
    await monitor.remove_challenge(1)  # Should NOT unsubscribe
    
    # Resolve second challenge  
    await monitor.remove_challenge(2)  # Should unsubscribe from BTCUSDT
    
asyncio.run(test_shared_symbol())
```

### Database Test
```sql
-- Create a test challenge
INSERT INTO challenge (
    ticker, direction, target, entry, trading_pair, creator, 
    pot_size, status, expiry, resolution_date
) VALUES (
    'BTC', 'UP', 50000, 48000, 'BTCUSDT', 'test_user',
    1000, 'OPEN', CURRENT_DATE, CURRENT_DATE
);

-- Run resolution
SELECT resolve_challenges_due_today();

-- Verify
SELECT id, status, final_price FROM challenge WHERE creator = 'test_user';
```

## Security Considerations

- pg_cron runs with database owner privileges
- Resolution logic is in a database function (immutable)
- Final price is set at resolution time and cannot be modified
- Only OPEN challenges can be resolved
- WebSocket subscriptions are managed internally and cannot be manipulated externally