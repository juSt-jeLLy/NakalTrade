"""
Agent Wallet Manager for NakalTrade
Handles wallet creation and x402 payments using eth-account
"""

import os
import json
import asyncio
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

from eth_account import Account
from x402.clients.requests import x402_requests

class AgentWallet:
    """
    Agent wallet that uses eth-account to handle x402 payments automatically
    """
    
    def __init__(self):
        self.account = None
        self.session = None
        self.wallet_address = None
        self.wallet_data_file = "nakal_agent_wallet.json"
        
    def initialize(self):
        """Initialize wallet using eth-account"""
        self._initialize_eth_account()
        
        if self.account:
            self.session = x402_requests(self.account)
            print(f"✅ x402 session created for wallet: {self.wallet_address}")
    
    def _initialize_eth_account(self):
        """Initialize using eth-account (with private key)"""
        private_key = os.getenv("AGENT_PRIVATE_KEY")

        if private_key:
            self.account = Account.from_key(private_key)
            self.wallet_address = self.account.address
            print(f"🔑 Loaded agent wallet from AGENT_PRIVATE_KEY: {self.wallet_address}")
        else:
            # Generate new wallet if no private key is provided
            self.account = Account.create()
            self.wallet_address = self.account.address
            
            print("⚠️ AGENT_PRIVATE_KEY not found in .env. A new wallet has been generated.")
            print(f"🔐 Generated new wallet address: {self.wallet_address}")
            print(f"‼️ IMPORTANT: Save this private key to your .env file as AGENT_PRIVATE_KEY to reuse the wallet:")
            print(self.account.key.hex())
            print(f"💰 Fund this wallet with USDC on Polygon Amoy to enable copy trading.")
    
    def execute_payment(self, payment_id: str, amount: float = 0.01):
        """
        Execute payment using x402 protocol
        """
        if not self.session:
            if not self.account:
                print("❌ No wallet account available for payment.")
                return None
            self.session = x402_requests(self.account)
        
        url = f"http://localhost:8402/copytrade/{payment_id}"
        
        print(f"💸 Executing x402 payment for copy trade...")
        print(f"   Payment ID: {payment_id}")
        print(f"   Amount: ${amount}")
        print(f"   From wallet: {self.wallet_address}")
        
        try:
            response = self.session.post(url)
            
            if response.status_code == 200:
                print(f"✅ Payment successful!")
            else:
                print(f"❌ Payment failed: {response.status_code} - {response.text}")
            return response
                
        except Exception as e:
            print(f"❌ Payment execution error: {e}")
            return None
    
    def get_address(self) -> str:
        """Get wallet address for funding"""
        return self.wallet_address
    
    def get_wallet_info(self) -> dict:
        """Get wallet information"""
        return {
            "address": self.wallet_address,
            "type": "eth-account",
            "network": "polygon-amoy",
            "ready": self.account is not None
        }
