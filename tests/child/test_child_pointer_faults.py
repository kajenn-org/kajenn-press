"""A pointer that is valid JSON but not an object never turns into a 500."""

import asyncio

from child.support import running
from child.test_child_serving_contract import PUBLIC, published
from publication.storage_support import filesystem

from kajenn_press.child import create_static_site_server


def test_non_object_pointer_keeps_the_loaded_release_or_answers_503(tmp_path):
    storage, settings_id, _manifest = published(tmp_path)
    pointer_key = storage["bucket"] + f"/pointers/{settings_id}.json"

    async def check():
        child = create_static_site_server(
            bindings={PUBLIC: settings_id}, release_storage=storage, cache_seconds=1
        )
        async with running(child, PUBLIC) as http:
            before = await http.get("/it/")
            assert before.status_code == 200
            filesystem().pipe(pointer_key, b"[]")
            await asyncio.sleep(1.2)
            kept = await http.get("/it/")
            assert kept.status_code == 200 and kept.text == before.text
        fresh = create_static_site_server(bindings={PUBLIC: settings_id}, release_storage=storage)
        async with running(fresh, PUBLIC) as http:
            assert (await http.get("/it/")).status_code == 503

    asyncio.run(check())
