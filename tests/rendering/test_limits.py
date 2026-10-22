"""Configuration and derived readiness edge cases."""

import pytest

from kajenn_public_site.rendering.process import RenderWorker


@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan"), True, "15"])
def test_timeout_is_explicit_positive_finite(value):
    with pytest.raises(ValueError, match="timeout"):
        RenderWorker("/unused", timeout=value)


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_output_limit_is_positive_bytes(value):
    with pytest.raises(ValueError, match="output_limit"):
        RenderWorker("/unused", output_limit=value)
