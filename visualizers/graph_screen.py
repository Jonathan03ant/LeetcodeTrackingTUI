"""Textual screen for stepping through graph states."""

from collections.abc import Callable, Iterable

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Static

from .graph_view import render_graph_state
from .state import GraphState


GraphTrace = Callable[
    [tuple[tuple[str, str], ...], str, str],
    Iterable[GraphState],
]


class GraphVisualizerScreen(Screen):
    """Display a sequence of graphical graph-traversal frames."""

    BINDINGS = [
        Binding("left", "previous", "Previous"),
        Binding("right", "next", "Next"),
        Binding("r", "reset", "Reset"),
        Binding("q", "back", "Back"),
    ]

    CSS = """
    GraphVisualizerScreen {
        background: #0b1220;
    }

    GraphVisualizerScreen #visualizer_title {
        height: 1;
        padding: 0 2;
        background: #111827;
        color: #e5e7eb;
        text-style: bold;
    }

    GraphVisualizerScreen #graph_visualization {
        height: 1fr;
        min-height: 12;
        margin: 1 2 0 2;
        padding: 1;
        border: round #334155;
        background: #111827;
        color: #e5e7eb;
        overflow: auto;
    }

    GraphVisualizerScreen #step_message {
        height: auto;
        margin: 0 2;
        padding: 0 1;
        border-left: thick #2563eb;
        background: #0f172a;
        color: #cbd5e1;
    }

    GraphVisualizerScreen #step_counter {
        height: 1;
        margin: 0 2;
        color: #94a3b8;
        text-align: right;
        text-style: bold;
    }

    GraphVisualizerScreen .input_row {
        height: 1;
        margin: 1 2 0 2;
    }

    GraphVisualizerScreen #nodes_row {
        margin-top: 0;
    }

    GraphVisualizerScreen .input_label {
        width: 8;
        height: 1;
        color: #94a3b8;
    }

    GraphVisualizerScreen .graph_input {
        height: 1;
        min-height: 1;
        border: none;
        padding: 0 1;
        background: #1f2937;
        color: #f8fafc;
    }

    GraphVisualizerScreen #edges_input {
        width: 1fr;
    }

    GraphVisualizerScreen #start_input,
    GraphVisualizerScreen #target_input {
        width: 1fr;
    }

    GraphVisualizerScreen #target_label {
        width: 9;
        padding-left: 1;
    }

    GraphVisualizerScreen #controls {
        height: 1;
        margin: 1 2;
        align-horizontal: center;
    }

    GraphVisualizerScreen #controls Button {
        width: auto;
        min-width: 10;
        height: 1;
        margin: 0 1 0 0;
        padding: 0 2;
        border: none;
        color: #ffffff;
        text-style: bold;
    }

    GraphVisualizerScreen #load_button { background: #0f766e; }
    GraphVisualizerScreen #previous_button { background: #475569; }
    GraphVisualizerScreen #next_button { background: #2563eb; }
    GraphVisualizerScreen #reset_button { background: #92400e; }

    GraphVisualizerScreen #controls Button:hover {
        text-style: bold reverse;
    }

    GraphVisualizerScreen #controls Button:disabled {
        opacity: 40%;
    }
    """

    def __init__(
        self,
        title: str,
        trace: GraphTrace,
        default_edges: tuple[tuple[str, str], ...],
        default_start: str,
        default_target: str,
    ):
        super().__init__()
        self.visualizer_title = title
        self.trace = trace
        self.current_edges = default_edges
        self.current_start = default_start
        self.current_target = default_target
        self.states = self._build_states(
            default_edges,
            default_start,
            default_target,
        )
        self.current_step = 0

    def compose(self) -> ComposeResult:
        edges = ",".join(f"{left}-{right}" for left, right in self.current_edges)
        yield Header()
        yield Static(self.visualizer_title, id="visualizer_title")
        yield Static(id="graph_visualization")
        yield Static(id="step_message")
        yield Static(id="step_counter")
        with Horizontal(id="edges_row", classes="input_row"):
            yield Label("Edges:", classes="input_label")
            yield Input(
                value=edges,
                placeholder="A-B,A-C,B-D",
                id="edges_input",
                classes="graph_input",
            )
        with Horizontal(id="nodes_row", classes="input_row"):
            yield Label("Start:", classes="input_label")
            yield Input(
                value=self.current_start,
                id="start_input",
                classes="graph_input",
            )
            yield Label("Target:", id="target_label", classes="input_label")
            yield Input(
                value=self.current_target,
                id="target_input",
                classes="graph_input",
            )
        with Horizontal(id="controls"):
            yield Button("Load", id="load_button")
            yield Button("Previous", id="previous_button")
            yield Button("Next", id="next_button")
            yield Button("Reset", id="reset_button")
        yield Footer()

    def on_mount(self) -> None:
        self._show_current_state()

    def _parse_edges(self, raw_edges: str) -> tuple[tuple[str, str], ...]:
        edges = []
        for raw_edge in raw_edges.split(","):
            parts = [part.strip() for part in raw_edge.split("-")]
            if len(parts) != 2 or not all(parts):
                raise ValueError("Use edges like A-B,A-C,B-D")
            edge = (parts[0], parts[1])
            if edge not in edges and (edge[1], edge[0]) not in edges:
                edges.append(edge)
        if not edges:
            raise ValueError("Enter at least one edge")
        return tuple(edges)

    def _build_states(
        self,
        edges: tuple[tuple[str, str], ...],
        start: str,
        target: str,
    ) -> list[GraphState]:
        states = list(self.trace(edges, start, target))
        if not states:
            raise ValueError("A graph trace must produce at least one state")
        return states

    def _show_current_state(self) -> None:
        state = self.states[self.current_step]
        self.query_one("#graph_visualization", Static).update(
            render_graph_state(state)
        )
        self.query_one("#step_message", Static).update(state.message)
        self.query_one("#step_counter", Static).update(
            f"Step {self.current_step} / {len(self.states) - 1}"
        )
        self.query_one("#previous_button", Button).disabled = self.current_step == 0
        self.query_one("#next_button", Button).disabled = (
            self.current_step == len(self.states) - 1
        )

    def _load_input(self) -> None:
        try:
            edges = self._parse_edges(
                self.query_one("#edges_input", Input).value.strip()
            )
            start = self.query_one("#start_input", Input).value.strip()
            target = self.query_one("#target_input", Input).value.strip()
            states = self._build_states(edges, start, target)
        except ValueError as error:
            self.notify(str(error), severity="error")
            return

        self.current_edges = edges
        self.current_start = start
        self.current_target = target
        self.states = states
        self.current_step = 0
        self._show_current_state()

    def action_next(self) -> None:
        if self.current_step < len(self.states) - 1:
            self.current_step += 1
            self._show_current_state()

    def action_previous(self) -> None:
        if self.current_step > 0:
            self.current_step -= 1
            self._show_current_state()

    def action_reset(self) -> None:
        self.current_step = 0
        self._show_current_state()

    def action_back(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#load_button")
    def load_button_pressed(self) -> None:
        self._load_input()

    @on(Input.Submitted)
    def input_submitted(self) -> None:
        self._load_input()

    @on(Button.Pressed, "#previous_button")
    def previous_button_pressed(self) -> None:
        self.action_previous()

    @on(Button.Pressed, "#next_button")
    def next_button_pressed(self) -> None:
        self.action_next()

    @on(Button.Pressed, "#reset_button")
    def reset_button_pressed(self) -> None:
        self.action_reset()
