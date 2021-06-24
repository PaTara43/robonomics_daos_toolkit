import ipfshttpclient
import logging
import sys
import threading
import time
import typing as tp
import yaml

from os import path, rename
from scalecodec import ScaleBytes

# set up logging
logging.basicConfig(
    level=logging.DEBUG,
    filename="daemon.log",
    format="%(asctime)s %(levelname)s: %(message)s",
)


class ACL:
    """
    stores ACL values and holds usage_allowed method. Updates ACL as hew hash is uploaded via datalog from an
    address specified in DT mapping
    """

    def __init__(self, config: tp.Dict[str, tp.Any]) -> None:
        """
        Create an instance of a class, set its acl attribute as a list of allowed addresses and start a daemon,
        handling updates in datalog of the acl holder address

        Parameters
        ----------
        config : configuration dict to work with robonomics
        """

        logging.info("initializing ACL instance")
        # connect to substrate node with specified parameters
        self.substrate = subcon.substrate_connection(config["substrate"])
        self.acl_host_addr: str = self._get_acl_host_addr(
            config["acl"]["dt_id"], config["acl"]["acl_topic_name"]
        )

        # The following three functions are to be used in daemon, so they are not exiting if something's wrong,
        # exiting conditions are so defined here, in init script
        self.acl_hash: str = self._get_acl_hash()
        self.acl_f: str = self._fetch_acl()
        self.acl: tp.List[str] = self._read_acl_f()
        if not self.acl:
            logging.error(f"No acl or acl empty, exiting...")
            sys.exit()

        logging.info("initialized acl instance")
        # stat datalog updates handler
        self.datalog_updates_handler = threading.Thread(
            target=self._handle_datalog_updates
        )
        self.datalog_updates_handler.start()
        logging.info("Started datalog update daemon")

    def _get_acl_host_addr(self, dt_id: int, acl_topic_name: str) -> str:
        """
        Find a host address, which datalog stores IPFS hash of an acl. Address is specified in Digital Twin

        Parameters
        ----------
        dt_id : digital twin id of a device
        acl_topic_name : topic name, where the address for obtaining acl is stored

        Returns
        -------
        address in robonomics network, which datalog is to be used for retrieving IPFS hash of an acl
        """

        try:
            digital_twin = self.substrate.query("DigitalTwin", "DigitalTwin", [dt_id])
            dt_map = digital_twin.value
            logging.info(f"Fetched DT map.\n{dt_map}")
        except Exception as E:
            logging.error(f"Failed to fetch DT map. Exiting. Error:\n {E}")
            sys.exit()

        # since topic names in robonomics are represented as bytes (of wtf ScaleBytes is), create corresponding number
        acl_topic_h256 = str(ScaleBytes(acl_topic_name.encode("utf-8")))
        addr = None
        for i in range(len(dt_map)):
            if dt_map[i][0] == acl_topic_h256:
                addr = dt_map[i][1]
        if not addr:
            logging.critical(f"No topic {acl_topic_name} found in DT. Exiting")
            sys.exit()
        logging.info(f"Acl host address is {addr}")
        return addr

    def _get_acl_hash(self) -> str:
        """
        get an IPFS hash of the acl file from host address latest datalog. If no IPFS hash in datalog, exit

        Returns
        -------
        IPFS hash of an acl file. None if failure
        """

        try:
            # Get all records
            datalog = self.substrate.query_map("Datalog", "DatalogItem")
            addr_datalog = []

            # Find only host address datalogs
            for i in datalog.records:
                addr_datalog.append(i[1].value) if i[0].value[0] == self.acl_host_addr else None
            # Sort them by timestamp
            addr_datalog_sorted = sorted(addr_datalog, key=lambda log: log["timestamp"])
            logging.info(f"All records of this account:\n{addr_datalog_sorted}")
            hash = addr_datalog_sorted[-1]["payload"]
            logging.info(f"Latest record: {hash}")

            if "Qm" not in hash:
                logging.critical(f"No IPFS hash found in {self.acl_host_addr} datalog")
                hash = None
        except Exception as E:
            logging.error(f"Failed to fetch hash from acl host datalog. Error:\n {E}")
            hash = None

        return hash

    def _fetch_acl(self) -> str:
        """
        Fetch file from IPFS

        Returns
        -------
        acl filename. None if failure
        """

        # initial check if there is a hash
        if not self.acl_hash:
            return ""
        try:
            logging.info("Connecting to IPFS")
            client = ipfshttpclient.connect()
            name = "acl.yaml"
            logging.info("Fetching acl file")

            client.get(self.acl_hash)
            logging.info("Successfully fetched acl file")
            client.close()
            rename(self.acl_hash, name)
            return name
        except Exception as E:
            logging.error(f"Failed to fetch acl file. Error {E}")
            client.close()
            return ""

    def _read_acl_f(self) -> tp.List[str]:
        """
        load up an acl

        Returns
        -------
        List with every allowed ID. None if failure
        """

        # initial check if there is a file
        if self.acl_f == "" or not path.exists(self.acl_f):
            logging.error(f"acl file {self.acl_f} not found")
            return []
        logging.info(f"Acl file: {self.acl_f}")

        with open(self.acl_f, "r") as r_file:
            try:
                acl = yaml.safe_load(r_file)["allowed_ids"]
                print(acl)
                return acl
                # return yaml.safe_load(r_file)["allowed_ids"]
            except Exception as E:
                logging.error(f"Error loading acl: {E}")
                return []

    def _handle_datalog_updates(self):
        """
        monitor events in network and parse them to find new records in datalog. If so, update acl
        """

        while True:
            ch = self.substrate.get_chain_head()
            # print(f"Chain head: {ch}")

            events = self.substrate.get_events(ch)
            for e in events:
                if e.value["event_id"] == "NewRecord":
                    for p in e.params:
                        if (
                            p["type"] == "AccountId"
                            and p["value"] == self.acl_host_addr
                        ):
                            self.acl_hash: str = self._get_acl_hash()
                            self.acl_f: str = self._fetch_acl()
                            acl_new: tp.List[str] = self._read_acl_f()
                            if not acl_new:
                                logging.error(
                                    f"No acl or acl empty, keeping old acl..."
                                )
                            else:
                                self.acl = acl_new
                                time.sleep(1)

            time.sleep(1.9)

    def usage_allowed(self, user_id: str) -> bool:
        """
        check, if certain ID is allowed to use the machine by the policy

        Parameters
        ----------
        user_id : ID (address) to be checked if on the allow list
        """

        return user_id in self.acl


if __name__ == "__main__":

    """load up the configuration file"""

    import substrate_connection as subcon

    if not path.exists("config.yaml"):
        logging.error("config.yaml not found")

    with open("config.yaml", "r") as file:
        try:
            config_g = yaml.safe_load(file)
        except Exception as Err:
            logging.error(f"Error loading config.yaml: {Err}")

    acl_obj = ACL(config_g["robonomics"])
    print(acl_obj.acl)
else:
    from robonomics_daos_toolkit import substrate_connection as subcon
