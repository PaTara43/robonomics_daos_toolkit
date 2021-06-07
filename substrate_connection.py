import typing as tp
import logging
from substrateinterface import SubstrateInterface

# set up logging
logging.basicConfig(
    level=logging.INFO,
    filename="daemon.log",
    format="%(asctime)s %(levelname)s: %(message)s",
)


def substrate_connection(substrate_node_config: tp.Dict[str, tp.Any]) -> tp.Any:
    """
    establish connection to a specified substrate node
    """

    logging.info("Establishing connection to substrate node")
    substrate = SubstrateInterface(
        url=substrate_node_config["url"],
        ss58_format=32,
        type_registry_preset="substrate-node-template",
        type_registry={
            "types": {
                "Record": "Vec<u8>",
                "<T as frame_system::Config>::AccountId": "AccountId",
                "RingBufferItem": {
                    "type": "struct",
                    "type_mapping": [
                        ["timestamp", "Compact<u64>"],
                        ["payload", "Vec<u8>"],
                    ],
                },
            }
        },
    )
    logging.info("Successfully established connection to substrate node")
    return substrate
