<!-- generated from operations.xml by xmldocs: do not edit, edit the XML -->

## The site operations over REST and MCP
*Instruction booklet · booklet/operations · 2026-10-29*

### Purpose

How a program or an agent works on Kajenn Press sites through the 52 site operations, the same ones the administration and Help me use: how to call them, what each needs, and what it answers.

### Requirements

- A websites installation with site sources; `capabilities` says which parts are configured (`sites`, `publishing`, `rendering`) and lists the operations.
- A bearer token of an identity with the `editor` tag and grants on the sites (`read`, `write`, `create_site`, `build`, `publish`).

#### 1. Call an operation

Every operation is a route of one application on the websites root, reachable two ways with the same arguments:

- REST: `POST /<operation>` with a JSON object of arguments.
- MCP: `POST /mcp`, JSON-RPC `tools/call` with `name` the operation and `arguments` the same object; `tools/list` lists them.

Both answer `{"ok": true, "result": …}` or `{"ok": false, "error": {"code", "message", …}}`. Over REST the error codes map to HTTP statuses: `unauthenticated` 401, `forbidden` 403, `not_found` 404, `conflict` 409, `unavailable` 503, any other 422.

**Example — Add a content over REST**

```bash
curl -s -X POST https://kpress.example/content_add \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"site_id": "…", "key": "intro-1", "name": "Intro", "format": "html", "text": "<p>Hello</p>"}'
```

#### 2. Hold the site while changing it

Changes go to the caller's working copy of the site and need its editing lock: `site_open` takes the site (`force` takes it from another holder), `site_save` writes the working copy as a new S3 version of the source, `site_close` releases it. The lock expires after 30 minutes without changes.

Every change carries an idempotency `key` chosen by the caller: repeating a call with the same key and the same arguments returns the first result without running it again; the same key with other arguments is refused. Keys are kept 24 hours.

#### 3. The operations

Every operation except `site_list`, `starters_list`, `site_new` and `site_import` also takes `site_id`. "Lock" says whether the caller must hold the site; "Key" whether the call takes an idempotency key.

*Reading the site*

| Operation | Arguments | Permission | Lock | Key | What it does |
|---|---|---|---|---|---|
| `copies_update_plan` | original\_id | read | no | no | Copies of an original, with differences and what Update would select. |
| `page_check` | page\_id | read | no | no | Empty slots and unplaced contents of a page. |
| `page_render` | page\_id, language | build | no | no | Static HTML of a page in a language (main by default), rendered in the worker; slots shown in the main language for lack of a translation carry kpress\_fallback. |
| `seo_check` | page\_id | read | no | no | SEO problems of one page or of the whole site: titles, descriptions, alt, links. |
| `site_export` | version\_id | read | no | no | A saved version of the site as one zip, in base64. |
| `site_read` | — | read | no | no | Templates, contents with use counts, assets, pages and the holder. |
| `site_versions` | — | read | no | no | S3 versions of the site source, oldest first. |
| `template_switch_plan` | page\_id, template\_id | read | no | no | Proposed slot mapping, by name, for a page switching template. |

*Editing (working copy)*

| Operation | Arguments | Permission | Lock | Key | What it does |
|---|---|---|---|---|---|
| `asset_add` | name, kind, data\_base64, mime\_type | write | yes | yes | Add a CSS, JavaScript or media asset. |
| `content_add` | name, format, text | write | yes | yes | Add an HTML or Markdown content. |
| `content_save` | content\_id, text | write | yes | yes | Replace the text of a content; page copies change only through copies\_update. |
| `content_translate` | content\_id, language, text, proposed | write | yes | yes | Write the translation of a content into one of the site's other languages. |
| `copies_update` | original\_id, selected | write | yes | yes | Replace the selected copies, given as [page\_id, path], with the original. |
| `folder_add` | name, parent | write | yes | yes | Add a logical folder to the Pages tree. |
| `page_add` | name, template\_id | write | yes | yes | Add a page with a copy of a site template. |
| `page_alt_set` | page\_id, image, alt | write | yes | yes | Set the alt text of one image in this page's copy (a local change of the copy). |
| `page_asset_add` | page\_id, asset\_id | write | yes | yes | Copy an asset into a page. |
| `page_seo_set` | page\_id, fields, language | write | yes | yes | Set SEO fields of a page, in the main language or another one; an empty value clears the field (root page: site defaults). |
| `page_url_set` | page\_id, url, language | write | yes | yes | Move a page to a new URL path, in the main language or another one (without its prefix); the old path redirects to it. |
| `site_languages_set` | languages | write | yes | yes | Set the site's languages (BCP 47 tags such as it, en), main language first. |
| `site_text_set` | name, text, language, proposed | write | yes | yes | Set a template text of the site (such as a menu label), main language by default; templates read it as ^texts.<name>. |
| `slot_assign` | page\_id, slot, content\_id | write | yes | yes | Copy a content into a slot of a page. |
| `template_add` | name, engine, source, python\_source | write | yes | yes | Add a template (engine gramlot or htmlbuilder): a plain Source in TYTX JSON, or Python build code defining build(source, data). |
| `template_switch` | page\_id, template\_id, mapping | write | yes | yes | Switch a page's template with the confirmed slot mapping. |
| `translation_confirm` | translation, language | write | yes | yes | Confirm a translation proposed by Help me (translation: content\_<id> or text\_<name>). |
| `tree_move` | item\_id, parent, position | write | yes | yes | Move a page or folder in the Pages tree (drag and drop). |
| `unplaced_place` | page\_id, copy\_id, slot | write | yes | yes | Move an unplaced content copy into a free slot. |

