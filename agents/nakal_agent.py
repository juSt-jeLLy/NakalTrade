import os
import sys
import re
import httpx
import time
import asyncio
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

from uagents import Agent, Context, Model
import requests

# Load environment variables
load_dotenv()

# Agent configuration
agent = Agent(
    name="nakal_trade_agent",
    seed="nakal_trade_agent_seed_2025",
    port=int(os.getenv("PORT", 8100)),
    endpoint=[f"http://localhost:{os.getenv('PORT', 8100)}/submit"],
)

# ASI:One Mini configuration
ASI_ONE_API_KEY = os.getenv("ASI_ONE_API_KEY")
ASI_ONE_URL = "https://api.asi1.ai/v1/chat/completions"
ONEINCH_PROXY_URL = os.getenv("1INCH_PROXY_URL", )


# Simple Models
class ChatRequest(Model):
    message: str

class ChatResponse(Model):
    response: str

class AgentMessage(Model):
    agent_name: str
    message: str
    timestamp: float

class AgentMessagesResponse(Model):
    messages: List[AgentMessage]

class OneInchPortfolioClient:
    """Client for interacting with the 1inch Portfolio API via a proxy."""
    def __init__(self, ctx: Context):
        self._ctx = ctx
        # The user-provided proxy URL
        self.portfolio_base_url = f"{ONEINCH_PROXY_URL}/portfolio/portfolio/v4"
        self.balance_base_url = f"{ONEINCH_PROXY_URL}/balance/v1.2"
        self._ctx.logger.info(f"Using 1inch proxy for Portfolio: {self.portfolio_base_url}")
        self._ctx.logger.info(f"Using 1inch proxy for Balance: {self.balance_base_url}")

    async def _make_request(self, base_url: str, endpoint: str, addresses: List[str], chain_id: int) -> Dict[str, Any]:
        """Helper function to make requests to the 1inch API proxy."""
        headers = {"accept": "application/json"}
        # The balance API uses a different path structure for the address
        if "balance" in base_url:
            address_path = addresses[0] # Assumes single address for balance check
            url = f"{base_url}/{chain_id}/balances/{address_path}"
            params = {}
        else:
            params = {"addresses": ",".join(addresses), "chain_id": chain_id}
            url = f"{base_url}{endpoint}"
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                self._ctx.logger.info(f"Querying 1inch endpoint {url}")
                resp = await client.get(url, headers=headers, params=params)
                
                if resp.status_code == 200:
                    return resp.json()
                else:
                    error_msg = f"1inch API proxy error: {resp.status_code} - {resp.text}"
                    self._ctx.logger.error(error_msg)
                    return {"error": error_msg}
        except Exception as e:
            self._ctx.logger.error(f"Error calling 1inch proxy endpoint {url}: {e}")
            return {"error": str(e)}

    async def get_erc20_pnl(self, addresses: List[str], chain_id: int) -> Dict[str, Any]:
        return await self._make_request(self.portfolio_base_url, "/overview/erc20/profit_and_loss", addresses, chain_id)

    async def get_current_value(self, addresses: List[str], chain_id: int) -> Dict[str, Any]:
        return await self._make_request(self.portfolio_base_url, "/overview/erc20/current_value", addresses, chain_id)

    async def get_token_details(self, addresses: List[str], chain_id: int) -> Dict[str, Any]:
        return await self._make_request(self.portfolio_base_url, "/overview/erc20/details", addresses, chain_id)

    async def get_token_balances(self, addresses: List[str], chain_id: int) -> Dict[str, Any]:
        return await self._make_request(self.balance_base_url, "", addresses, chain_id)

# ────────────────────────────────────────────────────────────────────────────────
# Agent Lifecycle
# ────────────────────────────────────────────────────────────────────────────────

one_inch_client: Optional[OneInchPortfolioClient] = None

# Store recent agent messages (keep last 50)
agent_messages: List[AgentMessage] = []
MAX_MESSAGES = 50

