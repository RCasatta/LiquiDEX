import sys
import wallycore as wally

txmaker, address_taker, x, A, y, B, FEE, txidB, voutB, amountB, txidFEE, voutFEE, amountFEE = sys.argv[1:]

x = float(x)
y = float(y)
amountB = float(amountB)
amountFEE = float(amountFEE)

voutB = int(voutB)
voutFEE = int(voutFEE)

#decode tx
tx = wally.tx_from_hex(txmaker, 3)
scriptpubkey = wally.address_to_scriptpubkey(address_taker, wally.WALLY_NETWORK_LIQUID_REGTEST)

def h2b_rev(h):
    return wally.hex_to_bytes(h)[::-1]

def btc2sat(btc):
    return round(btc * 10**8)

def add_unblinded_output(tx_, script, asset, amount):
    wally.tx_add_elements_raw_output(
        tx_,
        script,
        b'\x01' + h2b_rev(asset),
        wally.tx_confidential_value_from_satoshi(btc2sat(amount)),
        None, # nonce
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

fixed_fee = 0.00005000

#add output A
add_unblinded_output(tx, scriptpubkey, A, x)
#add output change B
add_unblinded_output(tx, scriptpubkey, B, amountB - y)
#add output change FEE
add_unblinded_output(tx, scriptpubkey, FEE, amountFEE - fixed_fee)
#add output FEE
add_unblinded_output(tx, None, FEE, fixed_fee)
#add input B
add_unsigned_input(tx, txidB, voutB)
#add input FEE
add_unsigned_input(tx, txidFEE, voutFEE)
#print tx
print(wally.tx_to_hex(tx, 3))
