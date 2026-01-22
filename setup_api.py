import os
import getpass
import json
import eth_account
from hyperliquid.exchange import Exchange
from eth_account.signers.local import LocalAccount


def setup(base_url=None, perp_dexs=None):
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(config_path) as f:
        config = json.load(f)
    account: LocalAccount = eth_account.Account.from_key(get_secret_key(config))
    address = config["account_address"]
    if address == "":
        address = account.address
    print("Running with account address:", address)
    if address != account.address:
        print("Running with agent address:", account.address)

    exchange = Exchange(account, base_url, account_address=address, perp_dexs=perp_dexs)
    return address, exchange


def get_secret_key(config):
    if config["secret_key"]:
        secret_key = config["secret_key"]
    else:
        keystore_path = config["keystore_path"]
        keystore_path = os.path.expanduser(keystore_path)
        if not os.path.isabs(keystore_path):
            keystore_path = os.path.join(os.path.dirname(__file__), keystore_path)
        if not os.path.exists(keystore_path):
            raise FileNotFoundError(f"Keystore file not found: {keystore_path}")
        if not os.path.isfile(keystore_path):
            raise ValueError(f"Keystore path is not a file: {keystore_path}")
        with open(keystore_path) as f:
            keystore = json.load(f)
        password = getpass.getpass("Enter keystore password: ")
        secret_key = eth_account.Account.decrypt(keystore, password)
    return secret_key