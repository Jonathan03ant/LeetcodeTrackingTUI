"""Generic Textual screen for stepping through array states."""

from collections.abc import Callable, Iterable

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Static

from .array_view import render_array_state
from .state import ArrayState


class ArrayVisualizerScreen(Screen):
    """Display any sequence of ArrayState frames."""

    BINDINGS = [
        Binding("left", "previous", "Previous"),
        Binding("right", "next", "Next"),
        Binding("r", "reset", "Reset"),
        Binding("q", "back", "Back"),
    ]

    CSS = """
    ArrayVisualizerScreen {
        background: #0b1220;
    }

    ArrayVisualizerScreen #visualizer_title {
        height: 1;
        padding: 0 2;
        background: #111827;
        color: #e5e7eb;
        text-style: bold;
    }

    ArrayVisualizerScreen #array_visualization {
        height: auto;
        min-height: 8;
        margin: 1 2 0 2;
        padding: 1;
        border: round #334155;
        background: #111827;
        color: #e5e7eb;
    }

    ArrayVisualizerScreen #step_message {
        height: auto;
        margin: 0 2;
        padding: 0 1;
        border-left: thick #2563eb;
        background: #0f172a;
        color: #cbd5e1;
    }

    ArrayVisualizerScreen #step_counter {
        height: 1;
        margin: 0 2;
        color: #94a3b8;
        text-align: right;
        text-style: bold;
    }

    ArrayVisualizerScreen #input_row {
        height: 1;
        margin: 1 2 0 2;
    }

    ArrayVisualizerScreen #input_label {
        width: 7;
        height: 1;
        padding: 0 1 0 0;
        color: #94a3b8;
    }

    ArrayVisualizerScreen #array_input {
        width: 1fr;
        height: 1;
        min-height: 1;
        border: none;
        padding: 0 1;
        background: #1f2937;
        color: #f8fafc;
    }

    ArrayVisualizerScreen #controls {
        height: 1;
        margin: 1 2;
        align-horizontal: center;
    }

    ArrayVisualizerScreen #controls Button {
        width: auto;
        min-width: 10;
        height: 1;
        margin: 0 1 0 0;
        padding: 0 2;
        border: none;
        color: #ffffff;
        text-style: bold;
    }

    ArrayVisualizerScreen #load_button {
        background: #0f766e;
    }

    ArrayVisualizerScreen #previous_button {
        background: #475569;
    }

    ArrayVisualizerScreen #next_button {
        background: #2563eb;
    }

    ArrayVisualizerScreen #reset_button {
        background: #92400e;
    }

    ArrayVisualizerScreen #controls Button:hover {
        text-style: bold reverse;
    }

    ArrayVisualizerScreen #controls Button:disabled {
        opacity: 40%;
    }
    """

    def __init__(
        self,
        title: str,
        trace: Callable[[list[int]], Iterable[ArrayState]],
        default_values: tuple[int, ...],
    ):
        super().__init__()
        self.visualizer_title = title
        self.trace = trace
        self.current_values = list(default_values)
        self.states = self._build_states(self.current_values)
        self.current_step = 0

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(self.visualizer_title, id="visualizer_title")
        yield Static(id="array_visualization")
        yield Static(id="step_message")
        yield Static(id="step_counter")
        with Horizontal(id="input_row"):
            yield Label("Input:", id="input_label")
            yield Input(
                value=",".join(str(value) for value in self.current_values),
                placeholder="Example: 2,0,2,1,1,0",
                id="array_input",
            )
        with Horizontal(id="controls"):
            yield Button("Load", id="load_button", variant="primary")
            yield Button("Previous", id="previous_button")
            yield Button("Next", id="next_button")
            yield Button("Reset", id="reset_button")
        yield Footer()

    def on_mount(self) -> None:
        self._show_current_state()

    def _show_current_state(self) -> None:
        state = self.states[self.current_step]
        self.query_one("#array_visualization", Static).update(render_array_state(state))
        self.query_one("#step_message", Static).update(state.message)
        self.query_one("#step_counter", Static).update(
            f"Step {self.current_step} / {len(self.states) - 1}"
        )
        self.query_one("#previous_button", Button).disabled = self.current_step == 0
        self.query_one("#next_button", Button).disabled = (
            self.current_step == len(self.states) - 1
        )

    def _build_states(self, values: list[int]) -> list[ArrayState]:
        states = list(self.trace(values))
        if not states:
            raise ValueError("A visualizer trace must produce at least one state")
        return states

    def _load_input(self) -> None:
        raw_input = self.query_one("#array_input", Input).value.strip()
        if not raw_input:
            self.notify("Enter at least one value", severity="warning")
            return

        try:
            values = [int(part) for part in raw_input.replace(",", " ").split()]
            states = self._build_states(values)
        except ValueError as error:
            self.notify(str(error), severity="error")
            return

        self.current_values = values
        self.states = states
        self.current_step = 0
        self._show_current_state()
        self.notify(f"Loaded {len(values)} values", severity="information")

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

    @on(Input.Submitted, "#array_input")
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
