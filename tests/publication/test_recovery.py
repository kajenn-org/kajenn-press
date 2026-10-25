import multiprocessing
import os
import time

import pytest
from publication.support import candidate, services, site_fixture

from kajenn_press.catalog.errors import CatalogError
from kajenn_press.domain import DomainError


def interrupted_process(root, connection):
    editorial, pub = services(root)
    fixture = site_fixture(
        editorial, pub, source="import time\ndef build(source, data):\n    time.sleep(5)\n"
    )
    selection = candidate(pub, fixture)
    started = pub.execute("admin", "build_start", candidate_id=selection["record_id"], key="build")
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        status = pub.execute("admin", "build_status", build_id=started["record_id"])
        if status["attributes"]["state"] == "running":
            connection.send((selection, status))
            connection.close()
            os._exit(23)
        time.sleep(0.01)
    os._exit(24)


def test_real_process_interruption_retry_and_fence(tmp_path):
    ctx = multiprocessing.get_context("spawn")
    receiver, sender = ctx.Pipe(duplex=False)
    process = ctx.Process(target=interrupted_process, args=(str(tmp_path), sender))
    process.start()
    sender.close()
    assert receiver.poll(30)
    selection, running = receiver.recv()
    process.join(10)
    assert process.exitcode == 23
    editorial, pub = services(tmp_path)
    try:
        interrupted = pub.execute("admin", "build_status", build_id=running["record_id"])
        assert interrupted["attributes"]["state"] == "interrupted"
        assert interrupted["attributes"]["candidate_revision"] == selection["revision_id"]
        previous = pub.catalog.read().revisions[running["revision_id"]]
        with pytest.raises(DomainError) as stale:
            pub._transition(previous, previous["data"]["attributes"])
        assert stale.value.code == "stale_attempt"
        pub.worker.timeout = 0.1
        retry = pub.execute(
            "admin",
            "build_retry",
            build_id=running["record_id"],
            expected_generation=interrupted["generation"],
            key="retry",
        )
        pub._futures[retry["record_id"]].result(20)
        failed = pub.execute("admin", "build_status", build_id=retry["record_id"])
        assert failed["attributes"]["state"] == "failed"
        assert failed["attributes"]["candidate_revision"] == selection["revision_id"]
        assert failed["attributes"]["attempt_id"] != running["attributes"]["attempt_id"]
        with pytest.raises(DomainError, match="sealed"):
            pub.sealed_manifest(pub.catalog.read().revisions[failed["revision_id"]])
        assert not pub.find(
            pub.catalog.read(),
            "publication_channel",
            settings_id=selection["attributes"]["settings_id"],
        )
        # Closing an active bounded job joins it before the catalog can change owner.
        again = pub.execute(
            "admin",
            "build_retry",
            build_id=retry["record_id"],
            expected_generation=failed["generation"],
            key="again",
        )
        with pytest.raises(CatalogError):
            services(tmp_path)
        pub.close()
        generation = pub.catalog.read().generation
        pub._futures[again["record_id"]].done()
        assert pub.catalog.read().generation == generation
        assert all(f.done() for f in pub._futures.values())
    finally:
        pub.close()
        editorial.catalog.close()
