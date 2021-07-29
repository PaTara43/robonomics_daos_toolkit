import logging
import sys
import threading
import typing as tp

# set up logging
logging.basicConfig(
    level=logging.INFO,
    filename="daemon.log",
    format="%(asctime)s %(levelname)s: %(message)s",
)


class ACL:
    """
    stores ACL values and holds usage_allowed method. Updates ACL as hew hash is uploaded via datalog from an
    address specified in DT mapping
    """

    def __init__(self, config: tp.Dict[str, tp.Any], substrate) -> None:
        """
        Create an instance of a class, set its acl attribute as a list of allowed addresses and start a daemon,
        handling updates in datalog of the acl holder address

        Parameters
        ----------
        config : configuration dict to work with robonomics
        substrate: object representing connection to substrate
        """

        logging.info("initializing ACL instance")
        # connect to substrate node with specified parameters
        self.config = config
        self.substrate = substrate
        self.acl_host_addr: str = cu.get_topic_addr(self.substrate,
                                                    self.config["dt_id"], self.config["acl"]["acl_topic_name"]
                                                    )
        if not self.acl_host_addr:
            sys.exit()

        # The following three functions are to be used in daemon, so they are not exiting if something's wrong,
        # exiting conditions are so defined here, in init script
        self.acl_hash: str = cu.get_latest_datalog(self.substrate, self.acl_host_addr)
        self.acl_f: str = cu.fetch_file_from_ipfs(self.acl_hash, "acl.yaml")
        self.acl: tp.List[str] = cu.read_yaml_file(self.acl_f)["allowed_ids"]
        if not self.acl:
            logging.error(f"No acl or acl empty, exiting...")
            sys.exit()

        logging.info(f"Initialized acl instance. ACL: \n{self.acl}")
        # stat datalog updates handler
        logging.info("Starting datalog update daemon")
        subscriber = threading.Thread(target=self._datalog_subscriber)
        subscriber.start()

    def _datalog_subscriber(self):
        """
        Tread func to subscribe to datalog updates
        more: https://github.com/polkascan/py-substrate-interface#storage-subscriptions
        """

        try:
            self.substrate.query("Datalog", "DatalogIndex", [self.acl_host_addr],
                                 subscription_handler=self._handle_datalog_updates)
        except Exception as e:
            logging.error(f"Daemon exited. {e}")

    def _handle_datalog_updates(self, datalog_obj, update_nr, subscription_id):
        """
        Process updates in account datalog records number: Read new latest datalog and obtain ACL
        more: https://github.com/polkascan/py-substrate-interface#storage-subscriptions
        """

        if update_nr != 0:  # called not when subscriber is created
            logging.info(f"New record in datalog")
            self.acl_hash: str = cu.get_latest_datalog(self.substrate, self.acl_host_addr)
            self.acl_f: str = cu.fetch_file_from_ipfs(self.acl_hash, "acl.yaml")
            new_acl: tp.List[str] = cu.read_yaml_file(self.acl_f)["allowed_ids"]
            if not new_acl:
                logging.error(f"ACL not updated. Got None. Keeping old ACL \n{self.acl}")
            else:
                self.acl = new_acl
                logging.info(f"Updated ACL. New ACL is: \n {self.acl}")

        else:
            pass

    def usage_allowed(self, user_id: str) -> bool:
        """
        check, if certain ID is allowed to use the machine by the policy

        Parameters
        ----------
        user_id : ID (address) to be checked if on the allow list
        """

        return user_id in self.acl


if __name__ == "__main__":

    import common_utils as cu

    config = cu.read_yaml_file("config.yaml")["daos_toolkit"]
    substrate = cu.substrate_connection(config["substrate"])

    acl_obj = ACL(config, substrate)
    print(acl_obj.acl)
else:
    from robonomics_daos_toolkit import common_utils as cu
