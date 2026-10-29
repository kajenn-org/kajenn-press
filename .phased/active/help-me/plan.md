# Context: feat/help-me
Parent: main
Mode: manual
Must not break: The full suite (two interpreters, RustFS endpoint), the admin suite and the Docker suite keep passing; no test calls the Claude API unless an explicit opt-in variable is set.
Must not break: The decisions of `xmldocs/proposal/site-tab-redesign.xml` are not reopened (d-help-budget: information only; d-editing-lock: Help me works under the lock of the user who opened it; d-audit-minimal: Help me actions recorded as the user's, through Help me; d-idempotency-keep).
Must not break: Publishing stays an operator command: Help me has no Publish, rollback, maintenance, visibility or private link tool.
Must not break: The API key never reaches Bags, zips, logs, git, responses or the browser.
Must not break: Gramlot constitution: Source, Data, bindings and components; no imperative DOM manipulation. Sibling repositories are not edited.
Must not break: Every UI phase is checked in a real browser (Browser pane) against its approved mockup before it is closed.

## Objective

A Help me button in the site tab opens a chat beside the Visual editor. Sonnet interviews the operator, offers palettes, type pairs and SVG logo sketches as clickable choices, and builds the site through the site operations: templates, contents, assets, pages, slots, SEO, save. The result is ordinary site material, editable by hand. The conversation is kept per site and can be resumed. Tokens and cost show per chat and per site, for information only.

Entry: main `7ded265`; the 41 site operations of `SiteService`; `Site.record(..., via="help_me")` already exists; no Anthropic SDK in the dependencies.

Known API facts (Claude API reference, cached 2026-10-06): model `claude-sonnet-5-5`; $2 input, $10 output per million tokens, cache reads $0.20; thinking cannot be disabled (`between_tools` turns it off between tool calls); forced `tool_choice` returns 400 (only `auto`); thinking blocks are bound to the conversation, so the stored history must be append-only and keep each response's full content; refusals come back as `stop_reason: "refusal"` and the server-side fallback (`fallbacks: "default"`, beta) is recommended by default.

## Owner decisions (2026-10-29): all recommended options chosen; mockup `mockups/help-me.html` approved

- **N8-D1 · How Sonnet reaches the site.** (a) In process: the chat loop runs in websites and calls `SiteService.execute` with the operator's identity, the same operations and argument schemas as MCP; every change is audited `via="help_me"` and needs the operator's lock. (b) Through the MCP endpoint over HTTP with a token. Decided: (a); same operations, no token to manage.
- **N8-D2 · Which operations Sonnet gets.** (a) Reads, the editing changes (templates, contents, assets, pages, folders, slots, copies, SEO, alt texts) and `site_save`; no Publish, rollback, maintenance, visibility, private link, restore, site creation or deletion. (b) All of them. Decided: (a).
- **N8-D3 · Where conversations are kept.** (a) One JSON object per chat in the source bucket, `sites/<id>/help/<chat>.json`, outside the source zip: it does not grow site versions and it survives restores. (b) A section of the site Bag, inside every source version. Decided: (a).
- **N8-D4 · Choices.** (a) A tool `offer_choices` (palettes as colour lists, type pairs from a fixed list of system font stacks, SVG sketches); the tab renders them as cards and a click sends the choice as the next message. Fonts: system stacks only in this macro, because site pages allow fonts from their own origin only and no font files ship with Kajenn Press. (b) Also web fonts, which needs font files as site assets and a licence check. Decided: (a).
- **N8-D5 · SVG.** (a) Every SVG from Sonnet is cleaned before it becomes an asset or a preview: no `script`, `foreignObject`, event attributes, external references or `javascript:` URLs; previews render as `img` with a `data:` URL, which never runs scripts. (b) Stored as written. Decided: (a); published assets are served from the site's own origin.
- **N8-D6 · A turn in the browser.** (a) One call per message: the server runs the whole tool loop and answers when the turn ends; the chat shows "working" meanwhile and the Visual editor refreshes after. (b) Streaming with server-sent events. Decided: (a) now, (b) later if turns are long.
- **N8-D7 · Model settings (decided).** `claude-sonnet-5-5`, effort `medium`, adaptive thinking, prompt caching on the system prompt and tool list, server-side fallback `default` on refusal. The key comes from a secret file (`ANTHROPIC_API_KEY_FILE`); without it the Help me button says Help me is not configured.

## Decisions shared by all phases

- Tests use a scripted client in place of the Anthropic client (the API is an external dependency); one live test runs only with `KAJENN_HELP_LIVE=1` and costs real tokens, so it runs once, with the owner's go-ahead.
- New operations follow the naming of N3 and are listed at the gate of the phase that adds them.
- Each phase ends with its tests green, a browser check for UI phases, ruff clean on changed files, one commit on `feat/help-me`. Phases run back to back without confirmation between them; the run stops only at a gate, a blocker or the end.
- Every phase runs on Opus, never Fable.

## Work Plan

- [ ] **Phase 1**: Tools from the site operations
  - Files: a new `src/kajenn_press/help/tools.py`, `src/kajenn_press/site/service.py`, `tests/help/`.
  - Details: per N8-D1 and N8-D2: tool definitions (name, description, JSON schema with `strict`) built from the allowed operations; execution through `SiteService.execute` with the operator identity, an idempotency key per tool call, and the audit marked `via="help_me"`; errors returned as `is_error` tool results in the words of the service.
  - Done: every allowed operation has a tool whose schema matches its arguments; publishing operations have none; a change made through a tool is audited as the user's via Help me.

- [ ] **Phase 2**: SVG cleaning and choices
  - Files: `src/kajenn_press/help/svg.py`, `tools.py`, `tests/help/`.
  - Details: per N8-D4 and N8-D5: `offer_choices` (palette, type pair, SVG sketch) and `svg_asset_add` (cleaned SVG as a media asset); the cleaner keeps shapes, paths, text, gradients and `viewBox`, and refuses what it removes from a logo only when nothing drawable is left.
  - Done: scripts, event attributes, `foreignObject`, external `href` and `javascript:` never survive; a clean sketch is unchanged.

- [ ] **Phase 3**: The chat loop and its store
  - Files: `src/kajenn_press/help/chat.py`, `src/kajenn_press/help/store.py`, `pyproject.toml` (extra `help` with the Anthropic SDK), `application.py`, `tests/help/`.
  - Details: per N8-D3, N8-D6 and N8-D7: manual tool loop (append each response's full content, run the tool calls, return all results in one user message, stop on `end_turn`, `refusal` or a step limit); usage and cost per response (input, output, cache write and read) summed per chat and per site; chats stored after every step; operations `help_chats`, `help_chat_read`, `help_send`.
  - Done: a scripted conversation creates a page with two contents, keeps an append-only history, reports tokens and cost, and resumes from the store.

- [ ] **Phase 4**: System prompt and live check
  - Files: `src/kajenn_press/help/prompt.py`, `tests/help/`.
  - Details: a stable system prompt (what Kajenn Press is, slots and copies, SEO, what Help me may not do, ask before large changes, offer choices as cards) placed before the cache breakpoint; one live test with `KAJENN_HELP_LIVE=1`.
  - Done: the live test builds a two-page site from one request, with the owner's go-ahead for its cost.

- [ ] **Phase 5**: The Help me pane
  - Files: `src/kajenn_press/admin/pages/site.py`, `site.js`, `site.css`, `tests/admin/`.
  - Details: per the approved mockup: Help me button, chat pane at the right of the Visual editor, choice cards, actions list, chat list and New chat, tokens and cost per chat and per site; the Visual editor refreshes after each turn.
  - Done: matches the mockup in the browser with a scripted client; a live turn from the tab after the owner's go-ahead.

- [ ] **Phase 6**: Configuration and documentation
  - Files: `deploy/docker/websites.py`, `compose.yaml`, `compose.external-s3.yaml`, `HETZNER.md`, `README.md`, `deploy/docker/README.md`, `deploy/docker/requirements-websites.txt`.
  - Details: `ANTHROPIC_API_KEY_FILE` read from a secret provided by the owner, never generated; Hetzner step for the key; the websites requirements with hashes for the SDK.
  - Done: full, admin and Docker suites green; without the key the button says Help me is not configured.
