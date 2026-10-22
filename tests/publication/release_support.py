"""Real release scenarios shared by the publication contract suite."""

from publication.support import built, candidate, services, site_fixture
from services.scenarios import record


def publisher(root):
    editorial, pub = services(root)
    editorial.policy.grants["admin"]["*"].append("publish")
    return editorial, pub


def activate(
    pub, fixture, job, generation=0, key="activate", operation="release_activate"
):
    return pub.execute(
        "admin",
        operation,
        settings_id=fixture["settings"]["record_id"],
        build_id=job["record_id"],
        expected_generation=generation,
        key=key,
    )


def initial_release(editorial, pub, prefix="one"):
    fixture = site_fixture(editorial, pub, prefix=prefix)
    selected = candidate(pub, fixture, key=prefix + "candidate")
    job = built(pub, selected, key=prefix + "build")
    activation = activate(pub, fixture, job, key=prefix + "activate")
    return fixture, selected, job, activation


def edit_language(editorial, fixture, language, source, key):
    current = editorial.execute(
        "admin", "record_read", record_id=fixture["variants"][language]["record_id"]
    )
    return record(
        editorial,
        "draft_save",
        key=key,
        variant_id=current["record_id"],
        expected_generation=current["generation"],
        template_revision=fixture["template"]["revision_id"],
        blocks={"body": {"format": "markdown", "source": source}},
    )


def updated_release(editorial, pub, fixture, original_job):
    italian = edit_language(editorial, fixture, "it", "# Italiano aggiornato", "it-update")
    english = edit_language(editorial, fixture, "en", "UNFINISHED ENGLISH", "en-draft")
    selected = pub.execute(
        "admin",
        "candidate_create",
        settings_id=fixture["settings"]["record_id"],
        variant_revisions=[italian["revision_id"]],
        base_build_id=original_job["record_id"],
        key="updated-candidate",
    )
    return selected, built(pub, selected, key="updated-build"), italian, english
