import argparse
import time, requests, json

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
    assert utxo["assetblinder"] == utxo["amountblinder"] == "0"*64, "utxo must be unblinded"

    amount_receive = round(rate * utxo["amount"], 8)
    address = connection.call("getnewaddress")
    address = connection.call("getaddressinfo", address)["unconfidential"]

    tx = connection.call(
        "createrawtransaction",
        [{"txid": txid, "vout": vout, "sequence": 0xffffffff}],
        {address: amount_receive},
        0,
        False,
        {address: asset_receive})
    
    ret = connection.call(
        "signrawtransactionwithwallet",
        tx,
        None,
        "SINGLE|ANYONECANPAY")

    assert ret["complete"]
    print(ret["hex"])

if __name__ == "__main__":
    main()
