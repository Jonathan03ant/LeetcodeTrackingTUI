"""Map locally tracked LeetCode slugs to optional visualizer traces."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from .state import ArrayState
from .traces.arrays import trace_sort_colors


TraceFunction = Callable[[list[int]], Iterable[ArrayState]]


@dataclass(frozen=True)
class ArrayVisualizerSpec:
    """Configuration needed to run an array visualizer with custom input."""

    title: str
    default_values: tuple[int, ...]
    trace: TraceFunction


VISUALIZERS: dict[str, ArrayVisualizerSpec] = {
    "sort_colors": ArrayVisualizerSpec(
        title="Sort Colors — Dutch National Flag",
        default_values=(2, 0, 2, 1, 1, 0),
        trace=trace_sort_colors,
    ),
}


def get_visualizer(slug: str) -> ArrayVisualizerSpec | None:
    """Return the visualizer registered for a problem slug."""
    return VISUALIZERS.get(slug)
