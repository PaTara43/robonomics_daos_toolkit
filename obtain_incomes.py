import logging
import threading
import typing as tp

# set up logging
logging.basicConfig(
    level=logging.INFO,
    filename="daemon.log",
    format="%(asctime)s %(levelname)s: %(message)s",
)


class IncomeTracker:

    def __init__(self, config: tp.Dict[str, tp.Any], substrate):
        logging.info("Creating an instance of an IncomeTracker class")
        self.config = config
        self.substrate = substrate

        logging.info(f"Fetching device address from Digital Twin map")
        self.device_addr: str = cu.get_topic_addr(self.substrate,
                                                  self.config["dt_id"],
                                                  self.config["device_topic_name"])
        self.income_threshold = self.config["income_tracker"]["income_threshold"]
        logging.info(f"Device address is {self.device_addr}. Income threshold is {self.income_threshold} XRT")
        self.income_threshold *= 10 ** 12  # XRT with 12 decimals

        logging.info(f"Initiating new blocks subscriber for incomes obtaining")
        self.money_income_event = threading.Event()

        self.subscriber = threading.Thread(target=self._obtain_incomes)
        self.subscriber.start()

        logging.info("Block subscriber started. Waiting for money incomes")

    def _subscription_handler(self, obj, update_nr, subscription_id):
        """
        parse block events and trigger python Event on money income more than threshold to a device account

        params info:
        https://github.com/polkascan/py-substrate-interface/blob/65f247f129016f5bb3a9a572579033f35fd385ea/substrateinterface/base.py#L2588
        """
        ch: str = self.substrate.get_chain_head()
        chain_events = self.substrate.get_events(ch)
        for ce in chain_events:
            if ce.value["event_id"] == "Transfer" and \
                    ce.params[1]["value"] == self.device_addr:
                if ce.params[2]["value"] >= self.income_threshold:
                    self.money_income_event.source_address = ce.params[0]['value']
                    self.money_income_event.amount = ce.params[2]["value"]

                    logging.info(
                        f"New transaction from {self.money_income_event.source_address}. "
                        f"Amount: {round(self.money_income_event.amount / 10 ** 12, 2)} XRT")
                    self.money_income_event.set()  # trigger python Event in main loop
                else:
                    logging.info(f"Too small income. No money - no job.")


    def _obtain_incomes(self):
        """
        Subscribe to new block headers as soon as they are available. The callable `subscription_handler` will be
        executed when a new block is available and execution will block until `subscription_handler` will return
        a result other than `None`
        """

        self.substrate.subscribe_block_headers(self._subscription_handler)


if __name__ == '__main__':

    import common_utils as cu

    config = cu.read_yaml_file("config.yaml")["daos_toolkit"]
    substrate = cu.substrate_connection(config["substrate"])

    income_tracker = IncomeTracker(config, substrate)

    print("Waiting for money income")
    while True:
        income_tracker.money_income_event.wait()
        income_tracker.money_income_event.clear()
        print(f"Made coffee for {income_tracker.money_income_event.source_address}. "
              f"Got {round(income_tracker.money_income_event.amount / 10 ** 12, 2)} XRT")

else:
    from robonomics_daos_toolkit import common_utils as cu
