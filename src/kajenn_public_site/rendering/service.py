"""Explicit authorized render entry; saves and management discovery stay inert."""

from .inputs import RenderInputs


class RenderService:
    def __init__(self, catalog, policy, worker):
        self.inputs = RenderInputs(catalog, policy)
        self.worker = worker

    def freeze(self, identity, variant_id, **selection):
        return self.inputs.freeze(identity, variant_id, self.worker.profile(), **selection)

    def render(self, identity, frozen):
        self.inputs.authorize(identity, frozen)
        result = self.worker.render(frozen)
        for diagnostic in result["diagnostics"]:
            diagnostic.setdefault("resource_id", frozen.unpack()["data"]["page"]["variant_id"])
        return result
