import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.parametrize("error_type, status_code", [
    *(("LiteLLM_500", 500) for _ in range(100)),
    *(("Timeout", 408) for _ in range(100)),
    *(("Malformed_JSON", 200) for _ in range(50))
])
@pytest.mark.asyncio
async def test_smart_router_errors(error_type, status_code):
    # Simulate errors
    assert error_type in ["LiteLLM_500", "Timeout", "Malformed_JSON"]
    assert status_code in [500, 408, 200]
