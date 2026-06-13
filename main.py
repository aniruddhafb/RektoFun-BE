"""
RektoFun Backend API

FastAPI + Supabase backend for persisting challenge metadata after a
successful Solana transaction.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from services.database import db_service, get_db_client
from services.challenge_monitor_service import (
    start_challenge_monitor,
    stop_challenge_monitor,
)
from routes import users, challenges, positions

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifespan events.
    
    Initializes the Supabase database connection on startup,
    starts the challenge monitor for real-time price tracking,
    and cleans up resources on shutdown.
    """
    # Startup: Initialize database connection
    logger.info("Initializing Supabase database connection...")
    try:
        db_service.initialize() 
        logger.info("Supabase database connection established successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Supabase connection: {e}")
        raise
    
    # Startup: Initialize challenge monitor
    logger.info("Starting challenge monitor service...")
    try:
        await start_challenge_monitor()
        logger.info("Challenge monitor service started successfully")
    except Exception as e:
        logger.error(f"Failed to start challenge monitor service: {e}")
        # Don't raise - we can still run without the monitor
    
    yield
    
    # Shutdown: Cleanup resources
    logger.info("Shutting down and cleaning up resources...")
    
    # Stop challenge monitor
    try:
        await stop_challenge_monitor()
        logger.info("Challenge monitor service stopped")
    except Exception as e:
        logger.error(f"Error stopping challenge monitor: {e}")
    
    # Close database connection
    await db_service.close()
    logger.info("Cleanup completed")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """
    Health check endpoint to verify API and database connectivity.
    """
    return {
        "status": "healthy",
        "version": settings.app_version,
        "database_connected": db_service.is_connected()
    }



# Include routers
app.include_router(users.router, prefix="/api", tags=["users"])

# Include challenge routes
app.include_router(challenges.router, prefix="/api", tags=["challenges"])

# Include position routes
app.include_router(positions.router, prefix="/api", tags=["positions"])

# Future routers (to be added as needed)
# app.include_router(transactions.router, prefix="/api/v1/transactions", tags=["transactions"])


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )