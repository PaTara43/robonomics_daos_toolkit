import logging
import typing as tp

from datetime import datetime as dt

# set up logging
logging.basicConfig(
    level=logging.INFO,
    filename="daemon.log",
    format="%(asctime)s %(levelname)s: %(message)s",
)


class ActionLogger:

    def __init__(self, config: tp.Dict[str, tp.Any], substrate) -> None:
        """
        Creates a template dictionary with timestamp, action description  and status. This dictionary is to be
        updated later. Also connects to pinata if required.

        @param config: global configuration dictionary
        @param substrate: object representing connection to substrate
        """

        logging.info("Initializing action logger")
        self.config = config
        self.substrate = substrate
        self.action_log: tp.Dict = {
            "action": {
                "description": "",
                "status": "",
                "timestamp": ""
            },
        }
        self.log_hash: str = ""
        self.timestamp: str = ""
        # Check if seed and device account address from DT correspond
        logging.info("Check correspondence of seed and address")
        device_addr = cu.get_topic_addr(self.substrate, self.config["dt_id"], self.config["device_topic_name"])
        if cu.seed_to_account_corresponding(self.config["device_account_mnemonic"], device_addr):
            logging.info("Seed corresponds to account from DT topic " + self.config["device_topic_name"])
        else:
            logging.warning("Seed doesn't correspond to account from DT topic " + self.config["device_topic_name"])

        logging.info("Initialized action logger")

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
        log_file = cu.write_yaml_file(self.action_log, f"log_{self.timestamp}.yaml")

        # push log to ipfs
        if self.config["action_logger"]["use_pinata"]:
            self.log_hash = cu.pin_file_in_ipfs(log_file, pinata_api=self.config["action_logger"]["pinata"]["api"],
                                                pinata_secret=self.config["action_logger"]["pinata"]["secret_api"],
                                                remove_after=True)
        else:
            self.log_hash = cu.pin_file_in_ipfs(log_file, remove_after=True)

        # pushing hash to robonomics
        if self.log_hash:
            cu.write_datalog(self.substrate, self.config["device_account_mnemonic"], self.log_hash)
        else:
            logging.error("Empty log_hash. Not sending to blockchain")


if __name__ == "__main__":

    import common_utils as cu

    config = cu.read_yaml_file("config.yaml")["daos_toolkit"]
    substrate = cu.substrate_connection(config["substrate"])

    action_logger = ActionLogger(config, substrate)
    action_logger.log_action("action1", "status1")

    addr = cu.get_topic_addr(substrate, config["dt_id"], config["device_topic_name"])
    hash = cu.get_latest_datalog(substrate, addr)  # go to IPFS gateway and see record of action1 status1
    print(hash)

else:
    from robonomics_daos_toolkit import common_utils as cu
