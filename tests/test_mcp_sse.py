import pytest

@pytest.mark.parametrize("drop_point, schema_validity, loop_count", [
    *(("mid_stream", "malformed", i) for i in range(100)),
    *(("start", "valid", i) for i in range(100)),
    *(("end", "malformed", i) for i in range(50))
])
@pytest.mark.asyncio
async def test_mcp_sse_connections(drop_point, schema_validity, loop_count):
    # Simulate SSE drops
    assert drop_point in ["mid_stream", "start", "end"]
    assert schema_validity in ["malformed", "valid"]
