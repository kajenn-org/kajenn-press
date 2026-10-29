# Context: feat/languages
Parent: main
Mode: manual
Must not break: The full suite (two interpreters, RustFS endpoint), the admin suite and the Docker suite keep passing.
Must not break: The decisions of `xmldocs/proposal/site-tab-redesign.xml` are not reopened, the language decisions d-lang-* in particular.
Must not break: A site with one language behaves as today: same URLs, same published pages, same editor.
Must not break: Gramlot constitution: Source, Data, bindings and components; no imperative DOM manipulation. Sibling repositories are not edited.
Must not break: Every UI phase is checked in a real browser (Browser pane) against its approved mockup before it is closed.

## Objective

A site has a main language and may have others (proposal, section Languages). A page exists once; each content, the template's own texts and the SEO have one version per language; URLs carry the language as a prefix and the main language also answers without it; a missing translation shows the main text and is marked; a changed main text marks its translations to update; the editor works in one language at a time; Help me proposes translations to review; the published site has every language, `hreflang` and one sitemap.

Entry: main `1029f6d`. Inventory: no part of the code knows a language today. A content is one text (`Site.add_content`, `content_save`); a slot copy holds one text and one `original_digest` (`assign_content`, `update_plan`, `apply_update`); a page has one `url` and redirects are site-wide (`page_urls`, `set_page_url`); page data and the page section `seo` are single; `page_request` renders one page; Publish writes one object per page (`sites/<id>/pages/<page>.zip`) and one index entry per page (schema 2); the site server maps a path to one page; `head_html` writes no `hreflang`; the example layout hard-codes `lang="en"` and its menu texts.

## Owner decisions (2026-10-29): all recommended options chosen; mockup `mockups/languages.html` approved

- **N9-D1 · Where translations live.** (a) Each content keeps its main text as today and gains a `translations` Bag: one node per language with text, the digest of the main text it was made from, and `review` when Help me proposed it. Copies in pages carry the same Bag, so a page holds every language of its contents. (b) One content per language, linked by a common id. Decided: (a); copies, Update and the outdated marks keep working per language.
- **N9-D2 · The main language without prefix.** (a) The main language is served without prefix and that URL is canonical; `/<main>/…` answers 301 to it. (b) Both answer 200. Decided: (a); one URL per page and language, no duplicate content.
- **N9-D3 · Existing sites.** (a) A site without a language setting has one language, read from the root page's `lang` when its template sets one, else `en`; nothing else changes. (b) The operator is asked at the first opening. Decided: (a).
- **N9-D4 · Language codes.** (a) BCP 47 tags in lower case with optional region (`it`, `en`, `pt-br`), at most 8 languages per site. (b) Free strings. Decided: (a).
- **N9-D5 · Published objects.** (a) One object per page and language (`pages/<page>.<lang>.zip`), one index entry per page and language (schema 3): rollback stays per page, now per page and language. (b) One object per page holding every language. Decided: (a); a translation published alone does not rewrite the other languages.

## Decisions shared by all phases

- New operations follow the naming of N3 and are listed at the gate of the phase that adds them.
- Each phase ends with its tests green, a browser check for UI phases, ruff clean on changed files, one commit on `feat/languages`. Phases run back to back without confirmation between them; the run stops only at a gate, a blocker or the end.
- A live Help me check costs tokens: it runs once, with the owner's go-ahead.
- Every phase runs on Opus, never Fable.

## Work Plan

