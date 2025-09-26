import os
import sys
import re
import httpx
import time
import hashlib
import asyncio
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

from uagents import Agent, Context, Model
import requests
from agent_wallet import AgentWallet

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
ONEINCH_PROXY_URL = os.getenv("1INCH_PROXY_URL")


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
# Agent Globals
# ────────────────────────────────────────────────────────────────────────────────

one_inch_client: Optional[OneInchPortfolioClient] = None
agent_wallet: Optional[AgentWallet] = None
active_copy_trades: Dict[str, Any] = {}
agent_messages: List[AgentMessage] = []
MAX_MESSAGES = 50

# Supported chains for 1inch Portfolio API
CHAIN_NAME_TO_ID = {
    "ethereum": 1, "eth": 1, "arbitrum": 42161, "arb": 42161,
    "bnb chain": 56, "bnb": 56, "bsc": 56, "binance smart chain": 56,
    "gnosis": 100, "optimism": 10, "polygon": 137, "matic": 137,
    "base": 8453, "zksync era": 324, "linea": 59144,
    "avalanche": 43114, "avax": 43114,
}

# ────────────────────────────────────────────────────────────────────────────────
# Agent Lifecycle & Endpoints
# ────────────────────────────────────────────────────────────────────────────────

@agent.on_event("startup")
async def startup(ctx: Context):
    global one_inch_client, agent_wallet
    ctx.logger.info("🌟 NakalTrade Agent Starting with Copy Trading")
    
    if not ASI_ONE_API_KEY:
        ctx.logger.warning("⚠️ ASI_ONE_API_KEY not found. Analysis will be limited.")
    else:
        ctx.logger.info("✅ ASI:One API key configured")
    
    if not os.getenv("PAYMENT_ADDRESS"):
        ctx.logger.warning("⚠️ PAYMENT_ADDRESS not found. x402 service may fail.")
        
    one_inch_client = OneInchPortfolioClient(ctx)
    
    ctx.logger.info("💰 Initializing agent wallet for copy trading...")
    agent_wallet = AgentWallet()
    agent_wallet.initialize()
    wallet_info = agent_wallet.get_wallet_info()
    ctx.logger.info(f"💳 Agent wallet ready: {wallet_info['address']}")
    ctx.logger.info("✨ Agent is ready!")

@agent.on_rest_post("/chat", ChatRequest, ChatResponse)
async def chat_endpoint(ctx: Context, req: ChatRequest) -> ChatResponse:
    ctx.logger.info(f"💬 Chat received: {req.message}")
    
    message = req.message.lower()
    response = ""

    # Command: analyze {address} on {chain}
    analysis_match = re.search(r"analyze\s+(0x[a-fA-F0-9]{40})", message)
    if analysis_match:
        response = await handle_analysis(ctx, req.message, analysis_match)

    # Command: copy_trade {token_symbol}
    elif message.startswith("copy_trade"):
        response = await handle_copy_trade_start(ctx, message)

    # Command: execute {payment_id}
    elif message.startswith("execute"):
        response = await handle_copy_trade_execute(ctx, message)
    
    # Command: wallet
    elif message == "wallet":
        response = handle_wallet_info()

    else:
        response = "Sorry, I didn't understand. Try 'analyze {address} on {chain}' or 'wallet'."

    # Store and return the response
    store_agent_message("NakalTrade", response)
    return ChatResponse(response=response)

@agent.on_rest_get("/agent_messages", AgentMessagesResponse)
async def get_agent_messages(ctx: Context) -> AgentMessagesResponse:
    return AgentMessagesResponse(messages=agent_messages)

@agent.on_rest_get("/health", ChatResponse)
async def health_check(ctx: Context) -> ChatResponse:
    return ChatResponse(response="NakalTrade agent is healthy!")

# ────────────────────────────────────────────────────────────────────────────────
# Command Handlers
# ────────────────────────────────────────────────────────────────────────────────

