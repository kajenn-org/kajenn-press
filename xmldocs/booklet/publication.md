<!-- generated from publication.xml by xmldocs: do not edit, edit the XML -->

## Publication and serving
*Instruction booklet · booklet/publication · 2026-10-29*

### Purpose

What Publish writes to the release bucket, how a site server reads it and answers visitors, how a site goes live on a registered server, and how rollback, maintenance, private sites and private links work.

### Requirements

- A release bucket with S3 versioning, written by websites and read by site servers with read-only keys.
- The site's root page with a public origin: it is the site's address.

#### 1. What Publish writes

Publish renders each selected page in each selected language and writes one zip object per page and language, then the site index, then the bindings. Every write is a new S3 version: nothing is overwritten in place.

*Objects in the release bucket*

| Key | Content |
|---|---|
| `sites/<site>/pages/<page>.zip` | The page in the main language. |
| `sites/<site>/pages/<page>.<language>.zip` | The page in another language. |
| `sites/<site>/index.json` | The site index: for every page and language, its URL, object key, the S3 version online, fingerprint, assets, refresh time, whether it is indexable and its language; the redirects; maintenance. |
| `bindings.json` | Public origin → site id, state (public or private), server, and for an alias the address it redirects to; for every site. |

A page object holds `page.json` (the page Bag, URL, fingerprint, the SHA-256 of the HTML, language), `index.html` (the pre-rendered page), its assets by content address, and for a page whose Data uses resolvers `request.json`, the render request without connections. The index is written after the pages and pins their versions, so a reader never sees half a publication.

A page is selected when its fingerprint differs from the one online: name, URL, the page as its language sees it, effective SEO, site texts and the site's languages. A translation changes only its own language.

#### 2. How a site server answers

A site server reads `bindings.json` and each site's index at most every cache interval, keeping the last valid ones, so a new address or a new publication needs no restart. For a request it finds the site by origin, then:

1. a private site answers 404 and a site in maintenance 503, unless the browser holds the cookie of a valid private link;
2. `/robots.txt` and `/sitemap.xml` come from the index; the sitemap lists every indexable page in every language; a root page that is not indexable closes the whole site to robots;
3. a redirect source answers 301 to its target, a path without its final slash 301 to the slashed one, a path with the main language's prefix 301 to the path without it;
4. `/_assets/<sha256>.<ext>` answers the asset with an immutable cache header;
5. a page URL answers its HTML; a page with resolvers is rendered again by the worker when its refresh time has passed and kept in a local cache;
6. anything else answers the 404 page of the path's language, else the main one.

A site server serves only the origins bound to its own name (`SITE_SERVER_NAME`, default `default`); an alias answers 301 to the address with the same path. `/_kpress/ask?domain=<name>` answers 200 only for a name bound to it: Caddy asks it before obtaining a certificate on demand.

Public pages carry no cookie and no session; only the private link sets one.

#### 3. Go live on a registered server

Servers are registered in `servers.json` of the source bucket by name, IPv4 and IPv6 addresses and agent URL (`server_add`, grant `servers`). A server runs a site server and the server agent behind nginx, Caddy or Traefik; the agent is a small service with four actions (`domain_add`, `domain_remove`, `domain_status`, `proxy_reload`), a bearer token per server and an allow-list of client addresses.

1. `site_server_set` chooses the server; with `alias`, the other name answers 301 to the address.
2. `dns_plan` lists the A and AAAA records to create; `dns_check` reads them through 1.1.1.1 and 8.8.8.8.
3. `site_go_live` checks the records, publishes, calls `domain_add` on the agent, which configures the proxy and obtains the certificate, then checks the address. It stops at the first failed step and reports each one.

The same steps move a site to another server: the binding names the new server, and the old one stops serving it at its next read of `bindings.json`.

*What the agent does per proxy*

