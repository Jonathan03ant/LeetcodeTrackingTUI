"""Rich renderer for node-and-edge graph states."""

from collections import defaultdict, deque

from rich.console import Group
from rich.text import Text

from .state import GraphState
from .theme import graph_edge_style, graph_node_style


def _layered_positions(
    state: GraphState,
    node_width: int,
) -> tuple[dict[str, tuple[int, int]], int, int]:
    adjacency = {node: [] for node in state.nodes}
    for left, right in state.edges:
        adjacency[left].append(right)
        adjacency[right].append(left)

    depths = {state.start: 0}
    queue = deque([state.start])
    while queue:
        node = queue.popleft()
        for neighbor in adjacency[node]:
            if neighbor not in depths:
                depths[neighbor] = depths[node] + 1
                queue.append(neighbor)

    next_depth = max(depths.values(), default=-1) + 1
    for node in state.nodes:
        if node not in depths:
            depths[node] = next_depth

    levels: dict[int, list[str]] = defaultdict(list)
    for node in state.nodes:
        levels[depths[node]].append(node)

    widest_level = max((len(nodes) for nodes in levels.values()), default=1)
    width = max(44, widest_level * (node_width + 7))
    height = (max(levels, default=0) + 1) * 5 - 2
    positions = {}

    for depth, nodes in levels.items():
        for index, node in enumerate(nodes):
            center_x = round((index + 1) * width / (len(nodes) + 1))
            positions[node] = (center_x, depth * 5 + 1)

    return positions, width, max(height, 3)


def _node_role(state: GraphState, node: str) -> str:
    if node == state.current:
        return "current"
    if node in state.visited:
        return "visited"
    if node in state.frontier:
        return "frontier"
    if node == state.target:
        return "target"
    return "default"


def _edge_role(state: GraphState, edge: tuple[str, str]) -> str:
    if state.active_edge and set(edge) == set(state.active_edge):
        return "active"
    if edge[0] in state.visited and edge[1] in state.visited:
        return "visited"
    return "default"


def _draw_line(
    characters: list[list[str]],
    styles: list[list[str]],
    start: tuple[int, int],
    end: tuple[int, int],
    style: str,
) -> None:
    start_x, start_y = start
    end_x, end_y = end
    delta_x = end_x - start_x
    delta_y = end_y - start_y
    steps = max(abs(delta_x), abs(delta_y))
    if steps == 0:
        return

    if delta_x == 0:
        character = "│"
    elif delta_y == 0:
        character = "─"
    elif delta_x * delta_y > 0:
        character = "╲"
    else:
        character = "╱"

    for step in range(steps + 1):
        x = round(start_x + delta_x * step / steps)
        y = round(start_y + delta_y * step / steps)
        if not (0 <= y < len(characters) and 0 <= x < len(characters[y])):
            continue
        existing = characters[y][x]
        characters[y][x] = character if existing == " " else "┼"
        styles[y][x] = style


def _draw_node(
    characters: list[list[str]],
    styles: list[list[str]],
    node: str,
    center: tuple[int, int],
    node_width: int,
    style: str,
) -> None:
    center_x, center_y = center
    left = center_x - node_width // 2
    rows = (
        "╭" + "─" * (node_width - 2) + "╮",
        "│" + f"{node:^{node_width - 2}}" + "│",
        "╰" + "─" * (node_width - 2) + "╯",
    )

    for row_offset, row in enumerate(rows):
        y = center_y - 1 + row_offset
        for column_offset, character in enumerate(row):
            x = left + column_offset
            if 0 <= y < len(characters) and 0 <= x < len(characters[y]):
                characters[y][x] = character
                styles[y][x] = style


def render_graph_state(state: GraphState) -> Group:
    """Render a graph state as positioned nodes and connecting edges."""
    longest_label = max((len(node) for node in state.nodes), default=1)
    node_width = max(5, longest_label + 4)
    if node_width % 2 == 0:
        node_width += 1

    positions, width, height = _layered_positions(state, node_width)
    characters = [[" " for _ in range(width)] for _ in range(height)]
    styles = [["" for _ in range(width)] for _ in range(height)]

    for edge in state.edges:
        _draw_line(
            characters,
            styles,
            positions[edge[0]],
            positions[edge[1]],
            graph_edge_style(_edge_role(state, edge)),
        )

    for node in state.nodes:
        _draw_node(
            characters,
            styles,
            node,
            positions[node],
            node_width,
            graph_node_style(_node_role(state, node)),
        )

    rendered_rows = []
    for character_row, style_row in zip(characters, styles):
        row = Text()
        for character, style in zip(character_row, style_row):
            row.append(character, style=style)
        row.rstrip()
        rendered_rows.append(row)

    status = Text("Stack: ", style="bold")
    status.append("[" + ", ".join(state.frontier) + "]")
    status.append("    Visited: ", style="bold")
    status.append("{" + ", ".join(sorted(state.visited)) + "}")

    return Group(*rendered_rows, Text(""), status)
