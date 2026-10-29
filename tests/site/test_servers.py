"""The registry of servers (N7b Phase 1)."""

import pytest
from publication.storage_support import versioned_bucket

from kajenn_press.domain import AccessPolicy, DomainError
from kajenn_press.site.service import SiteService
from kajenn_press.site.store import SourceStore

GRANTS = {"root": {"*": ["read", "write", "servers"]}, "anna": {"*": ["read", "write"]}}


@pytest.fixture
def service(tmp_path):
    return SiteService(tmp_path / "s", SourceStore(versioned_bucket()), AccessPolicy(GRANTS))


def add(service, identity="root", key="w1", name="web-1", **extra):
    arguments = {
        "ipv4": ["157.90.1.20"],
        "ipv6": ["2a01:4f8::20"],
        "agent_url": "https://web-1.example:8890",
        **extra,
    }
    return service.execute(identity, "server_add", key=key, name=name, **arguments)


def test_servers_are_registered_listed_and_removed_with_the_servers_grant(service):
    assert add(service)["ipv6"] == ["2a01:4f8::20"]
    assert add(service, key="w1")["name"] == "web-1"  # same key: the first result
    listed = service.execute("anna", "server_list")
    assert listed == [
        {
            "name": "web-1",
            "ipv4": ["157.90.1.20"],
            "ipv6": ["2a01:4f8::20"],
            "agent_url": "https://web-1.example:8890",
        }
    ]
    with pytest.raises(DomainError):
        add(service, identity="anna", key="w2", name="web-2")
    service.execute("root", "server_remove", key="r1", name="web-1")
    assert service.execute("root", "server_list") == []


@pytest.mark.parametrize(
    "extra",
    [
        {"ipv4": ["300.1.1.1"]},
        {"ipv4": ["2a01:4f8::20"]},
        {"ipv4": [], "ipv6": []},
        {"agent_url": "http://web-1.example:8890"},
        {"agent_url": "ftp://web-1.example"},
    ],
)
def test_invalid_servers_are_refused(service, extra):
    with pytest.raises(DomainError):
        add(service, **extra)


def test_names_are_unique_and_lower_case(service):
    add(service)
    with pytest.raises(DomainError, match="exists"):
        add(service, key="w2")
    with pytest.raises(DomainError, match="lower case"):
        add(service, key="w3", name="Web 1")
    assert (
        add(service, key="w4", name="local", agent_url="http://127.0.0.1:8890")["name"] == "local"
    )
