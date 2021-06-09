# Robonomics DAOS toolkit
### Toolkit for interacting with devices within DAOS. Get ACL from blockchain, log sessions (coming in future) and perform transactions to control devices in a smart office (coming in future).

*Note: the entire communication is based on substrate blockchain, in particular, [Robonomics](https://robonomics.network/) platform*
These modules are mostly based on using a thing called Digital Twin. More about them in Robonomics one may find [here](https://wiki.robonomics.network/docs/en/digital-twins/).

Requirements:
- [Robonomics binary](https://github.com/airalab/robonomics/releases) (tested fine on 0.29)
- [IPFS v0.6.0](https://dist.ipfs.io/go-ipfs/v0.6.0/go-ipfs_v0.6.0_linux-arm.tar.gz)
- Rust-nightly ([here](https://www.rust-lang.org/tools/install) and [here](https://doc.rust-lang.org/edition-guide/rust-2018/rustup-for-managing-rust-versions.html))
- Digital Twin for your devices
- ```pip3 install -r requirements.txt```

## Main modules
### ACL - Access Control List
*Grant access to devices for those IDs only, which are presented in a blockchain-confirmed list*
1) Create a config dictionary (either parse `.yaml` file or whatever)

Make sure to make it of form of `config.yaml` from this repository. `url: "ws://127.0.0.1:9944"` is for local or development robonomics node. If other, fill in with corresponding IP

2) In your script import acl module:

```from robonomics-daos-toolkit.acl import ACL```
   
3) The best pattern to use this module is to initiate an instance of `ACL` class in the beginning and then refer to its `acl` attribute every time you need to check whether ID is on the list.

Example:
```python
acl_obj = ACL(config["robonomics"])
allow_list = acl_obj.acl
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

After creating a Digital Twin You have assigned specific topics to specific addresses in Robonomics network, which datalog may be read.
Datalog of each account may be read by calling some functions of py-substrate-interface. 

When starting the script, it looks for Digital Twin with a config-described ID, parses its topics, looks for the topic as it's named in config, takes the last record of the corresponding account datalog with an IPFS hash and downloads it. If it's a yaml file, script parses it and creates a list of everything under "allowed ids".

The last thing starting is a thread, which parses all new blocks of the chain and looks for new records of the account. If there is a new record, script parses it, repeats all the cycle and obtains an acl.
