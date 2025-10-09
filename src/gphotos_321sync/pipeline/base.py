"""Base classes for pipeline architecture."""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar, AsyncIterator, Optional, Any, Dict, List
from dataclasses import dataclass, field
from enum import Enum
from ..logging_config import get_logger

# Type variables for input and output
TInput = TypeVar("TInput")
TOutput = TypeVar("TOutput")


class PipelineStage(str, Enum):
    """Pipeline stage identifiers."""

    INGESTION = "ingestion"
    EXTRACTION = "extraction"
    SCANNING = "scanning"
    METADATA_EXTRACTION = "metadata_extraction"
    NORMALIZATION = "normalization"
    GALLERY_BUILDING = "gallery_building"


@dataclass
class PipelineContext:
    """Context passed through pipeline stages."""

    job_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to context."""
        self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata from context."""
        return self.metadata.get(key, default)


class PipelineComponent(ABC, Generic[TInput, TOutput]):
    """Base class for pipeline components."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.logger = get_logger(f"{__name__}.{name}")
        self._next_component: Optional["PipelineComponent"] = None

    @abstractmethod
    async def process(
        self, input_data: TInput, context: PipelineContext
    ) -> AsyncIterator[TOutput]:
        """
        Process input and yield output items.

        This is a generator to support streaming/chunked processing.
        Components can yield items as they're ready rather than
        waiting for all processing to complete.
        """
        pass

    async def execute(
        self, input_data: TInput, context: PipelineContext
    ) -> AsyncIterator[TOutput]:
        """
        Execute this component and optionally pass to next component.

        This method handles logging and error propagation.
        """
        self.logger.info(
            f"Starting component: {self.name}",
            extra={
                "extra_fields": {"job_id": context.job_id, "component": self.name}
            },
        )

        try:
            async for output in self.process(input_data, context):
                self.logger.debug(
                    "Component yielded output",
                    extra={
                        "extra_fields": {
                            "job_id": context.job_id,
                            "component": self.name,
                            "output_type": type(output).__name__,
                        }
                    },
                )
                yield output

            self.logger.info(
                f"Component completed: {self.name}",
                extra={
                    "extra_fields": {"job_id": context.job_id, "component": self.name}
                },
            )

        except Exception as e:
            self.logger.error(
                f"Component failed: {self.name}",
                exc_info=True,
                extra={
                    "extra_fields": {
                        "job_id": context.job_id,
                        "component": self.name,
                        "error_type": type(e).__name__,
                    }
                },
            )
            raise

    def chain(self, next_component: "PipelineComponent") -> "PipelineComponent":
        """Chain this component to another."""
        self._next_component = next_component
        return next_component


class Pipeline:
    """Pipeline orchestrator."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.logger = get_logger(f"{__name__}.Pipeline.{name}")
        self.components: List[PipelineComponent] = []

    def add_component(self, component: PipelineComponent) -> "Pipeline":
        """Add component to pipeline."""
        self.components.append(component)
        return self

    async def run(
        self, initial_input: Any, context: PipelineContext
    ) -> AsyncIterator[Any]:
        """
        Run pipeline from start to finish.

        Each component processes output from previous component.
        """
        self.logger.info(
            f"Starting pipeline: {self.name}",
            extra={
                "extra_fields": {
                    "job_id": context.job_id,
                    "pipeline": self.name,
                    "component_count": len(self.components),
                }
            },
        )

        current_data = initial_input

        for i, component in enumerate(self.components):
            self.logger.debug(
                f"Running component {i+1}/{len(self.components)}: {component.name}",
                extra={
                    "extra_fields": {
                        "job_id": context.job_id,
                        "component": component.name,
                        "stage": i + 1,
                    }
                },
            )

            # Process current data through component
            # For first component, current_data is the initial input
            # For subsequent components, current_data is a list of outputs from previous component
            if i == 0:
                # First component: process initial input directly
                outputs = []
                async for output in component.execute(current_data, context):
                    outputs.append(output)
                current_data = outputs
            else:
                # Subsequent components: process each output from previous component
                new_outputs = []
                for item in current_data:
                    async for output in component.execute(item, context):
                        new_outputs.append(output)
                current_data = new_outputs

        # Yield final outputs
        for output in current_data:
            yield output

        self.logger.info(
            f"Pipeline completed: {self.name}",
            extra={"extra_fields": {"job_id": context.job_id, "pipeline": self.name}},
        )
