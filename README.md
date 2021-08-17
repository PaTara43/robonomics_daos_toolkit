# Robonomics DAOS toolkit
### Toolkit for interacting with devices within DAOS. Get ACL from blockchain, log sessions, check incomes and perform transactions to control devices in a smart office.

*Note: the entire communication is based on substrate blockchain, in particular, [Robonomics](https://robonomics.network/) platform.
These modules are mostly based on using a thing called Digital Twin. More about them in Robonomics one may find [here](https://wiki.robonomics.network/docs/en/digital-twins/).*

Requirements:
- [Robonomics binary](https://github.com/airalab/robonomics/releases) (tested fine on 1.0)
- [IPFS v0.6.0](https://dist.ipfs.io/go-ipfs/v0.6.0/go-ipfs_v0.6.0_linux-arm.tar.gz)
- Rust-nightly ([here](https://www.rust-lang.org/tools/install) and [here](https://doc.rust-lang.org/edition-guide/rust-2018/rustup-for-managing-rust-versions.html))
- Digital Twin for your devices
- ```pip3 install -r requirements.txt```

### 1. Common utils - set of tools to facilitate device integration in Robonomics
*Read and write yaml, check datalogs, write datalogs, interact with ipfs and digital twins, send launch commands*

This set of functions contains the most widely used for working with Robonomics. Each method has a description, and a common testing script is executed when `common_utils.py` is called. For pinning in IPFS daemon is needed.

1) Launch IPFS daemon with 
    ```
    ipfs daemon
    ```

2) Launch [Robonomics](https://github.com/airalab/robonomics/releases/tag/v1.0.0) developer node. 
   Don't forget to add execution rights to the binary (skip this step if connecting to existing remote node).

    2.1) Download it:
    ```bash
    wget https://github.com/airalab/robonomics/releases/download/v1.0.0/robonomics-1.0.0-x86_64-unknown-linux-gnu.tar.gz
    tar -xvf robonomics-1.0.0-x86_64-unknown-linux-gnu.tar.gz
    rm robonomics-1.0.0-x86_64-unknown-linux-gnu.tar.gz 
    chmod +x robonomics
    ```
    2.2) Each time to run node execute:
    ```bash
    ./robononomics --dev --tmp
    ```
   This will launch a developer node not attached to any in network.


3) Go to [parachain.robonomics.network](parachain.robonomics.network) and 
   [create a digital twin](https://wiki.robonomics.network/docs/en/digital-twins/) 
   and topics for it with a specified addresses. 
   Push `any.yaml` file IPFS hash to corresponding 
   [account datalog](https://wiki.robonomics.network/docs/en/rio-datalog/)
   
4) Fill in `config.yaml`. It has comments!
   
5) Feel free to try any functions of `common_utils.py`!

### 2. ACL - Access Control List
*Grant access to devices for those IDs only, which are presented in a blockchain-confirmed list*
1) Steps 1-4 of Common Utils

2) Upload yaml file with acl to IPFS network. You may use local node, [Pinata](https://pinata.cloud/), etc.
   
Don't forget to make the uploaded file look like this for correct parsing:
```
allowed_ids:
  - '124567890'
```
   
3) In your script import acl module and common utils, create config dictionary and substrate instance

```python
from robonomics_daos_toolkit import acl, common_utils as cu

# load up configuration
config = cu.read_yaml_file("config.yaml")
```
   
4) The best pattern to use this module is to initiate an instance of `acl.ACL` class in the beginning and then refer 
   to its `usage_allowed` method every time you need to check whether ID is on the list.

Example:

