"""Pinned source graphs and authorization, without any rendering dependencies."""

import pytest
from services.scenarios import create_service, record, seed

from kajenn_public_site.domain import DomainError
from kajenn_public_site.rendering.contract import CONTRACT
from kajenn_public_site.rendering.inputs import RenderInputs


def test_exact_transitive_graph_and_current_policy(tmp_path):
    service = create_service(tmp_path)
    try:
        site, other, template, content, variant = seed(service)
        inputs = RenderInputs(service.catalog, service.policy)
        with pytest.raises(DomainError, match="Missing build"):
            inputs.freeze("admin", variant["record_id"], {"contract": CONTRACT})
        service.policy.grants["admin"]["*"] += ["build"]
        frozen = inputs.freeze("admin", variant["record_id"], {"contract": CONTRACT})
        data = frozen.unpack()
        assert set(data["references"]) == {
            site["revision_id"],
            template["revision_id"],
            content["revision_id"],
            variant["revision_id"],
        }
        assert other["record_id"] not in frozen.encoded.decode()
        record(
            service,
            "resource_save",
            key="new",
            scope="library",
            kind="template",
            name="page",
            source="changed",
            engine="gramlot",
            blocks={},
            record_id=template["record_id"],
            expected_generation=template["generation"],
        )
        assert (
            inputs.freeze(
                "admin",
                variant["record_id"],
                {"contract": CONTRACT},
                generation=data["catalog_generation"],
            )
            == frozen
        )
        service.policy.grants["admin"]["*"].remove("use")
        with pytest.raises(DomainError, match="Missing use"):
            inputs.authorize("admin", frozen)
    finally:
        service.catalog.close()
