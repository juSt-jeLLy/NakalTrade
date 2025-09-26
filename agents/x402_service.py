"""
x402 Payment Service for NakalTrade
Handles real blockchain payment verification for copy trading
"""

import os
import json
from typing import Dict, Any
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from x402.fastapi.middleware import require_payment
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="NakalTrade x402 Payment Service", version="1.0.0")

# Store payment records
payment_records: Dict[str, Any] = {}

# Get configuration from environment
WALLET_ADDRESS = os.getenv("PAYMENT_ADDRESS")
NETWORK = os.getenv("NETWORK", "polygon-amoy")
FACILITATOR_URL = os.getenv("FACILITATOR_URL", "https://x402.polygon.technology")
DEFAULT_PRICE = 0.01  # Default price in USD for the copy trade service fee

# Health check endpoint (no payment required)
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "NakalTrade x402 Payment Service",
        "network": NETWORK,
        "wallet": WALLET_ADDRESS[:6] + "..." + WALLET_ADDRESS[-4:] if WALLET_ADDRESS else "Not set"
    }

# Apply x402 payment middleware to the copytrade path
app.middleware("http")(
    require_payment(
        path="/copytrade/*",
        price=f"${DEFAULT_PRICE}",
        pay_to_address=WALLET_ADDRESS,
        network=NETWORK,
        facilitator_config={"url": FACILITATOR_URL},
        description="Copy Trade Service Fee"
    )
)

# Payment verification endpoint (protected by middleware above)
@app.post("/copytrade/{payment_id}")
async def verify_copy_trade(payment_id: str, request: Request):
    """
    This endpoint is protected by x402 middleware.
    It will only execute if payment has been verified.
    """
    logger.info(f"Payment verified for copy trade ID: {payment_id}")
    
    payment_records[payment_id] = {
        "status": "completed",
        "timestamp": datetime.now().isoformat(),
        "amount": DEFAULT_PRICE,
        "network": NETWORK,
        "verified": True,
        "tx_hash": request.headers.get("X-Transaction-Hash", f"0x{payment_id}")
    }
    
    return {
        "status": "paid",
        "payment_id": payment_id,
        "tx_hash": request.headers.get("X-Transaction-Hash", f"0x{payment_id}"),
        "message": "Copy trade fee successfully verified via x402"
    }

@app.get("/payment/status/{payment_id}")
async def check_payment_status(payment_id: str):
    """Check if a payment has been completed"""
    if payment_id in payment_records:
        return payment_records[payment_id]
    else:
        return { "status": "pending", "payment_id": payment_id }

@app.post("/payment/create")
async def create_payment_request(item_name: str = "Copy Trade", price: float = DEFAULT_PRICE):
    """
    Create a new payment request for a copy trade
    """
    import hashlib
    import time
    
    payment_id = hashlib.sha256(f"{item_name}{time.time()}".encode()).hexdigest()[:10]
    
    return {
        "payment_id": payment_id,
        "item": item_name,
        "price": price,
        "currency": "USDC",
        "network": NETWORK,
        "pay_to": WALLET_ADDRESS,
        "verification_url": f"/copytrade/{payment_id}"
    }

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("X402_PORT", 8402))
    logger.info(f"Starting NakalTrade x402 Service on port {port}")
    logger.info(f"Network: {NETWORK}")
    logger.info(f"Wallet: {WALLET_ADDRESS}")
    logger.info(f"Facilitator: {FACILITATOR_URL}")
    
    if not WALLET_ADDRESS:
        logger.error("FATAL: PAYMENT_ADDRESS environment variable is not set.")
    else:
        uvicorn.run(app, host="0.0.0.0", port=port)
