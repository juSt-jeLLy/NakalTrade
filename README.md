# NakalTrade - AI-Powered Copy Trading Platform

NakalTrade is an innovative copy trading platform that leverages AI agents to analyze successful traders' wallets and provide intelligent trading recommendations. The platform combines wallet analysis, AI-powered insights, and seamless cross-chain trading execution through an agentic payment flow.

## 🎯 Project Overview

NakalTrade revolutionizes copy trading by introducing a multi-agent system that not only tracks successful traders but also provides specialized analysis and automated execution. Users can input any public wallet address from Twitter-famous traders, and our AI agents will analyze their trading history, provide specialized insights, and execute trades on behalf of the user.

### Key Features

- **Wallet Analysis**: Real-time tracking and historical analysis of any public wallet address
- **Multi-Agent Intelligence**: Specialized AI agents for meme coins and blue-chip crypto analysis
- **Cross-Chain Trading**: Seamless token swaps across different blockchain networks
- **Agentic Payment Flow**: Direct human-to-agent and agent-to-human payment processing
- **1inch Integration**: Advanced price discovery and swap execution
- **Polygon x402**: Streamlined payment processing for agent interactions

## 🏗️ Architecture

The platform consists of three main AI agents working in coordination:

1. **Portfolio Analysis Agent**: Fetches and processes wallet history using 1inch Portfolio and PNL APIs
2. **Meme Coin Specialist Agent**: Analyzes meme coin trades and market patterns
3. **Blue Chip Crypto Agent**: Focuses on established cryptocurrency investments

All agents are registered on ASI's Agentverse and communicate through the ASI One chat protocol, making them accessible and integratable with other AI agents in the ecosystem.

## 🛠️ Tech Stack

### Frontend
- **ASI One LLM**: Direct integration with Agentverse for seamless agent communication
- **Chat Interface**: Built-in ASI One chat protocol for user interactions

### Backend
- **Python**: Core agent logic and API integrations
- **Node.js**: Real-time communication and API handling
- **JavaScript**: Frontend interactions and wallet integrations

### APIs & Services
- **1inch Portfolio API**: Wallet history and PNL data fetching
- **1inch Swap API**: Token price discovery and swap execution
- **Polygon x402**: Agentic payment processing for human-agent transactions
- **ASI Agentverse**: Agent registration and communication protocol

### Blockchain Integration
- **Multi-chain Support**: Cross-chain and same-chain swap capabilities
- **Embedded Wallets**: Secure fund management and automated deposits
- **Smart Contract Integration**: Automated trade execution and fund management

## 🚀 Getting Started

Follow these steps to get the NakalTrade agent up and running on your local machine.

### 1. Set Up the Environment

First, you need to create and activate a Python virtual environment. This ensures that all the project's dependencies are managed separately from your system's global Python packages.

```bash
# Create the virtual environment (do this only once)
python3 -m venv .venv

# Activate the virtual environment (do this every time you start a new terminal session)
source .venv/bin/activate
```

### 2. Install Dependencies

Once your virtual environment is activated, you can install all the necessary Python packages using the provided requirements.txt file.

```bash
pip install -r requirements.txt
```

### 3. Configure API Keys

The agent uses multiple APIs that require authentication. You will need to configure the following:

1. Copy the `.env.example` file to a new file named `.env`
2. Add your API keys:
   - ASI:One Mini API key for AI processing
   - 1inch API key for portfolio and swap data
   - Polygon x402 credentials for payment processing

```env
ASI_API_KEY=your_asi_api_key_here
ONEINCH_API_KEY=your_1inch_api_key_here
POLYGON_X402_KEY=your_polygon_key_here
```

### 4. Run the Agent

Now you are ready to start the agent system.

```bash
python nakal_agent.py
```

The agent will start up and begin listening for requests on http://localhost:8100.

## 🔧 How It Works

### Step-by-Step Process

1. **Wallet Input**: User provides a public wallet address of a successful trader (often from Twitter/X)
2. **Data Fetching**: Portfolio Analysis Agent uses 1inch Portfolio API to retrieve complete trading history and PNL data
3. **AI Analysis**: The fetched data is distributed to two specialized agents:
   - Meme Coin Trader Agent analyzes meme coin patterns and trends
   - Blue Chip Crypto Agent evaluates established cryptocurrency trades
4. **Recommendation Generation**: Both agents collaborate to provide trading suggestions based on historical performance
5. **Trade Execution**: User can choose to execute suggested trades or custom tokens
6. **Automated Processing**: 
   - Agent generates orders using 1inch API for optimal pricing
   - User transfers funds to the agent's wallet
   - Polygon x402 performs the swap (cross-chain or same-chain)
   - Resultant funds are deposited into user's embedded wallet

### Technical Implementation

The platform uses a sophisticated multi-agent architecture where each agent has specialized knowledge:

- **Portfolio Agent**: Handles data aggregation and initial processing
- **Meme Specialist**: Uses pattern recognition for volatile, trend-based tokens
- **Blue Chip Analyst**: Focuses on fundamental analysis and market stability
- **Execution Engine**: Manages the entire trade lifecycle from order generation to fund settlement


## 📋 Partner Technologies

### ASI (Artificial Superintelligence)
- **Agent Registration**: All agents are registered on ASI Agentverse
- **Communication Protocol**: ASI One chat protocol for seamless interactions
- **Multi-Agent Coordination**: Leveraging ASI's framework for specialized agent collaboration

### 1inch Network
- **Portfolio API**: Comprehensive wallet analysis and PNL tracking
- **Swap API**: Optimal price discovery and trade execution
- **Cross-chain Capabilities**: Supporting multiple blockchain networks

### Polygon x402
- **Agentic Payments**: Enabling direct human-to-agent financial transactions
- **Automated Processing**: Streamline

### 5. Open the Frontend

To interact with the agent, open the `frontend.html` file in your web browser. You can now enter queries like `analyze 0x... on eth` to get a detailed performance analysis of any wallet.


