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

def rawblindrawtransaction(tx_hex,
                           input_amount_blinders, input_amounts,
                           input_assets, input_asset_blinders,
                           output_amount_blinders, output_amounts,
                           output_assets, output_asset_blinders):
    """Expects inputs as `elements-cli rawblindrawtransaction`

    and data about already blinded outputs.
    Inputs types and order are questionable but consistent with the rpc call.
    """

    tx = wally.tx_from_hex(tx_hex, wally.WALLY_TX_FLAG_USE_WITNESS | wally.WALLY_TX_FLAG_USE_ELEMENTS)

    input_values = [btc2sat(i) for i in input_amounts]
    input_assets = [h2b_rev(h) for h in input_assets]
    input_abfs = [h2b_rev(h) for h in input_asset_blinders]
    input_vbfs = [h2b_rev(h) for h in input_amount_blinders]
    input_ags = [wally.asset_generator_from_bytes(a, bf) for a, bf in zip(input_assets, input_abfs)]

    input_assets_concat = b''.join(input_assets)
    input_abfs_concat = b''.join(input_abfs)
    input_ags_concat = b''.join(input_ags)

    min_value = 1
    ct_exp = 0
    # TODO: assert all output amounts are in the supported range
    ct_bits = 52

    # TODO: add general support for non-fee unblinded outputs, for those:
    #       - do not generate blinders
    #       - do not set *proof and nonce
    out_num = wally.tx_get_num_outputs(tx)
    output_blinded_values = []
    output_abfs = []
    output_vbfs = []
    assert len(output_amount_blinders) == len(output_amounts) == len(output_asset_blinders) == len(output_assets) == out_num
    for out_idx in range(out_num):
        given = bool(output_amount_blinders[out_idx])
        if wally.tx_get_output_nonce(tx, out_idx) == b'\x00' * 33:  # unblinded
            if out_idx == out_num - 1:  # fee
                continue

            # If given, 0-th output might be unblinded
            assert out_idx == 0 and given

        output_abfs.append(h2b_rev(output_asset_blinders[out_idx]) if given else os.urandom(32))
        output_vbfs.append(h2b_rev(output_amount_blinders[out_idx]) if given else os.urandom(32))
        output_blinded_values.append(btc2sat(output_amounts[out_idx]) if given else wally.tx_confidential_value_to_satoshi(wally.tx_get_output_value(tx, out_idx)))

    output_vbfs.pop(-1)
    output_vbfs.append(wally.asset_final_vbf(
        input_values + output_blinded_values, wally.tx_get_num_inputs(tx),
        b''.join(input_abfs + output_abfs), b''.join(input_vbfs + output_vbfs)))

    for out_idx in range(out_num - 1):
        given = bool(output_amount_blinders[out_idx])

        blinding_pubkey = wally.tx_get_output_nonce(tx, out_idx)
        scriptpubkey = wally.tx_get_output_script(tx, out_idx)
        assert scriptpubkey

        if given:
            asset = h2b_rev(output_assets[out_idx])
            value_satoshi = btc2sat(output_amounts[out_idx])
        else:
            asset_prefixed = wally.tx_get_output_asset(tx, out_idx)
            value_bytes = wally.tx_get_output_value(tx, out_idx)

            assert asset_prefixed[0] == 1 and value_bytes[0] == 1
            value_satoshi = wally.tx_confidential_value_to_satoshi(value_bytes)
            asset = asset_prefixed[1:]

        output_abf = output_abfs[out_idx]
        output_vbf = output_vbfs[out_idx]
        blinded = output_abf != b'\x00' * 32 and output_vbf != b'\x00' * 32

        if not blinded:
            continue

        eph_key_prv = os.urandom(32)
        eph_key_pub = wally.ec_public_key_from_private_key(eph_key_prv)
        blinding_nonce = wally.sha256(wally.ecdh(blinding_pubkey, eph_key_prv))

        output_generator = wally.asset_generator_from_bytes(asset, output_abf)
        output_value_commitment = wally.asset_value_commitment(
            value_satoshi, output_vbf, output_generator)

        rangeproof = wally.asset_rangeproof_with_nonce(
            value_satoshi, blinding_nonce, asset, output_abf, output_vbf,
            output_value_commitment, scriptpubkey, output_generator, min_value,
            ct_exp, ct_bits)

        surjectionproof = wally.asset_surjectionproof(
            asset, output_abf, output_generator, os.urandom(32),
            input_assets_concat, input_abfs_concat, input_ags_concat)

        if not given:
            wally.tx_set_output_asset(tx, out_idx, output_generator)
            wally.tx_set_output_value(tx, out_idx, output_value_commitment)
            wally.tx_set_output_nonce(tx, out_idx, eph_key_pub)
        wally.tx_set_output_surjectionproof(tx, out_idx, surjectionproof)
        wally.tx_set_output_rangeproof(tx, out_idx, rangeproof)

    return wally.tx_to_hex(tx, wally.WALLY_TX_FLAG_USE_WITNESS | wally.WALLY_TX_FLAG_USE_ELEMENTS)

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
    parser.add_argument("-p", "--proposal", help="Proposal to match", required=True)

    args = parser.parse_args()

    j = json.loads(args.proposal)
    tx = j["tx"]
    assert len(j["inputs"]) == len(j["outputs"]) == 1
    maker_input = j["inputs"][0]
    maker_output = j["outputs"][0]
    x = maker_input["amount"]
    A = maker_input["asset"]
    input_amount_blinders = [maker_input["amount_blinder"]]
    input_amounts = [sat2btc(x)]
    input_assets = [A]
    input_asset_blinders = [maker_input["asset_blinder"]]
    y = maker_output["amount"]
    B = maker_output["asset"]

    tx = wally.tx_from_hex(tx, wally.WALLY_TX_FLAG_USE_WITNESS | wally.WALLY_TX_FLAG_USE_ELEMENTS)

    connection = RPCHost(args.node_url)

    assert wally.tx_get_num_inputs(tx) == 1
    txid = b2h_rev(wally.tx_get_input_txhash(tx, 0))
    vout = wally.tx_get_input_index(tx, 0)
    ret = connection.call("gettxout", txid, vout)
    assert ret["confirmations"] > 1
    if "value" in ret:
        assert ret["value"] == sat2btc(x)
        assert ret["asset"] == A
        assert maker_input["amount_blinder"] == maker_input["asset_blinder"] == "0" * 64
    else:
        asset_commitment = wally.asset_generator_from_bytes(h2b_rev(A), h2b_rev(maker_input["asset_blinder"]))
        amount_commitment = wally.asset_value_commitment(x, h2b_rev(maker_input["amount_blinder"]), asset_commitment)
        assert b2h(asset_commitment) == ret["assetcommitment"]
        assert b2h(amount_commitment) == ret["valuecommitment"]

    assert wally.tx_get_num_outputs(tx) == 1
    asset_commitment = wally.tx_get_output_asset(tx, 0)
    amount_commitment = wally.tx_get_output_value(tx, 0)
    if asset_commitment[0] == 1:
        assert amount_commitment[0] == 1
        assert asset_commitment[1:] == h2b_rev(B)
        assert amount_commitment == wally.tx_confidential_value_from_satoshi(y)
    else:
        asset_commitment_ = wally.asset_generator_from_bytes(h2b_rev(B), h2b_rev(maker_output["asset_blinder"]))
        amount_commitment_ = wally.asset_value_commitment(y, h2b_rev(maker_output["amount_blinder"]), asset_commitment_)
        assert asset_commitment == asset_commitment_
        assert amount_commitment == amount_commitment_

    unspents = connection.call("listunspent")
    unspents = [u for u in unspents if u["spendable"]]
    utxos_B = [u for u in unspents if u["asset"] == B]
    assert sum(btc2sat(u["amount"]) for u in utxos_B) >= y
    fixed_fee = 5000
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

    # TODO: shuffle added inputs and outpus, otherwise blinding partially pointless...

    tx_hex = wally.tx_to_hex(tx, wally.WALLY_TX_FLAG_USE_WITNESS | wally.WALLY_TX_FLAG_USE_ELEMENTS)
    num_out = wally.tx_get_num_outputs(tx)
    tx_hex = rawblindrawtransaction(
        tx_hex,
        input_amount_blinders,
        input_amounts,
        input_assets,
        input_asset_blinders,
        [maker_output["amount_blinder"]] + [None] * (num_out - 1),
        [sat2btc(maker_output["amount"])] + [None] * (num_out - 1),
        [maker_output["asset"]] + [None] * (num_out - 1),
        [maker_output["asset_blinder"]] + [None] * (num_out - 1),
    )

    ret = connection.call("signrawtransactionwithwallet", tx_hex)
    assert ret["complete"]
    tx_hex = ret["hex"]

    ret = connection.call("testmempoolaccept", [tx_hex])
    assert all(e["allowed"] for e in ret), ret

    print(tx_hex)

if __name__ == "__main__":
    main()
