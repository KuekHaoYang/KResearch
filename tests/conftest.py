"""Shared test fixtures."""

import pytest

from kresearch.config import KResearchConfig
from kresearch.models.mind_map import MindMap, Source
from kresearch.models.state import ResearchState


@pytest.fixture
def config():
    return KResearchConfig(gemini_api_key="test-key")


@pytest.fixture
def mind_map():
    return MindMap.create("test query")


@pytest.fixture
def state():
    return ResearchState.create("test query", max_iterations=5)


@pytest.fixture
def sample_source():
    return Source(url="https://example.com", title="Example")
