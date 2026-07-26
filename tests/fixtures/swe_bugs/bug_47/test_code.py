import pytest
from .code import process
@pytest.mark.asyncio
async def test_process():
    assert await process({'key': 'val'})
