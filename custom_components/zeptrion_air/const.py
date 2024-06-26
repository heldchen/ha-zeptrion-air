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