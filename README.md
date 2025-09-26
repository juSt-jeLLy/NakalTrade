# NakalTrade Portfolio Analysis Agent

This project provides a simple yet powerful agent for analyzing the historical performance of any crypto wallet using the 1inch Portfolio API.

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

Once your virtual environment is activated, you can install all the necessary Python packages using the provided `requirements.txt` file.

```bash
pip install -r requirements.txt
```

### 3. Configure API Keys

The agent uses the ASI:One Mini model for natural language processing. You will need to get an API key and configure it.

1.  Copy the `.env.example` file to a new file named `.env`.
2.  Open the `.env` file and add your ASI:One Mini API key.

### 4. Run the Agent

Now you are ready to start the agent.

```bash
python nakal_agent.py
```

The agent will start up and begin listening for requests on `http://localhost:8100`.

### 5. Open the Frontend

To interact with the agent, open the `frontend.html` file in your web browser. You can now enter queries like `analyze 0x... on eth` to get a detailed performance analysis of any wallet.