# Supported chains for 1inch Portfolio API
CHAIN_NAME_TO_ID = {
    "ethereum": 1,
    "eth": 1,
    "arbitrum": 42161,
    "arb": 42161,
    "bnb chain": 56,
    "bnb": 56,
    "bsc": 56,
    "binance smart chain": 56,
    "gnosis": 100,
    "optimism": 10,
    "polygon": 137,
    "matic": 137,
    "base": 8453,
    "zksync era": 324,
    "linea": 59144,
    "avalanche": 43114,
    "avax": 43114,
}

@agent.on_event("startup")
async def startup(ctx: Context):
    global one_inch_client
    ctx.logger.info("🌟 NakalTrade Agent Starting")
    ctx.logger.info(f"📍 Address: {agent.address}")
    ctx.logger.info("🤖 Using 1inch API for Portfolio Analysis")
    
    # Check if API key is configured
    if not ASI_ONE_API_KEY:
        ctx.logger.warning("⚠️ ASI_ONE_API_KEY not found in environment. Please set it in your .env file.")
    else:
        ctx.logger.info("✅ ASI:One API key configured")
    
    one_inch_client = OneInchPortfolioClient(ctx)
    ctx.logger.info("✨ Ready!")

@agent.on_rest_post("/chat", ChatRequest, ChatResponse)
async def chat_endpoint(ctx: Context, req: ChatRequest) -> ChatResponse:
    """Chat endpoint that uses 1inch API for portfolio analysis"""
    global agent_messages
    ctx.logger.info(f"💬 Chat: {req.message}")
    
    # Handle analysis requests, e.g., "analyze 0x... on polygon"
    analysis_match = re.search(r"analyze\s+(0x[a-fA-F0-9]{40})", req.message, re.IGNORECASE)
    if analysis_match:
        wallet_address = analysis_match.group(1)
        
        # Use LLM to intelligently parse the chain from the user's message
        chain_name = await parse_chain_with_gpt(req.message)
        
        if chain_name not in CHAIN_NAME_TO_ID:
            # Fallback or error if the LLM returns an unsupported chain
            response = f"Sorry, I don't support the '{chain_name}' chain. Supported chains are: {', '.join(CHAIN_NAME_TO_ID.keys())}"
            return ChatResponse(response=response)

        chain_id = CHAIN_NAME_TO_ID[chain_name]
        ctx.logger.info(f"📈 Initiating portfolio analysis for {wallet_address} on {chain_name} (ID: {chain_id})")

        # Concurrently fetch all required data points from the 1inch API
        pnl_data, value_data, details_data, balance_data = await asyncio.gather(
            one_inch_client.get_erc20_pnl(addresses=[wallet_address], chain_id=chain_id),
            one_inch_client.get_current_value(addresses=[wallet_address], chain_id=chain_id),
            one_inch_client.get_token_details(addresses=[wallet_address], chain_id=chain_id),
            one_inch_client.get_token_balances(addresses=[wallet_address], chain_id=chain_id)
        )

        # Check for errors in any of the API responses
        if "error" in pnl_data or "error" in value_data or "error" in details_data or "error" in balance_data:
            response = f"❌ Error fetching portfolio data from 1inch. Please try again later."
            ctx.logger.error(f"1inch API Errors: PnL({pnl_data.get('error')}), Value({value_data.get('error')}), Details({details_data.get('error')}), Balance({balance_data.get('error')})")
        else:
            # Combine data and use LLM to parse and summarize the results
            combined_data = {
                "pnl": pnl_data,
                "value": value_data,
                "details": details_data,
                "balances": balance_data,
            }
            response = await parse_pnl_with_gpt(wallet_address, chain_name, combined_data)

        # Store and return response
        agent_msg = AgentMessage(agent_name="NakalTrade", message=response, timestamp=time.time())
        agent_messages.append(agent_msg)
        if len(agent_messages) > MAX_MESSAGES:
            agent_messages = agent_messages[-MAX_MESSAGES:]
        return ChatResponse(response=response)

    # Fallback for unhandled messages
    response = "Sorry, I can only analyze wallets (e.g., 'analyze 0x... on eth')."
    
    # Store agent's response
    agent_msg = AgentMessage(
        agent_name="NakalTrade",
        message=response,
        timestamp=time.time()
    )
    agent_messages.append(agent_msg)
    
    # Keep only last MAX_MESSAGES
    if len(agent_messages) > MAX_MESSAGES:
        agent_messages = agent_messages[-MAX_MESSAGES:]
    
    return ChatResponse(response=response)