```python
# initializing all daos tools
if config["use_daos_toolkit"]:

    if config["daos_toolkit"]["use_acl"]:
        # initiate an instance of ACL class based on digital twin of a device
        acl_obj = acl.ACL(config["daos_toolkit"], cu.substrate_connection(config["daos_toolkit"]["substrate"]))
        if not acl_obj:
            sys.exit()
            
<...>

if config["daos_toolkit"]["use_acl"]:
    # check if user is allowed to use the machine
    if not acl_obj.usage_allowed(<UID>):
        logging.warning(f"Usage declined.")
        continue
    else:
        logging.info(f"Usage allowed. Continuing.")
```
The script automatically looks for new records with datalogs (to be described below) so each time you refer to `usage_allowed` method, the acl is the most up-to-date one.

5) Launch your script or the existing `acl.py`

If everything is alright, you should see the contents of the `acl.yaml` file in logs.

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
Datalog of each account may be read by calling some functions of [py-substrate-interface](https://github.com/polkascan/py-substrate-interface). 

When starting the script, it looks for Digital Twin with a config-described ID, parses its topics, looks for the acl topic as it's named in config, takes the last record of the corresponding account datalog with an IPFS hash and downloads it. If it's a yaml file, script parses it and creates a list of everything below "allowed ids".

The last thing starting is a thread, which tracks new records of the account. If there is a new record, script parses it, repeats all the cycle and obtains an acl.

### 3. Action logger - store device logs in blockchain
*Record actions and their statuses and send those to blockchain to prove that a specific device has done some action. Supports `str`.*

1) Steps 1-4 of Common Utils. Optionally add Pinata credentials, if you want your log to be visible fast and worldwide.

2) In your script import action logger module and substrate connection module:

```python
from robonomics_daos_toolkit import action_logger, common_utils as cu

# load up configuration
config = cu.read_yaml_file("config.yaml")
```

3) The best pattern to use this module is to initiate an instance of `action_logger.ActionLogger` class in the beginning and then refer to its `log_action` method every time you need to save information in the blockchain.

Example:
```python
if config["use_daos_toolkit"]:

    if config["daos_toolkit"]["use_action_logger"]:
    # initiate an instance of action logger
    action_logger = action_logger.ActionLogger(config["daos_toolkit"],
                                               cu.substrate_connection(config["daos_toolkit"]["substrate"]))
    if not action_logger:
        sys.exit()

<...>

if config["daos_toolkit"]["use_action_logger"]:
    action_logger.log_action("Action", "Status")
```

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
Later, when user calls `log_action` method, a dictionary of form
```python
action:
  description: action
  status: status
  timestamp: 2021.07.13-19:37:38
```
is filled in, saved as `.yaml` and sent to IPFS/Pinata. The IPFS hash is stored in Robonomics via extrinsic `Datalog.record`. 
To sign this extrinsic a  mnemonic seed is used. Interacting with Substrate blockchain is possible with https://github.com/polkascan/py-substrate-interface

### 4. Obtain incomes - trigger Python Events on money income
*Each time there is a transaction to the device address with value more than a threshold - trigger Python Event*

1) Steps 2-4 of Common Utils

2) In your script import obtain_incomes module and substrate connection module:

```python
from robonomics_daos_toolkit import obtain_incomes, common_utils as cu

# load up configuration
config = cu.read_yaml_file("config.yaml")
substrate = cu.substrate_connection(config["daos_toolkit"]["substrate"])
```

3) Start IncomeTracker:

```python
income_tracker = obtain_incomes.IncomeTracker(config["daos_toolkit"], substrate)

while True:
    # wait for money income event
    income_tracker.money_income_event.wait()
    income_tracker.money_income_event.clear()
    print(f"From {income_tracker.money_income_event.source_address} "
          f"got {round(income_tracker.money_income_event.amount / 10 ** 12, 2)} XRT")
```

4) On [parachain.robonomics.network](https://parachain.robonomics.network/#/explorer) send transaction to device account. If the amount exceeds threshold - event is set. Log is printed.

5) Combine it with ACL and Action Logger and have fun!

#### How it works
When created an `IncomeTracker` instance, a thread is started, which parses events in every new block in the chain and if there is a Transaction event,
parses it to meet requirements of target address and income threshold. If met, triggers python event, returning source address and income amount.

