#!/usr/bin/env python3
"""
trade.py — place a MARKET order on the IBKR PAPER account. Manual, one order per run.

Usage:
    python trade.py BUY  AAPL 10
    python trade.py SELL AAPL 10

Safety:
    - Refuses to run unless the connected account is a paper account (id starts "DU").
    - Requires "Read-Only API" to be UNCHECKED in TWS
      (File -> Global Configuration -> API -> Settings).
    - Places one market order, waits for the result, prints it. Nothing automatic.
"""

import sys
from ib_async import IB, Stock, MarketOrder

HOST, PORT, CLIENT_ID = "127.0.0.1", 7497, 21


def main() -> None:
    if len(sys.argv) != 4 or sys.argv[1].upper() not in ("BUY", "SELL"):
        sys.exit("Usage: python trade.py BUY|SELL SYMBOL QUANTITY   (e.g. python trade.py BUY AAPL 10)")

    action = sys.argv[1].upper()
    symbol = sys.argv[2].upper()
    try:
        qty = int(sys.argv[3])
        if qty <= 0:
            raise ValueError
    except ValueError:
        sys.exit("Quantity must be a positive whole number.")

    ib = IB()
    try:
        ib.connect(HOST, PORT, clientId=CLIENT_ID, timeout=12)  # NOT readonly - we place an order
    except Exception as e:
        sys.exit(f"\n  x Could not connect to TWS on {HOST}:{PORT}. Is the API enabled? ({e})\n")

    # --- safety: paper accounts only ---
    accounts = ib.managedAccounts()
    if not any(a.startswith("DU") for a in accounts):
        ib.disconnect()
        sys.exit(f"\n  x REFUSING TO TRADE: account(s) {accounts} are not paper (paper ids start 'DU').\n")
    account = next(a for a in accounts if a.startswith("DU"))

    contract = Stock(symbol, "SMART", "USD")
    if not ib.qualifyContracts(contract):
        ib.disconnect()
        sys.exit(f"  x Symbol {symbol} not recognized.")

    print(f"\n  Placing PAPER order: {action} {qty} {symbol}  (account {account})")
    order = MarketOrder(action, qty)
    trade = ib.placeOrder(contract, order)

    # Wait for a FILL. Orders often sit briefly in PendingSubmit before IBKR
    # acknowledges and fills them, so we hold the connection open rather than
    # disconnecting early (which would strand the order). Once acknowledged
    # (Submitted/PreSubmitted) we give it a short grace period to fill; if it
    # doesn't, it's resting (markets closed) and we report that.
    ack_at = None
    for i in range(60):  # up to ~30s
        ib.sleep(0.5)
        s = trade.orderStatus.status
        if s == "Filled" or s in ("Cancelled", "ApiCancelled", "Inactive"):
            break
        if s in ("Submitted", "PreSubmitted"):
            if ack_at is None:
                ack_at = i
            elif i - ack_at >= 12:  # ~6s after acknowledgment, still unfilled -> resting
                break

    st = trade.orderStatus
    print(f"  Status : {st.status}")
    if st.filled:
        print(f"  Filled : {st.filled} @ ${st.avgFillPrice:,.2f}")
    if st.remaining and st.status in ("Submitted", "PreSubmitted"):
        print(f"  Resting: {st.remaining} share(s) working - markets may be closed; "
              f"it will fill at the next open.")
    for entry in trade.log:
        if entry.message:
            print(f"  Note   : {entry.message}")
    if st.status == "PendingSubmit":
        print("  ! Still PendingSubmit - TWS may be holding it for an order-precaution\n"
              "    confirmation. In TWS: Global Configuration -> API -> Precautions ->\n"
              "    check 'Bypass Order Precautions for API Orders'. Then retry.")
    print()

    ib.disconnect()


if __name__ == "__main__":
    main()
