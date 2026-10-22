"""Operator orientation, shown on entry and retained in the Gallery navigation."""

from kajenn_public_site.admin.host import CURRENT_REQUEST
from kajenn_public_site.admin.views import AdminPage


class Page(AdminPage):
    title = "Home · How it works"

    async def main(self, root):  # wf:phase-1:new
        avatar = CURRENT_REQUEST.get().avatar()
        if avatar is None or "editor" not in avatar.tags:
            self.login_view(root)
            return
        home = root.main(class_="guide")
        hero = home.header(class_="guide-hero")
        hero.p("YOUR MULTISITE WORKSPACE", class_="guide-eyebrow")
        hero.h1("Multiple sites. One place to work.")
        hero.p(
            "Kajenn public site helps you organize pages, languages and resources across your sites. "
            "Your team prepares content here; visitors see the static HTML pages generated "
            "from the latest published release.",
            class_="guide-lead",
        )
        status = home.aside(class_="guide-status", aria_label="Available features")
        status.strong("What you can do today")
        status.p(
            "Create a site, browse content and language variants, and inspect resources, "
            "source files and revisions. Editing and publishing controls will arrive in later "
            "phases. The current content and resource views are read-only."
        )
        start = home.section(class_="guide-section")
        start.h2("Getting started")
        steps = start.ol(class_="guide-steps")
        for title, text in (
            (
                "Choose a site",
                (
                    "Use the selector in the top toolbar. To start a project, choose “New site” "
                    "and enter its name and languages. This action requires permission to create sites."
                ),
            ),
            (
                "Open Content",
                (
                    "In the navigation tree on the left, open Content under the site name. "
                    "Select a page from the list, then choose a language to inspect its blocks."
                ),
            ),
            (
                "Explore Resources and the library",
                (
                    "Resources contains items belonging to the selected site. The Shared library "
                    "contains reusable resources for multiple sites."
                ),
            ),
        ):
            item = steps.li()
            item.h3(title)
            item.p(text)
        start.p(
            "Each page opens in a tab. You can work with several sites at once: changing the "
            "site selector updates the navigation tree, while existing tabs keep their original "
            "site. Check the tab title to see which site you are viewing.",
            class_="guide-tip",
        )
        concepts = home.section(class_="guide-section")
        concepts.h2("How pages fit together")
        grid = concepts.div(class_="guide-grid")
        for title, text in (
            (
                "Site",
                (
                    "A project with its own pages, languages and resources. "
                    "One administrator or team can manage several sites."
                ),
            ),
            (
                "Content and languages",
                (
                    "A content item represents a page, such as “About us”. Its English and Italian "
                    "variants have their own text and URL paths. Each language can be published "
                    "when it is ready."
                ),
            ),
            (
                "Template",
                (
                    "Defines the page structure and its named blocks, such as introduction and body. "
                    "Templates can use Gramlot or HtmlBuilder and are rendered as static HTML."
                ),
            ),
            (
                "Blocks in Data",
                (
                    "Content stays separate from the template. Each language variant fills named "
                    "blocks with HTML or Markdown. Markdown can include HTML; the rendered markup "
                    "is filtered without changing the saved source."
                ),
            ),
            (
                "Resources and the library",
                (
                    "Templates, CSS, JavaScript and media can belong to a site or to the Shared "
                    "library. A copy made for a site is independent of the original: changing it "
                    "does not change other sites."
                ),
            ),
            (
                "Revisions",
                (
                    "Saving preserves a history of changes. The detail view lets you inspect "
                    "information, source files and revisions. A build uses specific revisions "
                    "so its output can be reproduced."
                ),
            ),
        ):
            card = grid.article(class_="guide-card")
            card.h3(title)
            card.p(text)
        example = home.section(class_="guide-example")
        example.h2("Example: an “About us” page")
        example.p(
            "A “Standard page” template defines two blocks: introduction and body. "
            "The English variant supplies the text for /en/about/ and the Italian variant "
            "supplies the text for /it/chi-siamo/. Both share the same structure, while "
            "keeping their content independent. You can publish English first and finish "
            "Italian later."
        )
        publication = home.section(class_="guide-section")
        publication.h2("From content to the public site")
        publication.p(
            "This is the intended workflow. Build and publishing services already exist; "
            "their administration controls will be added in the publishing phase."
        )
        flow = publication.ol(class_="guide-flow")
        for title, text in (
            ("Save", "Keep a new revision. Saving does not change the public site."),
            ("Build", "Combine templates, content blocks and resources into static pages."),
            ("Preview", "Review the build through a temporary link that can be revoked."),
            (
                "Publish",
                (
                    "Activate a release to make it public. Rollback reactivates a previous "
                    "release when needed."
                ),
            ),
        ):
            item = flow.li()
            item.h3(title)
            item.p(text)
        llm = home.section(class_="guide-section guide-llm")
        llm.h2("Work with an AI assistant")
        llm.p(
            "An LLM connected to Kajenn’s MCP/OpenAPI interfaces can create sites, content "
            "and language variants through the same services used by this administration. "
            "It requires an authorized connection and acts within the permissions "
            "assigned to its identity."
        )
        llm.blockquote(
            "“In the Kajenn site, create an About us page in English using the Standard page "
            "template, and prepare the introduction and body blocks.”"
        )
        llm.p(
            "If a reference is ambiguous, the assistant must first identify the correct site "
            "and template revision. Creating or updating content through MCP does not "
            "automatically publish it.",
            class_="muted",
        )
