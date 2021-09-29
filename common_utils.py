import ipfshttpclient
import logging
import typing as tp
import yaml

from os import path, rename, remove
from pinatapy import PinataPy
from substrateinterface import SubstrateInterface, Keypair
from scalecodec import ScaleBytes

# set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)


def read_yaml_file(yaml_path: str) -> tp.Dict or None:
    """
    Read a yaml file

    Parameters
    ----------
    yaml_path : path to yaml file

    Returns
    -------
    yaml file contains as dictionary
    """
    logging.info(f"Reading .yaml file {yaml_path}")
    if not path.exists(yaml_path):
        logging.error(f"{yaml_path} not found")
        return None

    with open(yaml_path, "r") as file:
        try:
            dictionary = yaml.safe_load(file)
            return dictionary
        except Exception as Err:
            logging.error(f"Error loading {yaml_path}: {Err}")
            return None


def write_yaml_file(dictionary: tp.Dict, name: str) -> str or None:
    """
    Save dictionary as a yaml file

    Parameters
    ----------
    dictionary : dictionary to be saved
    name : filename of .yaml. Must contain ".yaml"

    Returns
    -------
    filename of the new .yaml file
    """

    logging.info(f"Writing data to .yaml file {name}")
    try:
        yaml_file = open(f"{name}", "w")
        yaml.dump(dictionary, yaml_file)
        logging.info("YAML file saved")
        yaml_file.close()
        return name
    except Exception as e:
        logging.error(f"Failed to save dictionary to yaml file. Error: {e}")
        try:
            yaml_file.close()
        except Exception:
            pass
        return None


def substrate_connection(substrate_node_config: tp.Dict[str, tp.Any]) -> tp.Any:
    """
    establish connection to a specified substrate node
    """
    try:

        logging.info("Establishing connection to substrate node")
        substrate = SubstrateInterface(
            url=substrate_node_config["url"],
            ss58_format=32,
            type_registry_preset="substrate-node-template",
            type_registry={
                "types": {
                    "Record": "Vec<u8>",
                    "Parameter": "Bool",
                    "<T as frame_system::Config>::AccountId": "AccountId",
                    "RingBufferItem": {
                        "type": "struct",
                        "type_mapping": [
                            ["timestamp", "Compact<u64>"],
                            ["payload", "Vec<u8>"],
                        ],
                    },
                    "RingBufferIndex": {
                        "type": "struct",
                        "type_mapping": [
                            ["start", "Compact<u64>"],
                            ["end", "Compact<u64>"],
                        ],
                    }
                }
            },
        )
        logging.info("Successfully established connection to substrate node")
        return substrate
    except Exception as e:
        logging.error(f"Failed to connect to substrate: {e}")
        return None


def get_topic_addr(substrate, dt_id: int, topic_name: str) -> str or None:
    """
    Find address, corresponding to topic in Digital Twin

    Parameters
    ----------
    substrate: substrate connection instance
    dt_id : digital twin id of a device
    topic_name : topic name, where the address for obtaining acl is stored

    Returns
    -------
    address in robonomics network, which datalog is to be used for retrieving IPFS hash of an acl. None if no such topic
    """

    try:
        digital_twin = substrate.query("DigitalTwin", "DigitalTwin", [dt_id])
        dt_map = digital_twin.value
        logging.info(f"Fetched DT map.\n{dt_map}")
        if not dt_map:
            logging.error(f"No DT map for this DT or no DT.")
            return None
    except Exception as E:
        logging.error(f"Failed to fetch DT map. Error:\n {E}")
        return None

    # since topic names in robonomics are represented as bytes (of wtf ScaleBytes is), create corresponding number
    topic_h256 = str(ScaleBytes(topic_name.encode("utf-8")))
    addr = None
    for i in range(len(dt_map)):
        if dt_map[i][0] == topic_h256:
            addr = dt_map[i][1]
    if not addr:
        logging.critical(f"No topic {topic_name} found in DT.")
        return None
    logging.info(f"Topic {topic_name} host address is {addr}.")
    return addr