| Proxy | Configuration | Certificate |
|---|---|---|
| nginx | One server block per site in the agent's directory; `nginx -t` and reload. | `certbot certonly --webroot`. |
| Caddy | None: the binding is the configuration. | On demand, after the `ask` endpoint. |
| Traefik | One file per site in the file provider's directory. | The configured certificate resolver. |

#### 4. Roll back

- **A page in one language**: `page_rollback` pins an earlier S3 version of its object in a new index; the other pages and languages stay as they are.
- **The whole site**: `site_rollback` restores a saved source version and publishes every page that differs from it.

#### 5. Maintenance, private sites and private links

`maintenance_set` writes a new index with the maintenance flag; pages stay as they are. `site_visibility_set` makes the site private or public at its address, even before the first Publish.

`private_link` returns `<address>/_private/<token>`, valid 8 hours or 7 days. The token names the site and its expiry and is signed with HMAC-SHA256 under a secret shared by websites and the site servers. Opening it sets an HttpOnly cookie for that host (Secure on https, SameSite=Lax) and redirects to `/`; with it, the real site shows and its responses are not stored by shared caches. Rotating the secret revokes every link.

### Rules

- **must** — Give each site its own public origin. *(Publish refuses an address that belongs to another site.)*
- **must** — Give the site servers keys that can read object versions (`GetObjectVersion`, `ListBucketVersions`) and nothing else. *(Pages are read by pinned version.)*
- **should** — Give private links the shortest validity that serves. *(A link works until it expires and cannot be revoked one by one.)*

### Current limits

- An index of an earlier schema reads as absent: the next Publish writes every page again; until then the site server answers 503 for that site. · `src/kajenn_press/site/publish.py:81`
- A site server serves the sites of one release bucket.
- The agent runs the proxy commands through `sudo`, limited to the lines of `deploy/agent/sudoers-kpress-agent`.

### Verified facts

- `READ` `src/kajenn_press/site/published.py:27` · 2026-10-29 — The page object and index schema is 3; entries carry `language`.
- `TEST` `src/kajenn_press/site/publish.py:41` · 2026-10-29 — The main language's entry is the page id; another language's is `<page>.<language>`.
- `TEST` `src/kajenn_press/site/publish.py:236` · 2026-10-29 — Publish writes the pages, then the index, then the binding of the site's address.
- `TEST` `src/kajenn_press/site/published.py:50` · 2026-10-29 — A translation changes the fingerprint of its own language only.
- `TEST` `src/kajenn_press/site/serving.py:68` · 2026-10-29 — A running site server serves an address set after it started and stops serving the old one.
- `TEST` `src/kajenn_press/site/serving.py:272` · 2026-10-29 — The main language's prefixed path answers 301 to the unprefixed one.
- `TEST` `src/kajenn_press/site/serving.py:346` · 2026-10-29 — The sitemap lists indexable pages of every language; a noindex root gives `Disallow: /`.
- `TEST` `src/kajenn_press/site/private.py:35` · 2026-10-29 — Private links last 8 or 168 hours; forged, foreign and expired tokens are refused.
- `TEST` `src/kajenn_press/site/serving.py:224` · 2026-10-29 — A valid private link answers 303 with an HttpOnly cookie for its host.
- `TEST` `src/kajenn_press/site/serving.py:71` · 2026-10-29 — A site server serves only the origins bound to its name; moving a site to another server moves its serving.
- `TEST` `src/kajenn_press/site/golive.py:59` · 2026-10-29 — `site_go_live` reports dns, publish, certificate and online, and stops at the first failed step.
- `RUN` `tests/docker/test_proxies_contract.py:1` · 2026-10-29 — Caddy with its internal CA obtains a certificate on demand only for a name the site server binds; nginx accepts the agent's block; Traefik loads the agent's router.
- `RUN` `tests/docker/test_docker_composition_contract.py:1` · 2026-10-29 — The Docker composition publishes the example site in two languages, serves it, and opens it through a private link during maintenance.

### Related documents

- `booklet/site-tab`
- `booklet/operations`
