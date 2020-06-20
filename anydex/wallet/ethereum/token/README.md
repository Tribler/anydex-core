# Erc-20 tokens Wallet
The tokens wallet allows for the transfer of any erc-20 token.

The wallet is inherits from the ethereum wallet class, but has different methods
for transferring tokens and getting the balance. 

When a new token wallet is created it's actually just using the already created 
ethereum wallet or creating a new ethereum wallet.


## Usage
A token wallet can be created from it's constructor, but is not advised due to the amount of parameters.
Instead the `from_json` method can be used to create a token wallet from a json file, like the one below. 

````json
{
  "identifier": "LINK",
  "name": "ChainLink Token",
  "precision": 18,
  "contract_address": "0x514910771af9ca656af840dff83e8264ecf986ca"
}
````
You can specify a list of objects and a list of token wallets will be returned.

Either of json file can be specified or the default json file will be used.

The token wallet relies on the ethereum wallet having ethereum to pay fees.



## Features
- transfer tokens
- get transaction history
- get balance
- keys stored offline

## Notes
- The wallet needs to be connected to a node to work.
- all amounts are in the smallest denomination 