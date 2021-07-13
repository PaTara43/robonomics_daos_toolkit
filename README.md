# Robonomics DAOS toolkit
### Toolkit for interacting with devices within DAOS. Get ACL from blockchain, log sessions and perform transactions to control devices in a smart office (coming in future).

*Note: the entire communication is based on substrate blockchain, in particular, [Robonomics](https://robonomics.network/) platform*
These modules are mostly based on using a thing called Digital Twin. More about them in Robonomics one may find [here](https://wiki.robonomics.network/docs/en/digital-twins/).

Requirements:
- [Robonomics binary](https://github.com/airalab/robonomics/releases) (tested fine on 1.0)
- [IPFS v0.6.0](https://dist.ipfs.io/go-ipfs/v0.6.0/go-ipfs_v0.6.0_linux-arm.tar.gz)
- Rust-nightly ([here](https://www.rust-lang.org/tools/install) and [here](https://doc.rust-lang.org/edition-guide/rust-2018/rustup-for-managing-rust-versions.html))
- Digital Twin for your devices
- ```pip3 install -r requirements.txt```

## Main modules
### 1. ACL - Access Control List
*Grant access to devices for those IDs only, which are presented in a blockchain-confirmed list*
1) Create a config dictionary (either parse `.yaml` file or whatever)

Make sure to make it of form of `config.yaml` from this repository. `url: "ws://127.0.0.1:9944"` is for local or development robonomics node. If other, fill in with corresponding ws

2) In your script import acl module and substrate connection module:

```from robonomics_daos_toolkit import acl, substrate_connection as subcon```
   
3) The best pattern to use this module is to initiate an instance of `acl.ACL` class in the beginning and then refer to its `acl` attribute every time you need to check whether ID is on the list.

Example:
```python
if config["use_daos_toolkit"]:
    substrate = subcon.substrate_connection(config["daos_toolkit"]["substrate"])
    if config["daos_toolkit"]["use_acl"]:
        # initiate an instance of ACL class based on digital twin of a device
        logging.info("initiating ACL class")
        acl_obj = acl.ACL(config['daos_toolkit'], substrate)
        if not acl_obj:
            logging.critical("ACL instance error, exiting")
            sys.exit()
        else:
            logging.info("ACL initiated")
```
The script automatically looks for new records with datalogs (to be described below) so each time you refer to `acl` attribute, it's the most up-to-date one.

4) Launch IPFS

```bash
ipfs daemon
```

5) Upload yaml file with acl to IPFS network. You may use local node, [Pinata](https://pinata.cloud/), etc.
   
Don't forget to make the uploaded file look like this for correct parsing:
```
allowed_ids:
  '124567890'
```

6) Launch a Robonomics node (skip if connecting to existing node)
```bash
chmod +x robonomics
robonomics --dev --tmp
```

7) Go to [parachain.robonomics.network](parachain.robonomics.network) and [create a digital twin](https://wiki.robonomics.network/docs/en/digital-twins/) and an acl topic for it with a specified address. Push `acl.yaml` IPFS hash to corresponding [account datalog](https://wiki.robonomics.network/docs/en/rio-datalog/).

More info about accounts may be found on [wiki](https://wiki.robonomics.network/docs/en/create-account-in-dapp/). Paste digital twin ID and topic names to config file.

8) Launch your script or the existing `acl.py`

If everything is alright, you should see the contents of the `acl.yaml` file.

#### How it works

After creating a Digital Twin You have assigned specific topics to specific addresses in Robonomics network, which datalog may be read. This template is proposed:
```json
{
  "dt":{
    "acl_____________________________":"<acl_host_address_in_suubstrate>",
    "device__________________________":"<device_address_in_suubstrate>" #if necessary
  }
}   
```
Datalog of each account may be read by calling some functions of py-substrate-interface. 

When starting the script, it looks for Digital Twin with a config-described ID, parses its topics, looks for the acl topic as it's named in config, takes the last record of the corresponding account datalog with an IPFS hash and downloads it. If it's a yaml file, script parses it and creates a list of everything below "allowed ids".

The last thing starting is a thread, which parses all new blocks of the chain and looks for new records of the account. If there is a new record, script parses it, repeats all the cycle and obtains an acl.

### 2. Action logger - store device logs in blockchain
*Record actions and their statuses and send those to blockchain to prove that a specific device has done some action. Supports `str`.*

1) Create a config dictionary (either parse `.yaml` file or whatever)

Make sure to make it of form of `config.yaml` from this repository. `url: "ws://127.0.0.1:9944"` is for local or development robonomics node. If other, fill in with corresponding ws

2) In your script import action logger module and substrate connection module:

```from robonomics_daos_toolkit import action_logger, substrate_connection as subcon```
   
3) The best pattern to use this module is to initiate an instance of `action_logger.ActionLogger` class in the beginning and then refer to its `log_action` method every time you need to save information in the blockchain.

Example:
```python
if config["use_daos_toolkit"]:
    substrate = subcon.substrate_connection(config["daos_toolkit"]["substrate"])
    if config["daos_toolkit"]["use_action_logger"]:
        # initiate an instance of action logger
        logging.info("initiating ActionLogger class")
        action_logger = action_logger.ActionLogger(config['daos_toolkit'], substrate)
        if not action_logger:
            logging.critical("ActionLogger instance error, exiting")
            sys.exit()
        else:
            logging.info("ActionLogger initiated")
```
It parses DT object, prepares logging dictionary, establishes necessary connections

4) Launch IPFS

```bash
ipfs daemon
```

5) Optionally add Pinata credentials, if you want your log to be visible fast and worldwide.

6) When need to log some action, use
```python
if config["daos_toolkit"]["use_action_logger"]:
    action_logger.log_action(action: str, status: str)
```
to form a dictionary of form:
```python
action:
  description: action
  status: status
  timestamp: 2021.07.13-19:37:38
```
push it to IPFS, optionally, Pinata, and save hash in blockchain

#### How it works
When created an instance of ActionLogger, the script looks for the [Digital Twin](https://wiki.robonomics.network/docs/en/digital-twins/) map to see, if the provided mnemonic seed corresponds to the device account specified in DT.
This template is proposed to use:
```json
{
  "dt":{
    "acl_____________________________":"<acl_host_address_in_suubstrate>",#if acl is used
    "device__________________________":"<device_address_in_suubstrate>"
  }
}   
```
More on account [here](https://wiki.robonomics.network/docs/en/create-account-in-dapp/). It is better to use mnemonic seed of the exact same `<device_address_in_suubstrate>` as in DT.
Later, when user calls `log_action` method, a dictionary is filled in, saved as `.yaml` and sent to IPFS/Pinata. The IPFS hash is stored in Robonomics via extrinsic `Datalog.record`. 
To sign this extrinsic a  mnemonic seed is used. Interacting with Substrate blockchain is possible with https://github.com/polkascan/py-substrate-interface