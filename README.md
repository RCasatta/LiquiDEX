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
offering 1 sats of [Lager pints](https://blockstream.info/liquid/asset/8026fa969633b7b6f504f99dde71335d633b43d18314c501055fcd88b9fcb8de)
in exchange of 1 sat of [this unnamed asset](https://blockstream.info/liquid/asset/8026fa969633b7b6f504f99dde71335d633b43d18314c501055fcd88b9fcb8de).

### Requirements

`python3` with `requests` and `wallycore>=0.7.9` modules installed 

### Maker
```
$ python3 maker-cli.py -n http://USER:PSW@IP:PORT/ -u 52b988dbbd4db1069de7183f72687d7a8d367f89fc0ca4dcad8ae89e9822db16:2 -a 1a57c66ec5e922285d8d261bafe6f8eee7ec37a60c80a7eca9ae85c7a62f01ca -r 1 
{
  "tx": "02000000010116db22989ee88aaddca40cfc897f368d7a7d68723f18e79d06b14dbddb88b95202000000171600144c8f2937d509c9bf899e271ebf45f022ede744eaffffffff0101ca012fa6c785aea9eca7800ca637ece7eef8e6af1b268d5d2822e9c56ec6571a0100000000000000010017a914ee144f68da1f9bd660beae702ea16176c84b0583870000000000000247304402202550a31425efa9d35742f18fd488d540a11a3d8faeddb098b9249a6affa3b97e0220174d78870770f283c00e2669e0bf412d101989c7532f6c44340f5fedd52788b4832102a520dca5668fe0d89531d436ecb4fc52f5c9243ab0b45f5e14a64f08ccd26efa000000",
  "inputs": [
    {
      "asset": "8026fa969633b7b6f504f99dde71335d633b43d18314c501055fcd88b9fcb8de",
      "amount": 1,
      "asset_blinder": "ebf74cafa8f3811e09196ca9cd2c7bdbb07cd9f3c5dd481a719e66c87370326f",
      "amount_blinder": "2e675260821dc8e7ab4a3f910b4c655b32a58b0bdb20e630acb26d5b1ee5893a"
    }
  ],
  "outputs": [
    {
      "asset": "1a57c66ec5e922285d8d261bafe6f8eee7ec37a60c80a7eca9ae85c7a62f01ca",
      "amount": 1,
      "asset_blinder": "0000000000000000000000000000000000000000000000000000000000000000",
      "amount_blinder": "0000000000000000000000000000000000000000000000000000000000000000"
    }
  ]
}
```

### Taker

```
$ python3 taker-cli.py -n http://USER:PSW@IP:PORT/ -p '{"tx":"02000000010116db22989ee88aaddca40cfc897f368d7a7d68723f18e79d06b14dbddb88b95202000000171600144c8f2937d509c9bf899e271ebf45f022ede744eaffffffff0101ca012fa6c785aea9eca7800ca637ece7eef8e6af1b268d5d2822e9c56ec6571a0100000000000000010017a914ee144f68da1f9bd660beae702ea16176c84b0583870000000000000247304402202550a31425efa9d35742f18fd488d540a11a3d8faeddb098b9249a6affa3b97e0220174d78870770f283c00e2669e0bf412d101989c7532f6c44340f5fedd52788b4832102a520dca5668fe0d89531d436ecb4fc52f5c9243ab0b45f5e14a64f08ccd26efa000000","inputs":[{"asset":"8026fa969633b7b6f504f99dde71335d633b43d18314c501055fcd88b9fcb8de","amount":1,"asset_blinder":"ebf74cafa8f3811e09196ca9cd2c7bdbb07cd9f3c5dd481a719e66c87370326f","amount_blinder":"2e675260821dc8e7ab4a3f910b4c655b32a58b0bdb20e630acb26d5b1ee5893a"}],"outputs":[{"asset":"1a57c66ec5e922285d8d261bafe6f8eee7ec37a60c80a7eca9ae85c7a62f01ca","amount":1,"asset_blinder":"0000000000000000000000000000000000000000000000000000000000000000","amount_blinder":"0000000000000000000000000000000000000000000000000000000000000000"}]}' > tx.txt
```

### Result

[e1004eeb2d12130c9e62e8522ecc23f498adeb7cedca65423215027ab806edfe](https://blockstream.info/liquid/tx/e1004eeb2d12130c9e62e8522ecc23f498adeb7cedca65423215027ab806edfe)

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
