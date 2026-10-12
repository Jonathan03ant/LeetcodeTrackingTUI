"""Rich renderer shared by array-based algorithm traces."""

from rich.console import Group
from rich.text import Text

from .state import ArrayState
from .theme import (
    INDEX_STYLE,
    LABEL_STYLE,
    LEGEND_LABEL_STYLE,
    MUTED_POINTER_STYLE,
    POINTER_STYLE,
    array_style,
)


CELL_WIDTH = 7
ROW_PREFIX = "        "


def _style_for_index(state: ArrayState, index: int) -> str:
    if index in state.highlights:
        return array_style("highlight")

    for array_range in state.ranges:
        if array_range.start <= index <= array_range.end:
            return array_style(array_range.role)

    return array_style("default")


def render_array_state(state: ArrayState) -> Group:
    """Render an ArrayState without knowing which algorithm produced it."""
    indices = Text(ROW_PREFIX)
    values = Text("values  ", style=LABEL_STYLE)

    for index, value in enumerate(state.values):
        indices.append(f"{index:^{CELL_WIDTH}}", style=INDEX_STYLE)
        values.append(f"[{str(value):^{CELL_WIDTH - 2}}]", style=_style_for_index(state, index))

    pointer_rows = []
    for name, index in state.pointers:
        if 0 <= index < len(state.values):
            row = Text(f"{name:<8}", style=POINTER_STYLE)
            row.append(" " * (index * CELL_WIDTH))
            row.append(f"{'▲':^{CELL_WIDTH}}", style=POINTER_STYLE)
        else:
            row = Text(
                f"{name:<8} = {index} (outside array)",
                style=MUTED_POINTER_STYLE,
            )
        pointer_rows.append(row)

    legend = Text()
    visible_ranges = [r for r in state.ranges if r.start <= r.end]
    if visible_ranges:
        legend.append("Partitions: ", style=LEGEND_LABEL_STYLE)
        for position, array_range in enumerate(visible_ranges):
            if position:
                legend.append("  ")
            legend.append(
                f"{array_range.label} [{array_range.start}..{array_range.end}]",
                style=array_style(array_range.role),
            )

    parts = [indices, values, *pointer_rows]
    if visible_ranges:
        parts.extend([Text(""), legend])
    return Group(*parts)
