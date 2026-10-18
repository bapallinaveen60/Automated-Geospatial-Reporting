from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent.parent / "data" / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES
