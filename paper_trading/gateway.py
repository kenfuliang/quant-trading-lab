"""Read-only IB API handshake and paper-account identity validation."""
import re
import socket
import threading

from ibapi.client import EClient
from ibapi.wrapper import EWrapper

HOST = "127.0.0.1"
PORT = 4002


def validate_paper_accounts(accounts):
    if not accounts or any(not re.fullmatch(r"DU\d+", account) for account in accounts):
        raise ValueError("Gateway must expose only DU-prefixed IBKR paper accounts.")
    return accounts


class PaperProbe(EWrapper, EClient):
    def __init__(self):
        EWrapper.__init__(self)
        EClient.__init__(self, self)
        self.ready = threading.Event()
        self.accounts_received = threading.Event()
        self.accounts = []
        self.error_codes = []

    def nextValidId(self, orderId):
        self.ready.set()

    def managedAccounts(self, accountsList):
        self.accounts = [value.strip() for value in accountsList.split(",") if value.strip()]
        self.accounts_received.set()

    def error(self, reqId, errorTime, errorCode, errorString, advancedOrderRejectJson=""):
        self.error_codes.append(errorCode)


def probe(timeout=15):
    # Fixed loopback paper port. Never scan or fall back to live ports.
    try:
        with socket.create_connection((HOST, PORT), timeout=2):
            pass
    except OSError as error:
        raise RuntimeError("IB Gateway paper API is not listening on 127.0.0.1:4002. Sign in and check API settings.") from error
    client = PaperProbe()
    worker = None
    try:
        client.connect(HOST, PORT, clientId=71)
        worker = threading.Thread(target=client.run, daemon=True)
        worker.start()
        if not client.ready.wait(timeout):
            raise RuntimeError("IB API handshake timed out. Check Gateway's connection approval and socket settings.")
        client.reqManagedAccts()
        if not client.accounts_received.wait(timeout):
            raise RuntimeError("Gateway did not return managed accounts.")
        return validate_paper_accounts(client.accounts)
    finally:
        client.disconnect()
        if worker:
            worker.join(timeout=2)