def get_latest_datalog(substrate, addr: str) -> str or None:
    """
    Fetch latest datalog record of a provided account
    Parameters
    ----------
    substrate : substrate connection object
    addr : ss58 address of an account which datalog is tp be fetched

    Returns
    -------
    String, the latest record of specified account
    """
    try:
        datalog_total_number: int = substrate.query("Datalog", "DatalogIndex", [addr]).value['end'] - 1
        datalog: str = substrate.query("Datalog", "DatalogItem", [[addr, datalog_total_number]]).value["payload"]
        return datalog

    except Exception as e:
        logging.error(f"Error fetching latest datalog:\n{e}")
        return None


def seed_to_account_corresponding(seed: str, addr: str) -> bool:
    """
    Check if provided seed and address are a pair

    Parameters
    ----------
    seed : account seed
    addr : account address

    Returns
    -------
    Corresponds or not
    """
    try:
        logging.info("Checking correspondence of account seed and address from topic in digital twin")
        keypair = Keypair.create_from_mnemonic(seed, ss58_format=32)
    except Exception as e:
        logging.error(f"Failed to create keypair. Can't check correspondence: \n{e}")
        return False

    return addr == keypair.ss58_address


def write_datalog(substrate, seed: str, data: str) -> str or None:
    """
    Write any string to datalog

    Parameters
    ----------
    substrate : substrate connection instance
    seed : mnemonic seed of account which writes datalog
    data : data tp be stored as datalog

    Returns
    -------
    Hash of the datalog transaction
    """

    # create keypair
    try:
        keypair = Keypair.create_from_mnemonic(seed, ss58_format=32)
    except Exception as e:
        logging.error(f"Failed to create keypair for recording datalog: \n{e}")
        return None

    try:
        logging.info("Creating substrate call for recording datalog")
        call = substrate.compose_call(
            call_module="Datalog",
            call_function="record",
            call_params={
                'record': data
            }
        )
        logging.info(f"Successfully created a call for recording datalog:\n{call}")
        logging.info("Creating extrinsic for recording datalog")
        extrinsic = substrate.create_signed_extrinsic(call=call, keypair=keypair)
    except Exception as e:
        logging.error(f"Failed to create an extrinsic for recording datalog: {e}")
        return None

    try:
        logging.info("Submitting extrinsic for recording datalog")
        receipt = substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
        logging.info(f"Extrinsic {receipt.extrinsic_hash} for recording datalog sent and included "
                     f"in block {receipt.block_hash}")
        return receipt.extrinsic_hash
    except Exception as e:
        logging.error(f"Failed to submit extrinsic for recording datalog: {e}")
        return None


def send_launch(substrate, seed: str, target_address: str, on_off: bool) -> str or None:
    """
    Send Launch command to device

    Parameters
    ----------
    substrate : substrate connection instance
    seed : mnemonic seed of account which writes datalog
    target_address: device to be triggered with launch
    on_off : (true == on, false == off)

    Returns
    -------
    Hash of the datalog transaction if success
    """

    # create keypair
    try:
        keypair = Keypair.create_from_mnemonic(seed, ss58_format=32)
    except Exception as e:
        logging.error(f"Failed to create keypair for sending launch: \n{e}")
        return None

    try:
        logging.info("Creating substrate call for sending launch")
        call = substrate.compose_call(
            call_module="Launch",
            call_function="launch",
            call_params={
                'robot': target_address,
                'param': True if on_off else False
            }
        )
        logging.info(f"Successfully created a call for sending launch:\n{call}")
        logging.info("Creating extrinsic for sending launch")
        extrinsic = substrate.create_signed_extrinsic(call=call, keypair=keypair)
    except Exception as e:
        logging.error(f"Failed to create an extrinsic for sending launch: {e}")
        return None

    try:
        logging.info("Submitting extrinsic for sending launch")
        receipt = substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
        logging.info(f"Extrinsic {receipt.extrinsic_hash} for sending launch sent and included in block {receipt.extrinsic_hash}")
        return receipt.extrinsic_hash
    except Exception as e:
        logging.error(f"Failed to submit extrinsic for sending launch: {e}")
        return None


