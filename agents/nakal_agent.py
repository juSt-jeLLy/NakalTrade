import os
import sys
import re
import httpx
import time
import json
import asyncio
import hashlib
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

from uagents import Agent, Context, Model
import requests
from web3 import Web3, HTTPProvider
# The polygonscan library is not working, so we will use httpx for direct API calls.
# from polygonscan import PolygonScan

# Load environment variables
load_dotenv()

# Agent configuration
agent = Agent(
    name="nakal_trade_agent",
    seed="nakal_trade_agent_seed_2025",
    port=int(os.getenv("PORT", 8100)),
    endpoint=[f"http://localhost:{os.getenv('PORT', 8100)}/submit"],
)

# --- Constants ---
ASI_ONE_API_KEY = os.getenv("ASI_ONE_API_KEY")
ASI_ONE_URL = "https://api.asi1.ai/v1/chat/completions"
ONEINCH_PROXY_URL = os.getenv("1INCH_PROXY_URL")
PAYMENT_ADDRESS = os.getenv("PAYMENT_ADDRESS")
AGENT_PRIVATE_KEY = os.getenv("AGENT_PRIVATE_KEY")
POLYGONSCAN_API_KEY = os.getenv("POLYGONSCAN_API_KEY")
AMOY_USDC_CONTRACT = "0x41E94Eb019C0762f9Bfcf9Fb1E58725BfB0e7582"
MOCK_TOKEN_ADDRESS = "0x33432627F302E9C6a3f62ACf7CB581AD57E109dB" # CORRECTED Mock Token Address

# --- Models ---
class ChatRequest(Model): message: str
class ChatResponse(Model): response: str
class AgentMessage(Model): agent_name: str; message: str; timestamp: float
class AgentMessagesResponse(Model): messages: List[AgentMessage]

# --- Globals ---
one_inch_client: Optional[any] = None
active_copy_trades: Dict[str, Any] = {}
agent_messages: List[AgentMessage] = []
MAX_MESSAGES = 50
CHAIN_NAME_TO_ID = {
    "ethereum": 1, "eth": 1, "arbitrum": 42161, "arb": 42161,
    "bnb chain": 56, "bnb": 56, "bsc": 56, "binance smart chain": 56,
    "gnosis": 100, "optimism": 10, "polygon": 137, "matic": 137,
    "base": 8453, "zksync era": 324, "linea": 59144,
    "avalanche": 43114, "avax": 43114,
}

# --- Agent Logic ---
@agent.on_event("startup")
async def startup(ctx: Context):
    global one_inch_client
    ctx.logger.info("🌟 NakalTrade Agent Starting with Automated Payment Detection")
    one_inch_client = OneInchPortfolioClient(ctx)
    if not all([PAYMENT_ADDRESS, AGENT_PRIVATE_KEY, POLYGONSCAN_API_KEY]):
        ctx.logger.error("FATAL: Missing PAYMENT_ADDRESS, AGENT_PRIVATE_KEY, or POLYGONSCAN_API_KEY in .env")
    else:
        ctx.logger.info("✅ All configurations for copy trading are set.")
    ctx.logger.info("✨ Agent is ready!")

@agent.on_rest_post("/chat", ChatRequest, ChatResponse)
async def chat_endpoint(ctx: Context, req: ChatRequest) -> ChatResponse:
    message = req.message.lower()
    
    analysis_match = re.search(r"analyze\s+(0x[a-fA-F0-9]{40})", message)
    copy_trade_match = re.search(r"copytrade\s+([a-zA-Z0-9]+)\s+with address\s+(0x[a-fA-F0-9]{40})", message)

    if analysis_match:
        response = await handle_analysis(ctx, req.message, analysis_match)
    elif copy_trade_match:
        response = await handle_copy_trade(ctx, copy_trade_match)
    else:
        response = "Sorry, I didn't understand. Try 'analyze {address} on {chain}' or 'copytrade {TOKEN} with address {YOUR_ADDRESS}'."

    store_agent_message("NakalTrade", response)
    return ChatResponse(response=response)

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


async def handle_copy_trade(ctx: Context, match: re.Match) -> str:
    token_symbol, user_wallet = match.groups()
    payment_id = hashlib.sha256(f"{token_symbol}{user_wallet}{time.time()}".encode()).hexdigest()[:10]
    
    active_copy_trades[payment_id] = {
        "token": token_symbol.upper(),
        "user_wallet": user_wallet,
        "status": "watching"
    }
    
    asyncio.create_task(watch_for_payment(ctx, payment_id))

    return f"""🚀 **Copy Trade Initiated**
**Trade:** 1 {token_symbol.upper()}
**Service Fee:** 0.01 USDC
**Payment ID:** `{payment_id}`

I am now watching for a payment of **0.01 USDC** from your address `{user_wallet}` to my address `{PAYMENT_ADDRESS}` on **Polygon Amoy**. Please send the funds to proceed. This request will expire in 5 minutes."""

