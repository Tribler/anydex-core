# Node

AnyDex supports the use of external/remote nodes for most of the cryptocurrencies it supports.
To pass these node configurations around between implementations, a Node class is used.

## Usage
Use the `create_node` method to create a specific Node instance either from the set of default hosts, or from your own user configuration.

To make sure `create_node` creates a Node instance from your own specification, assign a value to the `host` key in `host_config` in the `config.py` file at the root of the `anydex` directory.
Standard host format used is: `protocol://username:password@domain:port`.
