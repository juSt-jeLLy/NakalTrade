import os
import sys
import re
from dotenv import load_dotenv
from uagents import Agent, Context, Model
from hyperon import MeTTa, S, E, ExpressionAtom
from typing import Dict, Any

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import metta_helpers

load_dotenv()

agent = Agent(
    name="nakal_metta_agent",
    seed="nakal_metta_agent_seed_2025",
    port=8234,
    endpoint=[f"http://localhost:8234/submit"],
    mailbox=True,
)

class NakalMettaQueryRequest(Model):
    query: str
    conversation_id: str

class NakalMettaQueryResponse(Model):
    intent: str | None
    entities: Dict[str, Any]
    conversation_id: str

metta = MeTTa()

def initialize_knowledge_graph():
    """Initializes the MeTTa knowledge graph with trading bot commands, synonyms, and entities."""
    
    # Action Synonyms -> Intent
    metta.run('''
        (= (synonym analyze) analyze-wallet)
        (= (synonym check) analyze-wallet)
        (= (synonym inspect) analyze-wallet)
        (= (synonym "look at") analyze-wallet)
        (= (synonym pnl) analyze-wallet)
        (= (synonym analyse) analyze-wallet)

        (= (synonym copytrade) copy-trade)
        (= (synonym copy) copy-trade)
        (= (synonym mimic) copy-trade)
        (= (synonym follow) copy-trade)
        (= (synonym trade) copy-trade)
    ''')

    # Known Chains
    chains = [
        "ethereum", "eth", "arbitrum", "arb", "bnb chain", "bnb", "bsc",
        "binance smart chain", "gnosis", "optimism", "polygon", "matic",
        "base", "zksync era", "linea", "avalanche", "avax"
    ]
    for chain in chains:
        # Use metta.run to let the parser handle multi-word strings correctly
        if ' ' in chain:
            metta.run(f'(= (is-chain "{chain}") True)')
        else:
            metta.run(f'(= (is-chain {chain}) True)')


@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info("NakalTrade MeTTa Agent starting...")
    initialize_knowledge_graph()
    ctx.logger.info("Knowledge graph initialized.")

def parse_query(query: str) -> tuple[str | None, Dict[str, Any]]:
    """Parses a natural language query into an intent and a set of entities using MeTTa."""
    
    # Tokenize by address pattern or words
    tokens = re.findall(r'0x[a-fA-F0-9]{40}|\w+', query.lower())

    intent = None
    entities = {}

    # 1. Identify Intent from the first matching synonym
    for i, token in enumerate(tokens):
        # Handle multi-word synonyms like "look at"
        phrase_2_words = ' '.join(tokens[i:i+2])
        
        # Check 2-word phrase first
        result_2 = metta.run(f'!(match &self (synonym "{phrase_2_words}" $intent) $intent)')
        if result_2 and result_2 != [[]]:
            intent = str(result_2[0][0])
            break

        # Check 1-word token
        result_1 = metta.run(f'!(match &self (synonym {token} $intent) $intent)')
        if result_1 and result_1 != [[]]:
            intent = str(result_1[0][0])
            break
            
    if not intent:
        return (None, {})

    # 2. Extract Entities
    i = 0
    while i < len(tokens):
        token = tokens[i]
        
        # Check for address, potentially preceded by "my address"
        is_addr_result = metta.run(f'!(py-atom metta_helpers.is_wallet_address "{token}")')
        if is_addr_result and str(is_addr_result[0][0]) == 'True':
            # Check if the preceding tokens are "my address"
            if i > 1 and tokens[i-2] == "my" and tokens[i-1] == "address":
                 entities['user_wallet'] = token
            elif 'address' not in entities: # First address is likely the one to analyze
                entities['address'] = token
            else: # Subsequent addresses might be user wallets for copy trading
                entities['user_wallet'] = token
            i += 1
            continue
            
        # Check for multi-word chains (longest match first)
        matched_chain = None
        for length in range(3, 0, -1): # Check for 3, 2, then 1-word chains
            if i + length <= len(tokens):
                phrase = " ".join(tokens[i:i+length])
                
                # Query must use quotes for multi-word symbols, but not for single words
                query_phrase = f'"{phrase}"' if length > 1 else phrase
                
                is_chain_result = metta.run(f'!(match &self (is-chain {query_phrase}) True)')
                
                if is_chain_result and is_chain_result != [[]]:
                    matched_chain = phrase
                    break # Found longest possible match
        
        if matched_chain:
            entities['chain'] = matched_chain
            i += len(matched_chain.split())
            continue

        # Check for volume (e.g., "volume 100")
        if token == "volume" and i + 1 < len(tokens):
            volume_candidate = tokens[i+1]
            is_num_result = metta.run(f'!(py-atom metta_helpers.is_number "{volume_candidate}")')
            if is_num_result and str(is_num_result[0][0]) == 'True':
                entities['volume'] = float(volume_candidate)
                i += 2
                continue

        # Check for token symbol in copy-trade
        if intent == 'copy-trade' and token not in ['copytrade', 'copy', 'mimic', 'follow', 'with', 'address', 'volume', 'usd']:
            # A simple heuristic: the first non-keyword after the intent is the token
            if 'token_symbol' not in entities:
                 entities['token_symbol'] = token.upper()

        i += 1
        
    return (intent, entities)


@agent.on_message(model=NakalMettaQueryRequest)
async def handle_query(ctx: Context, sender: str, msg: NakalMettaQueryRequest):
    ctx.logger.info(f"Received query from {sender}: {msg.query}")
    intent, entities = parse_query(msg.query)
    response = NakalMettaQueryResponse(
        intent=intent,
        entities=entities,
        conversation_id=msg.conversation_id
    )
    ctx.logger.info(f"Parsed response: Intent={response.intent}, Entities={response.entities}")
    await ctx.send(sender, response)

if __name__ == "__main__":
    print("Starting NakalTrade MeTTa Agent...")
    agent.run()
