"""DNS records of a site's address and their check (N7b, d-dns, N7b-D3).

Kajenn Press shows the records to create (A and AAAA for the address and its alias,
towards the server's addresses) and checks them through public resolvers, so a record
cached by the manager's own resolver does not mislead.
"""

RESOLVERS = ("1.1.1.1", "8.8.8.8")


def host(origin):
    return origin.partition("://")[2].split(":")[0]


def dns_plan(origins, server):
    """Records to create: each name of the site, A to the IPv4 and AAAA to the IPv6."""
    return [
        {"name": host(origin), "type": kind, "value": value}
        for origin in origins
        for kind, values in (("A", server["ipv4"]), ("AAAA", server["ipv6"]))
        for value in values
    ]


def public_lookup(name, kind, nameserver):
    """What one public resolver answers; nothing for a missing name or record."""
    import dns.exception
    import dns.resolver

    resolver = dns.resolver.Resolver(configure=False)
    resolver.nameservers = [nameserver]
    resolver.lifetime = 5
    try:
        return sorted(str(answer) for answer in resolver.resolve(name, kind))
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
        return []
    except dns.exception.Timeout:
        return None


def dns_check(plan, lookup=public_lookup, resolvers=RESOLVERS):
    """Each name and type: expected values, what every resolver answers, and a state.

    The state is `ok` when every resolver answers exactly the expected values, `missing`
    when none answers anything, `unknown` when a resolver did not answer in time, else
    `wrong`.
    """
    expected = {}
    for record in plan:
        expected.setdefault((record["name"], record["type"]), []).append(record["value"])
    checks = []
    for (name, kind), values in expected.items():
        answers = {resolver: lookup(name, kind, resolver) for resolver in resolvers}
        if any(found is None for found in answers.values()):
            state = "unknown"
        elif all(sorted(found) == sorted(values) for found in answers.values()):
            state = "ok"
        elif not any(answers.values()):
            state = "missing"
        else:
            state = "wrong"
        checks.append(
            {
                "name": name,
                "type": kind,
                "expected": sorted(values),
                "answers": answers,
                "state": state,
            }
        )
    return {"records": checks, "ok": all(check["state"] == "ok" for check in checks)}
