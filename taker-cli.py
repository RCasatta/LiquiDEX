import argparse
import time, requests, json

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
    parser.add_argument("-t", "--tx", help="transaction to match", required=True)

    args = parser.parse_args()

    tx = wally.tx_from_hex(args.tx, wally.WALLY_TX_FLAG_USE_WITNESS | wally.WALLY_TX_FLAG_USE_ELEMENTS)

    connection = RPCHost(args.node_url)

    assert wally.tx_get_num_inputs(tx) == 1
    txid = b2h_rev(wally.tx_get_input_txhash(tx, 0))
    vout = wally.tx_get_input_index(tx, 0)
    ret = connection.call("gettxout", txid, vout)
    assert ret["confirmations"] > 1
    x = btc2sat(ret["value"])
    A = ret["asset"]
    assert wally.tx_get_num_outputs(tx) == 1
    B_ = wally.tx_get_output_asset(tx, 0)
    assert B_[0] == 1
    B = b2h_rev(B_[1:])
    y_ = wally.tx_get_output_value(tx, 0)
    assert y_[0] == 1
    y = wally.tx_confidential_value_to_satoshi(y_)
    unspents = connection.call("listunspent")
    utxos_B = [u for u in unspents if u["asset"] == B]
    assert sum(btc2sat(u["amount"]) for u in utxos_B) >= y
    fixed_fee = 500
    FEE = connection.call("dumpassetlabels")["bitcoin"]
    utxos_FEE = [u for u in unspents if u["asset"] == FEE]
    assert sum(btc2sat(u["amount"]) for u in utxos_FEE) >= fixed_fee

    def add_unblinded_output(tx_, script, asset, sat, blinding_pubkey=None):
        wally.tx_add_elements_raw_output(
            tx_,
            script,
            b'\x01' + h2b_rev(asset),
            wally.tx_confidential_value_from_satoshi(sat),
            blinding_pubkey, # nonce
            None, # surjection proof
            None, # range proof
            0)

    def add_unsigned_input(tx_, txid, vout):
        wally.tx_add_elements_raw_input(
            tx_,
            h2b_rev(txid),
            vout,
            0xffffffff,
            None, # scriptSig
            None, # witness
            None, # nonce
            None, # entropy
            None, # issuance amount
            None, # inflation keys
            None, # issuance amount rangeproof
            None, # inflation keys rangeproof
            None, # pegin witness
            0)

    def get_new_scriptpubkey_and_blinding_pubkey(connection):
        address = connection.call("getnewaddress")
        info = connection.call("getaddressinfo", address)
        scriptpubkey = h2b(info["scriptPubKey"])
        blinding_pubkey = h2b(info["confidential_key"]) if info["confidential_key"] else None
        return (scriptpubkey, blinding_pubkey)

    input_amount_blinders = ["0" * 64]
    input_amounts = [sat2btc(x)]
    input_assets = [A]
    input_asset_blinders = ["0" * 64]

    # add output (A, x)
    scriptpubkey_Ax, blinding_pubkey_Ax = get_new_scriptpubkey_and_blinding_pubkey(connection)
    add_unblinded_output(tx, scriptpubkey_Ax, A, x, blinding_pubkey_Ax)
    # add inputs (B, y+c)
    tot_in_B = 0
    for u in utxos_B:
        add_unsigned_input(tx, u["txid"], u["vout"])
        input_amount_blinders.append(u["amountblinder"])
        input_amounts.append(u["amount"])
        input_asset_blinders.append(u["assetblinder"])
        input_assets.append(u["asset"])
        tot_in_B += btc2sat(u["amount"])
        if tot_in_B >= y:
            break
    # add change output (B, c)
    if tot_in_B > y:
        scriptpubkey_Bchange, blinding_pubkey_Bchange = get_new_scriptpubkey_and_blinding_pubkey(connection)
        add_unblinded_output(tx, scriptpubkey_Bchange, B, tot_in_B - y, blinding_pubkey_Bchange)
    # add inputs (FEE, fixed_fee+c)
    tot_in_FEE = 0
    for u in utxos_FEE:
        add_unsigned_input(tx, u["txid"], u["vout"])
        input_amount_blinders.append(u["amountblinder"])
        input_amounts.append(u["amount"])
        input_asset_blinders.append(u["assetblinder"])
        input_assets.append(u["asset"])
        tot_in_FEE += btc2sat(u["amount"])
        if tot_in_FEE >= fixed_fee:
            break
    # add change output (FEE, c)
    if tot_in_FEE > fixed_fee:
        scriptpubkey_FEEchange, blinding_pubkey_FEEchange = get_new_scriptpubkey_and_blinding_pubkey(connection)
        add_unblinded_output(tx, scriptpubkey_FEEchange, FEE, tot_in_FEE - fixed_fee, blinding_pubkey_FEEchange)
    # add output for fee
    add_unblinded_output(tx, None, FEE, fixed_fee)

    tx_hex = wally.tx_to_hex(tx, wally.WALLY_TX_FLAG_USE_WITNESS | wally.WALLY_TX_FLAG_USE_ELEMENTS)
    tx_hex = connection.call(
        "rawblindrawtransaction",
        tx_hex,
        input_amount_blinders,
        input_amounts,
        input_assets,
        input_asset_blinders
    )

    ret = connection.call("signrawtransactionwithwallet", tx_hex)
    assert ret["complete"]
    tx_hex = ret["hex"]

    ret = connection.call("testmempoolaccept", [tx_hex])
    assert all(e["allowed"] for e in ret), ret

    print(tx_hex)

if __name__ == "__main__":
    main()
