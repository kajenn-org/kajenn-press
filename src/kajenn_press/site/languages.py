"""Languages of a site: the main language, the others, and translated texts (N9).

The first language of a site is its main language. Contents and site texts (the
template's own texts, such as menu labels) keep their main text where they are; each
other language has a translation in the site section `translations`, under the key
`content_<id>` or `text_<name>`, with the digest of the main text it was made from and
`review` when Help me proposed it (N9-D1). A translation is missing, to update (its main
text changed since), to review, or done.
"""

import re

from genro_bag import Bag

from ..domain import DomainError
from .model import value_digest
from .seo import ROOT_URL

CODE = re.compile(r"[a-z]{2,3}(-[a-z0-9]{2,8})?")
MAX_LANGUAGES = 8
TEXT_NAME = re.compile(r"[a-z][a-z0-9_]{0,63}")
DEFAULT_LANGUAGE = "en"


def root_language(site):
    """The `lang` of the root page's template, when it sets one (N9-D3)."""
    root = site.page_urls().get(ROOT_URL)
    if root is None:
        return None
    for _path, node in site.page(root).template.value.query("#p,#n", deep=True):
        if node.node_tag == "html" and isinstance(node.attr.get("lang"), str):
            return node.attr["lang"].lower()
    return None


def site_languages(site):
    """The languages of a site, main language first."""
    stored = site.bag.get_node("info").attr.get("languages")
    if stored:
        return stored.split(",")
    language = root_language(site)
    return [language if language and CODE.fullmatch(language) else DEFAULT_LANGUAGE]


def main_language(site):
    return site_languages(site)[0]


def set_languages(site, languages):
    """Set the languages, main first; removing a language drops its translations."""
    if not isinstance(languages, list) or not 1 <= len(languages) <= MAX_LANGUAGES:
        raise DomainError("invalid_input", f"A site has 1 to {MAX_LANGUAGES} languages")
    if not all(isinstance(code, str) and CODE.fullmatch(code) for code in languages):
        raise DomainError("invalid_input", "Languages are BCP 47 tags such as it, en, pt-br")
    if len(set(languages)) != len(languages):
        raise DomainError("invalid_input", "A language appears twice")
    translations = site.section("translations")
    if languages[0] != main_language(site) and any(len(node.value) for node in translations.nodes):
        raise DomainError("conflict", "The main language changes only before any translation")
    kept = set(languages[1:])
    for node in translations.nodes:
        for language in [n.label for n in node.value.nodes if n.label not in kept]:
            node.value.pop(language)
    for page in site.section("pages").values():
        for copy in page.get_item("translations").values():
            for language in [n.label for n in copy.nodes if n.label not in kept]:
                copy.pop(language)
    site.bag.get_node("info").attr["languages"] = ",".join(languages)


def main_text(site, key):
    """The main text a translation key refers to."""
    kind, _, name = key.partition("_")
    if kind == "content":
        return site.node("contents", name).value
    if kind == "text":
        node = site.section("texts").get_node(name)
        if node is None:
            raise DomainError("not_found", f"No site text {name}", resource_id=name)
        return node.value
    raise DomainError("invalid_input", "A translation key is content_<id> or text_<name>")


def other_language(site, language):
    if language not in site_languages(site)[1:]:
        raise DomainError("invalid_input", f"{language} is not one of the site's other languages")
    return language


def set_translation(site, key, language, text, proposed=False):
    """Write the translation of a main text; Help me's translations are to review."""
    if not isinstance(text, str):
        raise DomainError("invalid_input", "A translation is a string")
    digest = value_digest(main_text(site, key))
    other_language(site, language)
    translations = site.section("translations")
    if translations.get_node(key) is None:
        translations.set_item(key, Bag())
    translations.get_item(key).set_item(
        language, text, _attributes={"main_digest": digest, "review": bool(proposed)}
    )


def confirm_translation(site, key, language):
    """Take a translation proposed by Help me as reviewed."""
    other_language(site, language)
    node = site.section("translations").get_node(f"{key}.{language}")
    if node is None:
        raise DomainError("not_found", f"No {language} translation of {key}")
    node.attr["review"] = False


def translation_states(site, key):
    """Each other language: state (missing, to_update, to_review, done) and text."""
    current = value_digest(main_text(site, key))
    found = site.section("translations").get_item(key)
    states = {}
    for language in site_languages(site)[1:]:
        node = found.get_node(language) if found is not None else None
        if node is None:
            states[language] = {"state": "missing", "text": None}
            continue
        state = (
            "to_update"
            if node.attr["main_digest"] != current
            else "to_review"
            if node.attr["review"]
            else "done"
        )
        states[language] = {"state": state, "text": node.value}
    return states


def set_site_text(site, name, text, language=None, proposed=False):
    """A template text of the site, such as a menu label, in the main or another language."""
    if not isinstance(name, str) or not TEXT_NAME.fullmatch(name):
        raise DomainError("invalid_input", "A text name is lower case: letters, digits, _")
    if language is None or language == main_language(site):
        if not isinstance(text, str):
            raise DomainError("invalid_input", "A text is a string")
        site.section("texts").set_item(name, text)
        return
    set_translation(site, "text_" + name, language, text, proposed)