- [x] **Phase 1**: Languages and translated texts in the site model
  > Done: `src/kajenn_press/site/languages.py`: site languages (info attribute `languages`, main first; without it the root template's `lang` or `en`, N9-D3), BCP 47 check, at most 8; the main language changes only before any translation; removing a language drops its translations. Translations live in the site section `translations` (`content_<id>`, `text_<name>` → language → text with `main_digest` and `review`); site texts (template texts, read as `^texts.<name>`) in the site section `texts`. Page copies of contents carry their translations in the page section `translations`; a changed translation makes the copy outdated and Update brings it along. States: missing, to_update, to_review, done. Operations `site_languages_set`, `content_translate`, `site_text_set`, `translation_confirm` (45 site operations); `site_read` returns languages, texts and translation states. Older sources get `texts` and `translations` sections on load; any other missing section still fails closed. Tests: `tests/site/test_languages.py` (11). Main suite: 203 passed, 11 skipped.
  - Files: `src/kajenn_press/site/model.py`, `service.py`, `application.py`, `storage.py`, `tests/site/`.
  - Details: per N9-D1, N9-D3 and N9-D4: site languages (main and others) and operation `site_languages_set`; content translations (`content_translate`, confirm of a proposed one); copies carry translations; per language states missing, to update (main digest changed), to review; Update brings translations along; page data (template texts) per language; `site_read` reports states per language.
  - Done: a two-language site shows missing, to update and to review correctly; a one-language site reads and saves as before.

- [x] **Phase 2**: URLs, redirects and SEO per language
  > Done: page section `languages` (language → URL and SEO fields); `language_url` (main without prefix, others `/<language>` + their URL or the main path), `site_urls`, `set_page_url(language)`; redirects stay full paths, so a changed English URL redirects only under `/en/` (`Site.redirect` shared with the main language); a main URL may not start with another language's prefix, and adding a language whose prefix a page uses is refused. SEO per language (`stored_seo`, `set_page_seo`, `effective_seo` with `language`): a field missing in a language takes the main value; root defaults per language; the origin stays one per site; `effective_seo` also returns `language` and `path`. `page_url_set` and `page_seo_set` take `language`; `site_read` returns `urls` and `seo_languages` per page. Deviation: `seo_check` stays in the main language: with the fallback, another language repeats the main findings. Tests: 2 more in `tests/site/test_languages.py`. Main suite: 205 passed, 11 skipped.
  - Files: `model.py`, `seo.py`, `service.py`, `application.py`, `tests/site/`.
  - Details: per d-lang-url and N9-D2: URL per page and language with the language prefix (main without prefix); redirects per language; SEO fields per language with root defaults per language; `seo_check` per language.
  - Done: URLs of every language are unique and stable; a changed URL redirects in its language only.

- [x] **Phase 3**: Rendering, publication and serving per language
  > Done: `page_request(language)`: slot texts from the page copy's translations, the main text where missing (listed in `fallback`, marked `kpress_fallback` in previews only), site texts as `^texts.<name>`, `^page.language`, SEO of that language, `hreflang` links (with `x-default`) when the site has several languages; the worker sets `html lang`. Schema 3: page objects and index entries carry `language`; the main language keeps the page id as entry and object name, every other language uses `<page id>.<language>`, so a one-language site publishes the same keys as before. `page_fingerprint(language)` sees only that language's translations and URL, so a translation changes only its language. Plan entries per page and language (`entry`, `language`); Publish takes page ids (every language) or entries (one language); rollback by entry. The site server answers `/<main>/…` with 301 to the unprefixed URL and the 404 page in the path's language when it exists. `page_render` takes `language`. An index of any earlier schema reads as absent for Publish. Tests: a two-language site published and served (`lang`, translations, main-text fallback, `hreflang`, 301, sitemap, a translation changing only its language, preview mark). Main suite: 206 passed, 11 skipped.
  - Files: `render.py`, `rendering/page.py`, `seo.py`, `publish.py`, `published.py`, `serving.py`, `tests/site/`, `tests/docker/`.
  - Details: per N9-D5: `page_request(lang)` (texts in that language, the main text where missing, `html lang`, `hreflang` links); one published object and index entry per page and language (schema 3, previous index replaced by the next Publish); the site server routes by prefix, 301 for the prefixed main language; one sitemap with every language.
  - Done: a two-language site is served in both languages with correct `lang`, `hreflang`, canonical and sitemap; a one-language site serves the same URLs as before.

- [ ] **Phase 4**: The editor in one language at a time
  - Files: `src/kajenn_press/admin/pages/site.py`, `site.js`, `site.css`, `tests/admin/`.
  - Details: per the approved mockup: language selector in the site bar; Visual editor, SEO tab and preview in the selected language; marks missing, to update and to review in the Pages and Contents trees; block editor with the main text beside the translation and Confirm translation; site languages in the SEO tab's site defaults.
  - Done: matches the mockup in the browser; a translation written in the tab shows in the preview of that language.

- [ ] **Phase 5**: Help me translates
  - Files: `src/kajenn_press/help/tools.py`, `prompt.py`, `tests/help/`.
  - Details: per d-lang-help: tools to propose a translation of a content or of page texts, always marked to review; the prompt explains languages; one live check with the owner's go-ahead.
  - Done: a scripted chat proposes translations that stay to review until confirmed; the live check translates one page.

- [ ] **Phase 6**: Example site, Docker and documentation
  - Files: `examples/kajenn_press_site/`, `tests/docker/`, `README.md`, `deploy/docker/README.md`.
  - Details: the example layout reads its menu texts and `lang` from page data; the example site gains Italian; the Docker test checks `/`, `/it/`, `hreflang` and the sitemap.
  - Done: full, admin and Docker suites green.