@agent.on_rest_get("/agent_messages", AgentMessagesResponse)
async def get_agent_messages(ctx: Context) -> AgentMessagesResponse:
    """Get recent agent messages for frontend polling"""
    global agent_messages
    return AgentMessagesResponse(messages=agent_messages)

@agent.on_rest_get("/health", ChatResponse)
async def health_check(ctx: Context) -> ChatResponse:
    ctx.logger.info("Health check requested")
    return ChatResponse(response="NakalTrade agent is healthy!")


async def parse_chain_with_gpt(user_input: str) -> str:
    """Use ASI:One Mini to parse the blockchain name from user input."""
    if not ASI_ONE_API_KEY:
        # Default to ethereum if key is missing
        return "ethereum"

    supported_chains = list(CHAIN_NAME_TO_ID.keys())

    prompt = f"""
From the user's request, identify the blockchain network.
The request is: "{user_input}"

Choose ONLY from the following list of supported chains: {supported_chains}

- Your response MUST be a single word or phrase from the list.
- If no specific chain is mentioned, you MUST default to "ethereum".
- For example, if the user says "on bnb" or "on bsc", you should return "bsc".
- If the user says "on polygon network", you should return "polygon".

Return ONLY the chain name.
"""
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {ASI_ONE_API_KEY}"
        }
        data = {
            "model": "asi1-mini",
            "messages": [
                {"role": "system", "content": f"You are an expert at identifying blockchain names from text. Your response must be one of {supported_chains}."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0,
        }
        response = requests.post(ASI_ONE_URL, headers=headers, json=data)
        response.raise_for_status()
        response_json = response.json()
        
        if 'choices' in response_json and response_json['choices']:
            chain = response_json['choices'][0]['message']['content'].strip().lower()
            # Ensure the returned chain is one of the keys we support
            if chain in CHAIN_NAME_TO_ID:
                return chain
    except Exception as e:
        print(f"Error parsing chain with LLM: {e}")

    # Fallback to simple regex if LLM fails
    chain_match = re.search(r"on\s+(\w+\s*\w*)", user_input, re.IGNORECASE)
    if chain_match:
        requested_chain = chain_match.group(1).lower().strip()
        if requested_chain in CHAIN_NAME_TO_ID:
            return requested_chain

    return "ethereum" # Default fallback


async def parse_pnl_with_gpt(wallet_address: str, chain_name: str, pnl_data: Dict[str, Any]) -> str:
    """Use ASI:One Mini to parse and summarize 1inch PnL data."""
    if not ASI_ONE_API_KEY:
        return "⚠️ ASI:One API key not configured. Cannot analyze data."

    # Truncate the data if it's too large to fit in the prompt
    pnl_json_str = str(pnl_data)
    if len(pnl_json_str) > 12000:
        pnl_json_str = pnl_json_str[:12000] + "... (data truncated)"

    parse_prompt = f"""
You are an expert DeFi portfolio analyst. Your task is to interpret the combined data from the 1inch Portfolio and Balance APIs for a user's wallet and provide a clear, concise, and actionable summary.

USER'S WALLET: {wallet_address}
CHAIN: {chain_name}

RAW 1inch PORTFOLIO & BALANCE DATA (JSON):
{pnl_json_str}

**CRITICAL ANALYSIS INSTRUCTIONS:**

1.  **Source of Truth for Holdings:** The `balances` data is the definitive source for what the wallet *currently holds*.
2.  **The Zero-Balance Exclusion Rule:** If a token has a zero or negligible balance in the `balances` data, it **MUST ONLY** be considered for the "Past Trades" section. It **MUST BE EXCLUDED** from the "Top Performers (Currently Held)" and "Top Underperformers (Currently Held)" lists, regardless of its PnL.
3.  **Explain PnL Composition:** Start with the total portfolio value and total PnL. **Crucially, you must explain that the total PnL is the sum of unrealized gains (on assets still held) and realized gains (from assets already sold).**
4.  **Special Handling for Stablecoins:**
    *   Identify common stablecoins (USDC, USDT, DAI).
    *   **NEVER** list stablecoins under "Top Performers," "Underperformers," or "Past Trades" unless their ROI is abnormally large (e.g., > 10% or < -10%), which would indicate a rare de-pegging event. Normal fluctuations are not trades.
    *   Instead, you can add a "Notes" section at the end to mention significant stablecoin activity, e.g., "*Note: The wallet has actively used USDC, likely for gas fees or as a temporary store of value between trades.*"
5.  **Distinguish Realized vs. Unrealized Gains:**
    *   If a non-stablecoin token appears in `pnl` with a profit but has a zero/non-existent entry in `balances`, classify it as a **"Successful Past Trade"** (Realized Gain).
    *   Tokens with PnL that are also present in `balances` represent **unrealized gains/losses**.
6.  **Top Movers (Unrealized):** Identify the top 3 best-performing and top 3 worst-performing **non-stablecoin** tokens that are **currently held**.
7.  **Past Trades (Realized):** Separately list up to 3 notable "Past Trades" of **non-stablecoin** assets.
8.  **Detailed Breakdown:** For each token listed, provide: Token `symbol`, `pnl_usd`, `roi`, current `value_usd`, and current `Holding` amount.
9.  **ETH vs. WETH Nuance:** If both ETH and WETH appear, add a note explaining that WETH is "Wrapped ETH" used for DeFi.
10. **Actionable Insights:** Base your insights on the most significant trades (realized or unrealized). Explain *why* a trade might be worth copying.

**EXAMPLE OUTPUT:**
**Portfolio Analysis for `0x...` on Ethereum**

This portfolio is currently valued at **$19.52**, with a total historical profit of **+$147.90 (+0.23%)**.
This profit is a combination of unrealized gains on current holdings and realized gains from past trades.

📈 **Top Performers (Currently Held):**
*   **ETH:** +$103.95 (+0.77%) | Value: $19.52 | Holding: 0.00485 ETH

📉 **Top Underperformers (Currently Held):**
*   *No significant underperforming non-stablecoin assets currently held.*

🔄 **Successful Past Trades (Realized Gains):**
*   *No significant past trades of non-stablecoin assets detected.*

💡 **Trade Insights:**
*   This wallet's primary holding is **ETH**, which is performing modestly. To replicate this, one could consider a similar small ETH position.
*   The majority of the portfolio's historical profit (`+$147.90`) comes from a combination of the current ETH position and past transactions.

*(Note: The wallet successfully realized gains from USDC transactions, suggesting active use of stablecoins, likely for fee coverage or liquidity purposes.)*

OUTPUT:
"""
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {ASI_ONE_API_KEY}"
        }
        data = {
            "model": "asi1-mini",
            "messages": [
                {"role": "system", "content": "You are a helpful DeFi analyst that summarizes wallet performance."},
                {"role": "user", "content": parse_prompt}
            ]
        }
        response = requests.post(ASI_ONE_URL, headers=headers, json=data)
        response.raise_for_status()
        response_json = response.json()
        
        if 'choices' in response_json and response_json['choices']:
            return response_json['choices'][0]['message']['content']
        else:
            return "❌ Could not get analysis from LLM."
    except Exception as e:
        return f"❌ Error analyzing data with LLM: {e}"


if __name__ == "__main__":
    print("""
🌟 NakalTrade Agent - 1inch Powered Portfolio Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Natural language portfolio analysis via 1inch API
• Example: "analyze 0xd8da6bf26964af9d7echancho.eth on eth"
• REST API: POST /chat {"message": "your question"}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """)
    agent.run()
