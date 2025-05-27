"""Constants for zeptrion_air."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "zeptrion_air"
ATTRIBUTION = "Data provided by http://jsonplaceholder.typicode.com/"

CONF_NAME="name"
CONF_IP_ADDRESS = "ip_address"
CONF_PORT = "port"
CONF_HOSTNAME = "hostname"
CONF_TYPE = "type"
CONF_FIRMWARE = "firmware"

# Services
SERVICE_BLIND_UP_STEP = "blind_up_step"
SERVICE_BLIND_DOWN_STEP = "blind_down_step"
SERVICE_BLIND_RECALL_S1 = "blind_recall_s1"
SERVICE_BLIND_RECALL_S2 = "blind_recall_s2"
SERVICE_BLIND_RECALL_S3 = "blind_recall_s3"
SERVICE_BLIND_RECALL_S4 = "blind_recall_s4"

# Platforms
PLATFORMS = ["cover", "switch"] # Assuming switch might exist or be added later