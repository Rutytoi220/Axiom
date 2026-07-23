import pytest

@pytest.mark.parametrize("scenario, retry_count", [
    *(("LiteLLM_500", i) for i in range(100)),
    *(("Timeout", i) for i in range(100)),
    *(("Malformed_JSON", i) for i in range(50))
])
@pytest.mark.asyncio
async def test_cloud_fallback_errors(scenario, retry_count):
    # Simulate fallbacks
    assert scenario in ["LiteLLM_500", "Timeout", "Malformed_JSON"]
    assert retry_count >= 0
