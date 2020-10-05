# LiquiDEX

**WARNING**: This is experimental software, do not use with real funds.

A decentralized exchange for Liquid transactions.

## Naming

- **Maker**: proposes the trade as a signed but partial transaction
- **Taker**: accepts the trade, completes and broadcasts the transaction

## Flow

Maker wants to propose to exchange amount `x` of asset `A` for amount `y` of
asset `B`.

Maker must have an utxo `U_xA` locking exactly amount `x` of asset `A`.

Maker creates a transaction `T_xAyB` spending a single utxo `U_xA` and receiving
a single output locking amount `y` of asset `B`. At this stage `T_xAyB` is
partial and invalid.

Maker signs the (only) input with `SIGHASH_SINGLE | SIHASH_ANYONECANPAY`.
This allows the Taker to add more inputs and outputs, without invalidating the
Maker signature.

Maker posts `TX_xAyB` to the __LiquiDEX__.

Taker sees `TX_xAyB` on the __LiquiDEX__, and decides to accept the trade.

Taker does _whatever it wants_ to complete the trade, what follow is an example.

Taker does some verifications, such as `U_xA` actually locks amount `x` of
asset `A`.

Taker adds an output locking amount `x` of asset `A`.

Taker funds `TX_xAyB` (fee and asset `A`).

Taker signs the newly added transacion inputs, possibly with `SIGHASH_ALL`.

Taker broadcasts the `TX_xAyB`, and the trade is executed.

### Examples

#### 10000 USDT in exchange of 1 LBTC

![Liquidex tx USDT-LBTC](imgs/Liquidex_tx_USDT-LBTC.png)

#### 10 asset A in exchange of 15 asset B 

![Liquidex tx A-B](imgs/Liquidex_tx_A-B.png)

## Test on Liquid Mainnet

In the following example performed on Liquid Mainnet, the Maker propose a trade
offering 175000000 sats of [this unnamed asset](https://blockstream.info/liquid/asset/8026fa969633b7b6f504f99dde71335d633b43d18314c501055fcd88b9fcb8de)
in exchange of 1.75 Atomic Swap pints.

### Requirements

`python3` with `requests` and `wallycore>=0.7.9` modules installed 

### Maker
```
$ python3 maker-cli.py -n http://USER:PSW@IP:PORT/ -u 8f8034f28110a1d1710ab243716f2581f08df9e4dc89355e24f6efe1c2861c07:1 -a f638b720fe531bbba23a71495aebf55592f45adc6c89f00de38303f60c7b51d7 -r 0.000001 | jq
{
  "tx": "020000000101071c86c2e1eff6245e3589dce4f98df081256f7143b20a71d1a11081f234808f01000000171600140b22d358af49422e133684f57d0eb49a9fca84e0ffffffff010a39e73aac4854ce1a1d0ec397db58ec6ce018413f6886abdcaaea3244cc2f803c099380bc1c9039e82a27df4217d54d8f107b8868ad5a947b802a4bfe48134fc6d2028e9004696ef308f97994ebe47294e5fa4273479f7e1a779f581a70f17f7b35be17a914f69b2673d97b6bdf04bbfee2afdf26056de39450870000000000000247304402201a3a6b57b7c70e8efbffd59c4b1e2402448436d97beb37fedc81897eade4f3f702202cce73b837719ac7d332aef7f9b2d7412ffbeffb677635458dc745b3190822bc83210249c7906961ac155d2a7f60429a4c8e90cc7b1857be5c7cb5c2f5fb736e3df8a4000000",
  "inputs": [
    {
      "asset": "8026fa969633b7b6f504f99dde71335d633b43d18314c501055fcd88b9fcb8de",
      "amount": 175000000,
      "asset_blinder": "e9fe8ff23076c01fe0e5b545807c01157c99501288d9479bfb7e7d24feba694d",
      "amount_blinder": "6a80b9e7b887bdde8f23ebe48b307d9516259591681d71d376fb290b13df1674"
    }
  ],
  "outputs": [
    {
      "asset": "f638b720fe531bbba23a71495aebf55592f45adc6c89f00de38303f60c7b51d7",
      "amount": 175,
      "asset_blinder": "07b4a065649a9f57e07dba6d87672f5e9d617bca0b8593da593ec77eec746b9c",
      "amount_blinder": "216f304aaadd2b62b81ac4d6ebc219b4d6b9b61611cf2103ab377944c9b69ae8"
    }
  ]
}

```

### Taker

```
$ python3 taker-cli.py -n http://USER:PSW@IP:PORT/ -p '{"tx":"020000000101071c86c2e1eff6245e3589dce4f98df081256f7143b20a71d1a11081f234808f01000000171600140b22d358af49422e133684f57d0eb49a9fca84e0ffffffff010a39e73aac4854ce1a1d0ec397db58ec6ce018413f6886abdcaaea3244cc2f803c099380bc1c9039e82a27df4217d54d8f107b8868ad5a947b802a4bfe48134fc6d2028e9004696ef308f97994ebe47294e5fa4273479f7e1a779f581a70f17f7b35be17a914f69b2673d97b6bdf04bbfee2afdf26056de39450870000000000000247304402201a3a6b57b7c70e8efbffd59c4b1e2402448436d97beb37fedc81897eade4f3f702202cce73b837719ac7d332aef7f9b2d7412ffbeffb677635458dc745b3190822bc83210249c7906961ac155d2a7f60429a4c8e90cc7b1857be5c7cb5c2f5fb736e3df8a4000000","inputs":[{"asset":"8026fa969633b7b6f504f99dde71335d633b43d18314c501055fcd88b9fcb8de","amount":175000000,"asset_blinder":"e9fe8ff23076c01fe0e5b545807c01157c99501288d9479bfb7e7d24feba694d","amount_blinder":"6a80b9e7b887bdde8f23ebe48b307d9516259591681d71d376fb290b13df1674"}],"outputs":[{"asset":"f638b720fe531bbba23a71495aebf55592f45adc6c89f00de38303f60c7b51d7","amount":175,"asset_blinder":"07b4a065649a9f57e07dba6d87672f5e9d617bca0b8593da593ec77eec746b9c","amount_blinder":"216f304aaadd2b62b81ac4d6ebc219b4d6b9b61611cf2103ab377944c9b69ae8"}]}' > tx.txt
```

### Result

[a43dafc00a6c488085bdf849ca954e4a82f80d56a1c8931873df83d5d22981a4](https://blockstream.info/liquid/tx/a43dafc00a6c488085bdf849ca954e4a82f80d56a1c8931873df83d5d22981a4)

## Considerations

[Existing protocol](https://github.com/Blockstream/liquid-swap/) is done in 3 steps while LiquiDEX use only 2 steps.
Moreover, contrary to liquid-swap, LiquiDEX it's not interactive, meaning that the Maker does not have to be online when the trade executes.
In LiquiDEX creating a trade proposal does not require an onchain tx, however, removing the proposal requires that the maker makes a tx, 
spending the input proposed as a trade and invalidating the proposal. 

## Possible improvements:

- Handle L-BTC as a trading asset.
- Taker could potentially take multiple maker proposed transactions and complete
  those in a single tx.
- Use PSET once there is a new Elements release supporting its finalized redesign.

## Copyright

[MIT](LICENSE)
