import argparse
import time, requests, json, os

import wallycore as wally

h2b = wally.hex_to_bytes
b2h = wally.hex_from_bytes
h2b_rev = lambda h : wally.hex_to_bytes(h)[::-1]
b2h_rev = lambda b : wally.hex_from_bytes(b[::-1])

def btc2sat(btc):
    return round(btc * 10**8)

def sat2btc(sat):
    return round(sat * 10**-8, 8)

# adapted from https://github.com/Blockstream/liquid_multisig_issuance 
class RPCHost(object):
    def __init__(self, url):
        self.session = requests.Session()
        self.url = url
        self.headers = {"content-type": "application/json"}

    def call(self, rpc_method, *params):
        payload = json.dumps({"method": rpc_method, "params": list(params), "jsonrpc": "2.0"})
        for i in range(5):
            try:
                response = self.session.post(self.url, headers=self.headers, data=payload)
                connected = True
            except requests.exceptions.ConnectionError:
                time.sleep(10)
        assert connected
        assert response.status_code in (200, 500), f"RPC connection failure: {response.status_code} {response.reason}"
        j = response.json()
        assert "error" not in j or j["error"] is None, f"Error : {j['error']}"
        return j['result']


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("-n", "--node-url", help="Elements node URL, eg http://USERNAME:PASSWORD@HOST:PORT/", required=True)
    parser.add_argument("-u", "--utxo", help="txid:vout", required=True)
    parser.add_argument("-a", "--asset", help="asset to receive", required=True)
    parser.add_argument("-r", "--rate", type=float, help="price_asset_send/price_asset_receive", required=True)

    args = parser.parse_args()

    txid, vout = args.utxo.split(":")
    vout = int(vout)
    asset_receive, rate = args.asset, args.rate

    connection = RPCHost(args.node_url)

    unspents = connection.call("listunspent")
    utxo = [u for u in unspents if u["txid"] == txid and u["vout"] == vout][0]

    amount_receive = round(rate * utxo["amount"], 8)
    address = connection.call("getnewaddress")

    tx = connection.call(
        "createrawtransaction",
        [{"txid": txid, "vout": vout, "sequence": 0xffffffff}],
        {address: amount_receive},
        0,
        False,
        {address: asset_receive})

    asset_blinder_bytes = os.urandom(32)
    amount_blinder_bytes = os.urandom(32)
    asset_commitment = wally.asset_generator_from_bytes(h2b_rev(asset_receive), asset_blinder_bytes)
    amount_commitment = wally.asset_value_commitment(btc2sat(amount_receive), amount_blinder_bytes, asset_commitment)

    tx_ = wally.tx_from_hex(tx, wally.WALLY_TX_FLAG_USE_WITNESS | wally.WALLY_TX_FLAG_USE_ELEMENTS)
    wally.tx_set_output_asset(tx_, 0, asset_commitment)
    wally.tx_set_output_value(tx_, 0, amount_commitment)
    tx = wally.tx_to_hex(tx_, wally.WALLY_TX_FLAG_USE_WITNESS | wally.WALLY_TX_FLAG_USE_ELEMENTS)

    ret = connection.call(
        "signrawtransactionwithwallet",
        tx,
        None,
        "SINGLE|ANYONECANPAY")

    assert ret["complete"]
    print(json.dumps({
        "tx": ret["hex"],
        "inputs": [{
            "asset": utxo["asset"],
            "amount": btc2sat(utxo["amount"]),
            "asset_blinder": utxo["assetblinder"],
            "amount_blinder": utxo["amountblinder"],
        }],
        "outputs": [{
            "asset": asset_receive,
            "amount": btc2sat(amount_receive),
            "asset_blinder": b2h_rev(asset_blinder_bytes),
            "amount_blinder": b2h_rev(amount_blinder_bytes),
        }],
    }, separators=(',', ':')))

if __name__ == "__main__":
    main()
