# Monero cryptocurrency

AnyDex supports the management and transfer of XMR.

## Features
- Allows transfer of XMR
- Supports remote nodes
- Provides transaction history of wallet
- Support for subaddresses and integrated addresses

## Setup

### Dependencies
- `monero` Python module (see [https://pypi.org/project/monero/](https://pypi.org/project/monero/))
- Official Monero installation* (see [https://www.getmonero.org/downloads/](https://www.getmonero.org/downloads/))

The Monero _daemon_ and _wallet-rpc-server_ executables (among other ones) are both contained in the `extras` folder in the archive. 

## Running
To allow AnyDex to interact with your Monero wallet, you must first start the Monero _daemon_ and _wallet-rpc-server_. 
Start the daemon using the following command:

`$ monerod`

Upon the first time running the daemon it will attempt to connect to the network and download an instance of the blockchain onto your machine.

To start the _wallet-rpc-server_ run the following command:

`$ monero-wallet-rpc --wallet-file wallet --password "" --rpc-bind-port 28088 --disable-rpc-login`

This command will start an instance of a _wallet_rpc_server_ on wallet file `wallet`, and bind to port 28088.

To use a remote node to communicate with the Monero blockchain instead, run just the following command:

`$ monero-wallet-rpc --wallet-file wallet --password "" --rpc-bind-port 28088 --disable-rpc-login --daemon-host hostname:port`

You are now ready to start interacting with your Monero wallet using AnyDex!

## Notes
- Implementation does not yet allow for multiple accounts
- Monero wallet class includes an additional `transfer_multiple` which may result in lower fees  
- Lack of database means `monitor_transaction` has no implementation
- AnyDex uses the `monero` Python module, _not_ `monero-python`

\* Must at least include `monero-wallet-rpc` executable