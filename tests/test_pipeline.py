"""Tests for pipeline architecture."""

import pytest
from pathlib import Path
from typing import AsyncIterator
from gphotos_sync.pipeline import PipelineComponent, Pipeline, PipelineContext


class TestComponent(PipelineComponent[int, str]):
    """Test component that converts integers to strings."""

    def __init__(self):
        super().__init__("TestComponent")

    async def process(self, input_data: int, context: PipelineContext) -> AsyncIterator[str]:
        """Convert integer to string."""
        yield str(input_data)


class DoubleComponent(PipelineComponent[int, int]):
    """Test component that doubles integers."""

    def __init__(self):
        super().__init__("DoubleComponent")

    async def process(self, input_data: int, context: PipelineContext) -> AsyncIterator[int]:
        """Double the input."""
        yield input_data * 2


@pytest.mark.asyncio
async def test_single_component():
    """Test single component execution."""
    component = TestComponent()
    context = PipelineContext(job_id="test-123")

    results = []
    async for result in component.execute(42, context):
        results.append(result)

    assert results == ["42"]


@pytest.mark.asyncio
async def test_pipeline_execution():
    """Test pipeline with multiple components."""
    pipeline = Pipeline("TestPipeline")
    pipeline.add_component(DoubleComponent())
    pipeline.add_component(TestComponent())

    context = PipelineContext(job_id="test-456")

    results = []
    async for result in pipeline.run(21, context):
        results.append(result)

    # 21 * 2 = 42, then convert to string
    assert results == ["42"]


@pytest.mark.asyncio
async def test_pipeline_context():
    """Test that context is passed through pipeline."""

    class ContextCheckComponent(PipelineComponent[int, int]):
        def __init__(self):
            super().__init__("ContextCheckComponent")

        async def process(self, input_data: int, context: PipelineContext) -> AsyncIterator[int]:
            # Add metadata
            context.add_metadata("processed", True)
            yield input_data

    pipeline = Pipeline("ContextTest")
    pipeline.add_component(ContextCheckComponent())

    context = PipelineContext(job_id="test-789")

    async for _ in pipeline.run(1, context):
        pass

    assert context.get_metadata("processed") is True
