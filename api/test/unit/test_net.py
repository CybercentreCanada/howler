from howler.common.net import (
    is_ip_in_network,
    is_valid_domain,
    is_valid_email,
    is_valid_ip,
    is_valid_port,
)


def test_port_check():
    assert is_valid_port(1)
    assert is_valid_port(2**16 - 1)
    assert is_valid_port("1")
    assert is_valid_port(str(2**16 - 1))
    assert is_valid_port(1.0)

    assert not is_valid_port(0)
    assert not is_valid_port(-1)
    assert not is_valid_port(2**16)
    assert not is_valid_port("PORT")


def test_valid_domain():
    assert is_valid_domain("cyber.gc.ca")
    assert not is_valid_domain("user@cyber.gc.ca")
    assert not is_valid_domain("user")


def test_valid_domain_iana_special_use():
    """Test IANA Special-Use Domain Names Registry entries.

    See: https://www.iana.org/assignments/special-use-domain-names/
    """
    assert is_valid_domain("server.local")
    assert is_valid_domain("server.local", allow_special_use_tlds=True)
    assert not is_valid_domain("server.local", allow_special_use_tlds=False)


def test_valid_domain_private_suffixes():
    """Test common private network suffixes.

    These are NOT IANA-registered but are widely used organizational conventions.
    They are accepted by default but can be rejected with allow_private_suffixes=False.
    """
    assert is_valid_domain("server.internal")
    assert not is_valid_domain("server.internal", allow_private_suffixes=False)


def test_valid_domain_public_only():
    """Test public internet domain validation.

    Setting both allow_special_use_tlds=False and allow_private_suffixes=False
    validates only IANA-registered public TLDs, useful for SSRF protection.
    """
    # Public internet domains
    assert is_valid_domain(
        "cyber.gc.ca", allow_special_use_tlds=False, allow_private_suffixes=False
    )
    assert is_valid_domain(
        "example.com", allow_special_use_tlds=False, allow_private_suffixes=False
    )

    # IANA special-use TLDs - rejected
    assert not is_valid_domain(
        "server.local", allow_special_use_tlds=False, allow_private_suffixes=False
    )
    assert not is_valid_domain(
        "hidden.onion", allow_special_use_tlds=False, allow_private_suffixes=False
    )

    # Private network suffixes - rejected
    assert not is_valid_domain(
        "server.internal", allow_special_use_tlds=False, allow_private_suffixes=False
    )


def test_valid_ip():
    assert is_valid_ip("5.5.5.5")
    assert not is_valid_ip("5,5.5.5")
    assert not is_valid_ip("5.S.5.5")
    assert not is_valid_ip("5.5.5")
    assert not is_valid_ip("5..5.5")
    assert not is_valid_ip("5.5.5.5.5")
    assert not is_valid_ip("0.5.5.5")
    assert not is_valid_ip("5.256.5.5")
    assert not is_valid_ip("5.5.-1.5")
    assert is_valid_ip("5.0.5.5")
    assert is_valid_ip("5.5.0.5")
    assert not is_valid_ip("5.5.5.0")


def test_valid_email():
    # TODO these tests are correct, but our is_valid_email code is lax
    assert is_valid_email("user@cyber.gc.ca")
    #     assert not is_valid_email('@cyber.gc.ca')
    #     assert not is_valid_email('user@')
    #     assert not is_valid_email('user@cyber')
    #     assert not is_valid_email('user@cy#ber.gc.ca')
    assert is_valid_email("user.name@cyber.gc.ca")
    #     assert not is_valid_email('user..name@cyber.gc.ca')
    assert is_valid_email("u#ser@cyber.gc.ca")
    assert is_valid_email('"u#ser"@cyber.gc.ca')
    assert is_valid_email('"user..name"@cyber.gc.ca')


def test_is_ip_in_network():
    from ipaddress import ip_network

    assert not is_ip_in_network("1...1", ip_network("2.0.0.0/24"))
    assert not is_ip_in_network("1.1.1.1", ip_network("2.0.0.0/24"))
    assert is_ip_in_network("2.2.2.2", ip_network("2.0.0.0/8"))
