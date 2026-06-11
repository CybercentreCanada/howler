import socket
import uuid
from ipaddress import IPv4Network, ip_address
from typing import Union

from howler.common.net_static import TLDS_ALPHA_BY_DOMAIN

# Special-use TLDs per RFC 6761 and RFC 7686
# These are reserved by IANA for specific purposes and not in the standard TLD list
SPECIAL_USE_TLDS = {
    "LOCAL",      # RFC 6762 - mDNS/Bonjour local network names
    "LOCALHOST",  # RFC 6761 - loopback address
    "TEST",       # RFC 6761 - testing
    "EXAMPLE",    # RFC 6761 - documentation examples
    "INVALID",    # RFC 6761 - invalid domain names
    "ONION",      # RFC 7686 - Tor hidden services
    "INTERNAL",   # Common internal network TLD
    "LAN",        # Common internal network TLD
    "HOME",       # Common internal network TLD
    "CORP",       # Common internal network TLD
    "LOCALDOMAIN",  # Common internal network TLD
}


def is_valid_port(value: Union[int, str, float]) -> bool:
    "Check if a port is valid"
    try:
        if 1 <= int(value) <= 65535:
            return True
    except ValueError:
        pass

    return False


def is_valid_domain(domain: str) -> bool:
    "Check if a domain is valid"
    if "@" in domain:
        return False

    if "." in domain:
        tld = domain.split(".")[-1].upper()
        return tld in TLDS_ALPHA_BY_DOMAIN or tld in SPECIAL_USE_TLDS

    return False


def is_valid_ip(ip: str) -> bool:
    "Check if an ip is valid"
    parts = ip.split(".")
    if len(parts) == 4:
        for p in parts:
            try:
                if not (0 <= int(p) <= 255):
                    return False
            except ValueError:
                return False

        if int(parts[0]) == 0:
            return False

        if int(parts[3]) == 0:
            return False

        return True

    return False


def is_ip_in_network(ip: str, network: IPv4Network) -> bool:
    "Check if an ip is in a given network"
    if not is_valid_ip(ip):
        return False

    return ip_address(ip) in network


def is_valid_email(email: str) -> bool:
    "Check if an email is valid"
    parts = email.split("@")
    if len(parts) == 2:
        if is_valid_domain(parts[1]):
            return True

    return False


def get_hostname() -> str:
    "Get the hostname of the computer howler is running on"
    return socket.gethostname()


def get_mac_address() -> str:
    "Get the mac address of the computer howler is running on"
    return "".join(["{0:02x}".format((uuid.getnode() >> i) & 0xFF) for i in range(0, 8 * 6, 8)][::-1]).upper()
