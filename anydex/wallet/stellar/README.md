# Stellar wallet

The stellar wallet is implemented using [py-stellar-base](https://github.com/StellarCN/py-stellar-base).

The wallet only supports Stellar lumens has no ability to transfer other assets.

## Transfers
Stellar has a few operations that transfer lumens, important to us are `Payment`,
`Create Account` and `Account Merge`.

The wallet supports `Create Account` and `Payment`. The wallet automatically
chooses the operation depending on if the receiving account is created or not.

The `Account Merge` operation is also supported, but does is not automatically used.

## Features
- transfer stellar lumens
- get transaction history
- get balance
- keys stored offline

## Notes
- only supports stellar lumens
- all amounts are in the smallest denomination 