async def handle_analysis(ctx: Context, original_message: str, match: re.Match) -> str:
    wallet_address = match.group(1)
    chain_name = await parse_chain_with_gpt(original_message)
    
    if chain_name not in CHAIN_NAME_TO_ID:
        return f"Sorry, '{chain_name}' is not a supported chain."

    chain_id = CHAIN_NAME_TO_ID[chain_name]
    ctx.logger.info(f"📈 Analyzing {wallet_address} on {chain_name} (ID: {chain_id})")

    pnl_data, value_data, details_data, balance_data = await asyncio.gather(
        one_inch_client.get_erc20_pnl([wallet_address], chain_id),
        one_inch_client.get_current_value([wallet_address], chain_id),
        one_inch_client.get_token_details([wallet_address], chain_id),
        one_inch_client.get_token_balances([wallet_address], chain_id)
    )

    if any("error" in d for d in [pnl_data, value_data, details_data, balance_data]):
        return "❌ Error fetching portfolio data from 1inch. Please try again later."
    
    combined_data = { "pnl": pnl_data, "value": value_data, "details": details_data, "balances": balance_data }
    return await parse_pnl_with_gpt(wallet_address, chain_name, combined_data)


async def handle_copy_trade_start(ctx: Context, message: str) -> str:
    token_symbol_match = re.search(r"copy_trade\s+([a-zA-Z0-9]+)", message)
    if not token_symbol_match:
        return "Invalid format. Use `copy_trade {TOKEN_SYMBOL}`."

    token_symbol = token_symbol_match.group(1).upper()
    trade_details = f"1 of {token_symbol}" # Mock amount for now
    
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                "http://localhost:8402/payment/create",
                params={"item_name": trade_details, "price": 0.01}
            )
            if res.status_code != 200:
                raise Exception(f"Payment service returned status {res.status_code}")
            
            payment_data = res.json()
            payment_id = payment_data["payment_id"]
            
            active_copy_trades[payment_id] = {
                "token": token_symbol,
                "price": 0.01,
                "status": "awaiting_payment"
            }
            
            return f"""
            🚀 **Copy Trade Initiated via x402**

            **Trade:** {trade_details}
            **Service Fee:** $0.01 USDC
            **Payment ID:** `{payment_id}`

            To proceed, fund the agent's wallet and type:
            `execute {payment_id}`
            """
    except Exception as e:
        ctx.logger.error(f"Failed to create x402 payment request: {e}")
        return "❌ Could not initiate copy trade. The x402 service might be down."

async def handle_copy_trade_execute(ctx: Context, message: str) -> str:
    payment_id_match = re.search(r"execute\s+([a-zA-Z0-9]+)", message)
    if not payment_id_match:
        return "Invalid format. Use `execute {payment_id}`."
        
    payment_id = payment_id_match.group(1)
    if payment_id not in active_copy_trades:
        return f"❌ Payment ID `{payment_id}` not found or expired."

    trade = active_copy_trades[payment_id]
    if trade["status"] == "completed":
        return f"✅ This trade has already been executed."

    ctx.logger.info(f"🤖 Agent executing x402 payment for {payment_id}")
    
    try:
        result = agent_wallet.execute_payment(payment_id, trade["price"])
        if result and result.status_code == 200:
            trade["status"] = "completed"
            return f"✅ **Payment Sent!**\n\nCopy trade for **{trade['token']}** has been executed via x402."
        else:
            status_code = result.status_code if result else "unknown"
            error_text = result.text if result else "No response"
            return f"❌ Payment failed (status: {status_code}). Check agent wallet balance and x402 service logs.\nDetails: {error_text}"
    except Exception as e:
        ctx.logger.error(f"Payment execution error: {e}")
        return f"❌ An unexpected error occurred during payment execution: {e}"

def handle_wallet_info() -> str:
    wallet_info = agent_wallet.get_wallet_info()
    return f"""
    💰 **Agent Wallet Information**

    **Address:** `{wallet_info['address']}`
    **Network:** {wallet_info['network']}

    Fund this wallet with USDC on Polygon Amoy to enable copy trading.
    """

# ────────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ────────────────────────────────────────────────────────────────────────────────

def store_agent_message(agent_name: str, message: str):
    global agent_messages
    agent_messages.append(AgentMessage(agent_name=agent_name, message=message, timestamp=time.time()))
    if len(agent_messages) > MAX_MESSAGES:
        agent_messages = agent_messages[-MAX_MESSAGES:]