*Editing session*

| Operation | Arguments | Permission | Lock | Key | What it does |
|---|---|---|---|---|---|
| `site_close` | — | write | yes | no | Release the site. |
| `site_open` | force | write | takes it | no | Take the site for editing; force takes it from another holder. |
| `site_restore` | version\_id | write | yes | no | Make an older version current again, as a new version. |
| `site_save` | — | write | yes | no | Save the working copy as a new S3 version. |

*Sites and Library*

| Operation | Arguments | Permission | Lock | Key | What it does |
|---|---|---|---|---|---|
| `site_import` | data\_base64, name | create\_site | no | yes | A new site from an exported zip; the importer holds it. |
| `site_list` | — | read (filters) | no | no | Sites with a source the caller can read, and who holds each. |
| `site_new` | name, starter\_id | create\_site | no | yes | Create a site source, empty or from a starting site; the creator holds it. |
| `starter_save` | name | library write, site read | no | yes | Keep the latest saved version of a site in the Library as a starting site. |
| `starters_list` | — | library read | no | no | Starting sites in the Library. |

*Publication*

| Operation | Arguments | Permission | Lock | Key | What it does |
|---|---|---|---|---|---|
| `maintenance_set` | on | publish, write | yes | yes | Put the published site in maintenance (503) or take it out. |
| `page_rollback` | page\_id, version\_id | publish, write | yes | yes | Put an earlier published version of a page online. |
| `page_versions` | page\_id | publish | no | no | Published versions of a page, oldest first, with the one online marked. |
| `private_link` | hours | publish | no | no | A link that shows the real site while private or in maintenance (8 or 168 hours). |
| `publication_state` | — | publish | no | no | Address, public or private, maintenance, last Publish and pages changed since. |
| `publish` | selected | publish, write | yes | yes | Save the source and publish the selected pages; the site index is written last. |
| `publish_plan` | — | publish | no | no | Pages changed since the last publication, selected, with their warnings. |
| `site_rollback` | version\_id | publish, write | yes | yes | Restore a source version and publish the whole site from it. |
| `site_visibility_set` | state | publish, write | yes | yes | Make the site public or private at its address (the root page's public origin). |
| `site_server_set` | server, alias | publish, write | yes | yes | Choose the registered server that serves the site; with alias, the other name (with or without `www.`) answers 301 to the address. |
| `dns_plan` | — | publish | no | no | The A and AAAA records to create for the address and its alias, towards the server's addresses. |
| `dns_check` | — | publish | no | no | What public resolvers (1.1.1.1, 8.8.8.8) answer for each record: ok, missing, wrong or unknown. |
| `site_go_live` | — | publish, write | yes | yes | Check the DNS records, publish, ask the server's agent to serve the address and obtain its certificate, then check the address; reports each step. |

*Servers*

| Operation | Arguments | Permission | Lock | Key | What it does |
|---|---|---|---|---|---|
| `server_list` | — | any principal | no | no | The registered servers with their addresses and agent URL. |
| `server_add` | name, ipv4, ipv6, agent\_url | servers (installation) | no | yes | Register a server; the agent URL is https, or http on the loopback. |
| `server_remove` | name | servers (installation) | no | yes | Remove a server that serves no site. |

### Rules

- **must** — Use a new key for every distinct change and the same key when retrying it. *(A repeated call is recognised by its key.)*
- **must** — Save before closing or leaving a site for long. *(Other holders' changes are lost when a site is taken.)*
- **should** — Read `publish_plan` before `publish`. *(The plan names exactly what changed and what is wrong.)*

### Current limits

- One holder edits a site at a time; there is no merge of concurrent changes. · `src/kajenn_press/site/service.py:107`

### Verified facts

- `TEST` `src/kajenn_press/site/service.py:107` · 2026-10-29 — The operations are the union of READS, CHANGES, CONTROLS, LIBRARY, PUBLISHING and SERVERS: 52, each a route of `PressApplication` (`tests/site/test_site_service.py`).
- `READ` `src/kajenn_press/application.py:18` · 2026-10-29 — REST maps `unauthenticated`, `forbidden`, `not_found`, `conflict`, `unavailable` to 401, 403, 404, 409, 503 and other errors to 422.
- `TEST` `tests/api/support.py:49` · 2026-10-29 — REST calls are `POST /<operation>`; MCP calls are JSON-RPC `tools/call` on `/mcp`.
- `READ` `src/kajenn_press/site/receipts.py:24` · 2026-10-29 — Idempotency receipts are kept 24 hours.
- `READ` `src/kajenn_press/site/lock.py:15` · 2026-10-29 — The editing lock expires after 30 minutes.

### Related documents

- `booklet/site-tab`
- `booklet/publication`