def fetch_file_from_ipfs(hash: str, name: str) -> str or None:
    """
    Fetch file from IPFS by its hash

    Parameters
    ----------
    hash : IPFS hash of a file
    name : name to be assigned to the fetched file

    Returns
    -------
    absolute path to the file
    """

    try:
        if "Qm" not in hash:
            logging.error(f"Not an IPFS hash passed as an argument")
            return None
        logging.info("Connecting to IPFS")
        client = ipfshttpclient.connect()
        logging.info("Fetching file")
        client.get(hash)
        logging.info("Successfully fetched acl file")
        client.close()
        rename(hash, name)
        return name
    except Exception as E:
        logging.error(f"Failed to fetch file. Error {E}")
        client.close()
        return None


def pin_file_in_ipfs(filepath: str, pinata_api=None, pinata_secret=None, remove_after=True) -> str or None:
    """
    push file to IPFS and pin it in Pinata if credential given. Then remove the file

    Parameters
    ----------
    remove_after : remove file after pinning to save space or not
    pinata_api : (str or None) pinata api
    pinata_secret : (str or None) pinata secret
    filepath : path to file to be pinned

    Returns
    -------
    IPFS hash of a pinned file
    """

    try:
        logging.info(f"Pushing file {filepath} to IPFS")
        ipfs_client = ipfshttpclient.connect()
        res = ipfs_client.add(filepath)
        hash = res["Hash"]
        ipfs_client.close()
        logging.info(f"File pushed to IPFS. Hash is {hash}")
    except Exception as e:
        logging.error(f"Failed to push file to local IPFS node. Error: {e}")
        hash = None
        try:
            ipfs_client.close()
        except Exception:
            pass

    if pinata_api and pinata_secret:
        try:
            logging.info("Pinning file to Pinata")
            pinata = PinataPy(pinata_api, pinata_secret)
            pinata.pin_file_to_ipfs(filepath)
            hash = pinata.pin_list()["rows"][0]["ipfs_pin_hash"]
            logging.info(f"File sent to pinata. Hash is {hash}")
        except Exception as e:
            logging.error(f"Failed to pin file to Pinata. Error: {e}")
            pass

    if remove_after:
        try:
            remove(filepath)
            logging.info("File removed")
        except Exception as e:
            logging.error(f"Failed to remove file: {e}")

    return hash


if __name__ == "__main__":
    # test yaml reading
    config = read_yaml_file("config.yaml")["daos_toolkit"]

    # test substrate connection
    substrate = substrate_connection(config["substrate"])

    # test fetching yaml contains from digital twin specified account datalog
    addr = get_topic_addr(substrate, config["dt_id"], config["acl"]["acl_topic_name"])
    print(f"Address from DT topic: {addr}")
    datalog = get_latest_datalog(substrate, addr)
    print(f"Datalog of address {addr} : {datalog}")
    filepath = fetch_file_from_ipfs(datalog, 'acl.yaml')
    print(f"File, fetched from ipfs: {filepath}")
    yaml_contains = read_yaml_file(filepath)
    print(f".yaml contains: {yaml_contains}")

    # test pinning dictionary data to IPFS
    new_filepath = write_yaml_file({"abc": "bca"}, "sample_yaml.yaml")
    print(f"Saved dictionary .yaml: {new_filepath}")
    hash = pin_file_in_ipfs(new_filepath, pinata_api=config["action_logger"]["pinata"]["api"],
                            pinata_secret=config["action_logger"]["pinata"]["secret_api"])
    print(f"Pinned file hash: {hash}")

    # test sending IPFS hash to blockchain as datalog of Digital Twin specified account
    device_addr = get_topic_addr(substrate, config["dt_id"], config["device_topic_name"])
    print(f"Device address from DT topic: {device_addr}")
    corresponds = seed_to_account_corresponding(config["device_account_mnemonic"], device_addr)
    print(f"Device address corresponds seed: {corresponds}")
    tr_hash = write_datalog(substrate, config["device_account_mnemonic"], hash)
    print(f"Sent datalog transaction hash: {tr_hash}")
    device_written_datalog = get_latest_datalog(substrate, device_addr)
    print(f"Recently written datalog: {device_written_datalog}")

    # test sending launch command to device
    sent_launch_hash = send_launch(substrate, config["device_account_mnemonic"],
                                   '5CApRpWX6LFX8u5bT8k9azogrMPF6FBmb6sVR3tLVnfp449D', True)
    print(sent_launch_hash)