async def watch_for_payment(ctx: Context, payment_id: str):
    trade = active_copy_trades.get(payment_id)
    if not trade: return

    ctx.logger.info(f"👀 Watching for payment for ID {payment_id} from {trade['user_wallet']}")
    start_time = time.time()
    
    while time.time() - start_time < 300: # 5 minute timeout
        try:
            # CORRECTED: Using the Etherscan V2 universal API with the correct chainid for Amoy.
            api_url = (
                f"https://api.etherscan.io/v2/api"
                f"?chainid=80002"
                f"&module=account"
                f"&action=tokentx"
                f"&contractaddress={AMOY_USDC_CONTRACT}"
                f"&address={PAYMENT_ADDRESS}"
                f"&page=1"
                f"&offset=10"
                f"&startblock=0"
                f"&endblock=99999999"
                f"&sort=desc"
                f"&apikey={POLYGONSCAN_API_KEY}"
            )

            async with httpx.AsyncClient() as client:
                response = await client.get(api_url)
                response.raise_for_status()
                data = response.json()

            if data["status"] == "1" and data["result"]:
                for tx in data["result"]:
                    if (tx['to'].lower() == PAYMENT_ADDRESS.lower() and
                        tx['from'].lower() == trade['user_wallet'].lower() and
                        int(tx['value']) == 10000): # 0.01 USDC (6 decimals)
                        
                        ctx.logger.info(f"✅ Payment DETECTED for {payment_id} in tx {tx['hash']}")
                        trade['status'] = "completed"
                        mock_tx_hash = execute_mock_token_transfer(ctx, trade['user_wallet'], trade['token'])
                        confirmation_message = f"✅ **Payment Received!**\nYour fee for trade `{payment_id}` was confirmed in tx `{tx['hash'][:10]}...`.\nI have sent you 1 mock {trade['token']} token. Tx: `{mock_tx_hash}`"
                        store_agent_message("NakalTrade", confirmation_message)
                        return
                        
        except Exception as e:
            ctx.logger.error(f"Error while watching for payment {payment_id}: {e}")
        
        await asyncio.sleep(15)

    if trade.get('status') == "watching":
        ctx.logger.info(f"⌛ Payment request {payment_id} expired.")
        store_agent_message("NakalTrade", f"Your copy trade request `{payment_id}` has expired.")
        del active_copy_trades[payment_id]

def execute_mock_token_transfer(ctx: Context, user_wallet: str, token_symbol: str) -> str:
    try:
        w3 = Web3(HTTPProvider("https://rpc-amoy.polygon.technology"))
        mock_erc20_abi = json.loads('[{"constant":false,"inputs":[{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"type":"function"}]')
        token_contract = w3.eth.contract(address=w3.to_checksum_address(MOCK_TOKEN_ADDRESS), abi=mock_erc20_abi)
        agent_account = w3.eth.account.from_key(AGENT_PRIVATE_KEY)
        
        tx = token_contract.functions.transfer(
            w3.to_checksum_address(user_wallet), w3.to_wei(1, 'ether')
        ).build_transaction({
            'chainId': 80002, 'gas': 70000, 'gasPrice': w3.eth.gas_price,
            'nonce': w3.eth.get_transaction_count(agent_account.address),
        })
        
        # Sign and send the transaction
        signed_tx = w3.eth.account.sign_transaction(tx, private_key=AGENT_PRIVATE_KEY)
        # CORRECTED: Used .raw_transaction as per the official web3.py v6 documentation.
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        ctx.logger.info(f"Mock token transfer sent: {tx_hash.hex()}")
        return tx_hash.hex()
    except Exception as e:
        ctx.logger.error(f"Failed to execute mock trade: {e}")
        return f"Failed to send mock token: {e}"

def store_agent_message(agent_name: str, message: str):
    global agent_messages
    agent_messages.append(AgentMessage(agent_name=agent_name, message=message, timestamp=time.time()))
    if len(agent_messages) > MAX_MESSAGES:
        agent_messages = agent_messages[-MAX_MESSAGES:]

class OneInchPortfolioClient:
    """Client for interacting with the 1inch Portfolio API via a proxy."""
    def __init__(self, ctx: Context):
        self._ctx = ctx
        self.portfolio_base_url = f"{ONEINCH_PROXY_URL}/portfolio/portfolio/v4"
        self.balance_base_url = f"{ONEINCH_PROXY_URL}/balance/v1.2"
        self._ctx.logger.info(f"Using 1inch proxy for Portfolio: {self.portfolio_base_url}")
        self._ctx.logger.info(f"Using 1inch proxy for Balance: {self.balance_base_url}")

    async def _make_request(self, base_url: str, endpoint: str, addresses: List[str], chain_id: int) -> Dict[str, Any]:
        headers = {"accept": "application/json"}
        if "balance" in base_url:
            address_path = addresses[0]
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

    top_performer_suggestion = ""
    try:
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
                    To copy this trade, type: `copytrade {top_performer['symbol']} with address YOUR_WALLET_ADDRESS`
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


# Required endpoints for frontend polling
@agent.on_rest_get("/agent_messages", AgentMessagesResponse)
async def get_agent_messages(ctx: Context) -> AgentMessagesResponse:
    return AgentMessagesResponse(messages=agent_messages)
@agent.on_rest_get("/health", ChatResponse)
async def health_check(ctx: Context) -> ChatResponse:
    return ChatResponse(response="NakalTrade agent is healthy!")

if __name__ == "__main__":
    print("🌟 NakalTrade Agent with Automated Payment Detection\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    agent.run()
