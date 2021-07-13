import ipfshttpclient
import logging
import pathlib
import sys
import typing as tp
import yaml

from datetime import datetime as dt
from pinatapy import PinataPy
from scalecodec import ScaleBytes
from substrateinterface import Keypair

from os import remove, path


# set up logging
logging.basicConfig(
    level=logging.INFO,
    filename="daemon.log",
    format="%(asctime)s %(levelname)s: %(message)s",
)


class ActionLogger:

    def __init__(self, config: tp.Dict[str, tp.Any], substrate_g) -> None:
        """
        Creates a template dictionary with timestamp, action description  and status. This dictionary is to be
        updated later. Also connects to pinata if required.

        @param config: global configuration dictionary
        @param substrate_g: object representing connection to substrate
        """

        logging.info("Initializing action logger")
        self.config = config
        self.path = pathlib.Path().resolve()
        logging.info("Initializing substrate connection")
        self.substrate = substrate_g
        # Add key
        self.keypair = Keypair.create_from_mnemonic(config["device_account_mnemonic"], ss58_format=32)
        self._check_if_mnemonic_of_device()

        if config["action_logger"]["use_pinata"]:
            pinata_api = self.config["action_logger"]["pinata"]["api"]
            pinata_secret_api = self.config["action_logger"]["pinata"]["secret_api"]
            if pinata_api and pinata_secret_api:
                self.pinata = PinataPy(pinata_api, pinata_secret_api)
            else:
                logging.error("No pinata api data passed")
                sys.exit()

        self.action_log: tp.Dict = {
            "action": {
                "description": "",
                "status": "",
                "timestamp": ""
            },
        }
        self.log_hash: str = ""
        self.timestamp: str = ""
        logging.info("Initialized action log")

    def log_action(self, action: str, status: str) -> None:
        """
        Fill in metadata fields: action description and status

        @param action: action description. What action is to be logged
        @param status: action status
        """

        try:
            if not isinstance(action, str) or not isinstance(status, str):
                logging.warning(
                    f"Fields types are not \"str\"! Type(action): {type(action)}; Type(status): {type(status)}")
            self.action_log["action"]["description"] = action
            self.action_log["action"]["status"] = status
            self.timestamp = dt.now().strftime("%Y.%m.%d-%H:%M:%S")
            self.action_log["action"]["timestamp"] = self.timestamp
            logging.info("Updated log with action description and its status")
        except Exception as e:
            logging.error(f"Failed to update action and status. Error: {e}")
            pass

        # save log
        self._save_log()

        # clean dict
        self.action_log: tp.Dict = {
            "action": {
                "description": "",
                "status": "",
                "timestamp": ""
            },
        }

    def _save_log(self) -> None:
        """save a YAML log; push it to local IPFS; pinata, if required; remove; send hash to Robonomics"""

        # save YAML file
        try:
            log_file = open(f"{self.path}/log_{self.timestamp}.yaml", "w")
            yaml.dump(self.action_log, log_file)
            logging.info("YAML session log saved")
        except Exception as e:
            logging.error(f"Failed to save log file. Error: {e}")
            log_file.close()
            pass

        # push log to ipfs
        try:
            ipfs_client = ipfshttpclient.connect()
            res = ipfs_client.add(f"{self.path}/log_{self.timestamp}.yaml")
            self.log_hash = res["Hash"]
            log_file.close()
            logging.info(f"Log pushed to IPFS. Hash is {self.log_hash}")
        except Exception as e:
            logging.error(f"Failed to push file to local IPFS node. Error: {e}")
            log_file.close()

        # pinning file to pinata
        if self.config["action_logger"]["use_pinata"]:
            try:
                self.pinata.pin_file_to_ipfs(f"{self.path}/log_{self.timestamp}.yaml")
                self.log_hash = self.pinata.pin_list()["rows"][0]["ipfs_pin_hash"]
                logging.info(f"Log sent to pinata. Hash is {self.log_hash}")
            except Exception as e:
                logging.error(f"Failed to pin file to Pinata. Error: {e}")

        # remove log file to save space
        try:
            remove(f"./log_{self.timestamp}.yaml")
            logging.info("Log file removed")
        except Exception as e:
            logging.error(f"Failed to remove log file: {e}")

        # pushing hash to robonomics
        try:
            logging.info("Creating substrate call")
            call = self.substrate.compose_call(
                call_module="Datalog",
                call_function="record",
                call_params={
                    'record': self.log_hash
                }
            )
            logging.info(f"Successfully created a call:\n{call}")
            logging.info("Creating extrinsic")
            extrinsic = self.substrate.create_signed_extrinsic(call=call, keypair=self.keypair)
            logging.info("Submitting extrinsic")
        except Exception as e:
            logging.error(f"Failed to create a call: {e}")
            pass

        try:
            receipt = self.substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
            logging.info(f"Extrinsic {receipt.extrinsic_hash} sent and included in block {receipt.extrinsic_hash}")
        except Exception as e:
            logging.error(f"Failed to send: {e}")

    def _check_if_mnemonic_of_device(self) -> bool:
        """

        check if mnemonic seed corresponds to device account address, specified in Digital Twin. Provide warnings.
        @return: true or false if mnemonic seed corresponds device address or not (failed to check)

        """

        try:
            logging.info("Checking mnemonics seed correspondence to account address in DT")
            digital_twin = self.substrate.query("DigitalTwin", "DigitalTwin", [self.config["dt_id"]])
            dt_map: tp.List = digital_twin.value
            logging.info(f"Fetched DT map.\n{dt_map}")
            if not dt_map:
                logging.warning(f"No DT map for this DT or no DT. Can't check correspondence")
                return False
        except Exception as E:
            logging.warning(f"Failed to fetch DT map. Can't check correspondence. Error:\n {E}")
            return False

        # since topic names in robonomics are represented as bytes (of wtf ScaleBytes is), create corresponding number
        device_topic_h256 = str(ScaleBytes(self.config["device_topic_name"].encode("utf-8")))
        addr = None
        for i in range(len(dt_map)):
            if dt_map[i][0] == device_topic_h256:
                addr = dt_map[i][1]

        if not addr:
            logging.warning(f"No topic {device_topic_h256} found in DT. Can't check correspondence")
            return False

        logging.info(f"Device address from DT is {addr}")
        logging.info(f"Mnemonic seed address: {self.keypair.ss58_address}")
        # Compare addresses
        if self.keypair.ss58_address == addr:
            logging.info("Mnemonic seed address corresponds with device address in DT")
            return True
        else:
            logging.warning("Mnemonic seed address doesn't correspond with device address in DT")
            return False


if __name__ == "__main__":

    import substrate_connection as subcon

    if not path.exists("config.yaml"):
        logging.error("config.yaml not found")

    with open("config.yaml", "r") as file:
        try:
            config_g = yaml.safe_load(file)
        except Exception as Err:
            logging.error(f"Error loading config.yaml: {Err}")
    substrate = subcon.substrate_connection(config_g["daos_toolkit"]["substrate"])
    action_logger = ActionLogger(config_g["daos_toolkit"], substrate)
    action_logger.log_action("action1", "status1")