async def parse_chain_with_gpt(user_input: str) -> str:
    if not ASI_ONE_API_KEY: return "ethereum"
    supported_chains = list(CHAIN_NAME_TO_ID.keys())
    prompt = f"""From the user's request, identify the blockchain network. The request is: "{user_input}"
Choose ONLY from the following list: {supported_chains}. Default to "ethereum" if unsure. Return ONLY the chain name."""
    try:
        response = requests.post(ASI_ONE_URL, headers={"Authorization": f"Bearer {ASI_ONE_API_KEY}", "Content-Type": "application/json"},
                                 json={"model": "asi1-mini", "messages": [{"role": "user", "content": prompt}], "temperature": 0})
        response.raise_for_status()
        choice = response.json()['choices'][0]['message']['content'].strip().lower()
        return choice if choice in CHAIN_NAME_TO_ID else "ethereum"
    except Exception as e:
        print(f"Error parsing chain with LLM: {e}")
        chain_match = re.search(r"on\s+(\w+\s*\w*)", user_input, re.IGNORECASE)
        if chain_match:
            requested_chain = chain_match.group(1).lower().strip()
            if requested_chain in CHAIN_NAME_TO_ID:
                return requested_chain
        return "ethereum"

async def parse_pnl_with_gpt(wallet_address: str, chain_name: str, pnl_data: Dict[str, Any]) -> str:
    if not ASI_ONE_API_KEY:
        return "⚠️ ASI:One API key not configured. Cannot analyze data."

    # Find the top performing token to suggest for a copy trade
    top_performer_suggestion = ""
    try:
        # Check pnl data and ensure it's a list of dicts with 'pnl_usd'
        if 'pnl' in pnl_data and 'erc20' in pnl_data['pnl'] and isinstance(pnl_data['pnl']['erc20'], list):
            performers = [
                token for token in pnl_data['pnl']['erc20']
                if 'pnl_usd' in token and isinstance(token['pnl_usd'], (int, float))
                   and 'symbol' in token and token['symbol'].lower() not in ['usdc', 'usdt', 'dai']
            ]
            if performers:
                top_performer = max(performers, key=lambda x: x['pnl_usd'])
                if top_performer['pnl_usd'] > 0:
                    top_performer_suggestion = f"""
                    ---
                    💡 **Copy Trade Suggestion**
                    This wallet's top performer is **{top_performer['symbol']}**.
                    To copy this trade, type: `copy_trade {top_performer['symbol']}`
                    """
    except Exception as e:
        print(f"Could not determine top performer: {e}")


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

    1.  **Source of Truth:** Use `balances` for current holdings and `pnl` for historical performance.
    2.  **Zero-Balance Rule:** If a token has a zero balance, it's a "Past Trade." Do not list it under current holdings.
    3.  **Explain PnL:** Start with total portfolio value and PnL. Explain that PnL is a mix of realized (sold) and unrealized (held) gains.
    4.  **Exclude Stablecoins:** Do NOT list USDC, USDT, DAI as top performers or underperformers.
    5.  **Structure:** Provide "Top Performers (Currently Held)," "Top Underperformers (Currently Held)," and "Successful Past Trades (Realized Gains)."
    6.  **Actionable Insights:** Base your insights on the most significant trades.

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
    *   This wallet's primary holding is **ETH**.

    Provide your analysis based on the data.
    """
    try:
        response = requests.post(ASI_ONE_URL, headers={"Authorization": f"Bearer {ASI_ONE_API_KEY}", "Content-Type": "application/json"},
                                 json={"model": "asi1-mini", "messages": [{"role": "user", "content": parse_prompt}], "temperature": 0.2})
        response.raise_for_status()
        analysis_result = response.json()['choices'][0]['message']['content']
        return analysis_result + top_performer_suggestion
    except Exception as e:
        return f"❌ Error analyzing data with LLM: {e}"


if __name__ == "__main__":
    print("""
🌟 NakalTrade Agent with x402 Copy Trading
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Analyze wallets: "analyze 0x... on eth"
• Get wallet info: "wallet"
• Initiate a trade: "copy_trade {TOKEN_SYMBOL}"
• Execute payment: "execute {payment_id}"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """)
    # Run the x402 service as a separate process
    import subprocess
    service_process = subprocess.Popen([sys.executable, "x402_service.py"])
    print(f"🚀 Started x402 service with PID: {service_process.pid}")
    
    agent.run()

    # Clean up the service process on agent shutdown
    service_process.terminate()
    service_process.wait()
