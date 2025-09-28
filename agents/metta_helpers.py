import re

def is_wallet_address(token: str) -> bool:
    """Checks if a string is an Ethereum-style wallet address."""
    return re.fullmatch(r"0x[a-fA-F0-9]{40}", token) is not None

def is_number(token: str) -> bool:
    """Checks if a string can be converted to a float."""
    try:
        float(token)
        return True
    except ValueError:
        return False
