#!/usr/bin/env python3
"""
Interview Prep Progress Tracker - Interactive Dashboard
"""

import json
import random
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll

from leetcode_fetcher import fetch_problem_description, format_problem_for_display
from textual.widgets import (
    Header, Footer, Static, ProgressBar, Button,
    Label, Input, Collapsible, TextArea
)
from textual.binding import Binding
from textual.screen import Screen, ModalScreen
from textual import on
from tree_sitter import Language
import tree_sitter_c
import tree_sitter_cpp

from visualizers import ArrayVisualizerScreen, get_visualizer


LANGUAGES = {
    "cpp": {
        "display_name": "C++",
        "extension": ".cpp",
        "leetcode_slug": "cpp",
        "editor_language": "cpp",
        "comment_prefix": "//",
    },
    "python": {
        "display_name": "Python",
        "extension": ".py",
        "leetcode_slug": "python3",
        "editor_language": "python",
        "comment_prefix": "#",
    },
}
LANGUAGE_NAMES = {
    language: config["display_name"] for language, config in LANGUAGES.items()
}
DEFAULT_LANGUAGE = "cpp"


def register_cpp_highlighting(editor: TextArea) -> None:
    """Register combined C and C++ Tree-sitter rules on an editor."""
    cpp_language = Language(tree_sitter_cpp.language())
    highlight_query = (
        tree_sitter_c.HIGHLIGHTS_QUERY
        + "\n"
        + tree_sitter_cpp.HIGHLIGHTS_QUERY
    )
    editor.register_language("cpp", cpp_language, highlight_query)


class ProgressData:
    """Manages progress data loading and saving"""

    def __init__(self, filepath: str = "progress.json"):
        self.filepath = Path(__file__).parent / filepath
        self.data = self.load()

    def load(self) -> Dict:
        """Load progress data from JSON file"""
        if not self.filepath.exists():
            raise FileNotFoundError(f"Progress file(JSON) not found: {self.filepath}")

        with open(self.filepath, 'r') as f:
            return json.load(f)

    def save(self):
        """Save progress data to JSON file"""
        self.data['meta']['last_updated'] = datetime.now().strftime("%Y-%m-%d")
        with open(self.filepath, 'w') as f:
            json.dump(self.data, f, indent=2)

    def get_preferred_language(self) -> str:
        """Return the preferred solution language, defaulting to C++."""
        language = self.data["meta"].get("preferred_language", DEFAULT_LANGUAGE)
        return language if language in LANGUAGES else DEFAULT_LANGUAGE

    def set_preferred_language(self, language: str) -> None:
        """Persist the preferred solution language."""
        if language not in LANGUAGES:
            raise ValueError(f"Unsupported language: {language}")
        self.data["meta"]["preferred_language"] = language
        self.save()

    def add_problem(self, phase_id: int, topic_name: str, problem_name: str):
        """Add a solved problem to a specific topic"""
        for phase in self.data['leetcode']['phases']:
            if phase['id'] == phase_id:
                for topic in phase['topics']:
                    if topic['name'] == topic_name:
                        if problem_name not in topic['problems']:
                            topic['problems'].append(problem_name)
                            topic['solved'] = len(topic['problems'])
                        break
                # Recalculate phase total
                phase['solved'] = sum(t['solved'] for t in phase['topics'])
                break

        # Recalculate total
        self.data['leetcode']['total_solved'] = sum(p['solved'] for p in self.data['leetcode']['phases'])
        self.save()

    def toggle_systems_topic(self, module_name: str, topic_name: str):
        """Toggle completion status of a systems topic"""
        for module in self.data['systems']['modules']:
            if module['name'] == module_name:
                for topic in module['topics']:
                    if topic['name'] == topic_name:
                        topic['completed'] = not topic['completed']
                        self.save()
                        return topic['completed']
        return False

    def get_all_solved_problems(self) -> List[Tuple[str, str, str, str, int]]:
        """Get all solved problems as list of (problem_name, pattern, url, topic_name, phase_name, phase_id)"""
        solved = []
        for phase in self.data['leetcode']['phases']:
            phase_name = phase['name']
            phase_id = phase['id']
            for topic in phase['topics']:
                topic_name = topic['name']
                for problem in topic['problems']:
                    # Handle both old string format and new dict format
                    if isinstance(problem, dict):
                        problem_name = problem.get('name', '')
                        pattern = problem.get('pattern', '')
                        url = problem.get('url', '')
                    else:
                        # Old format: "Problem Name; pattern"
                        parts = problem.split(';')
                        problem_name = parts[0].strip()
                        pattern = parts[1].strip() if len(parts) > 1 else ''
                        url = ''

                    solved.append((problem_name, pattern, url, topic_name, phase_name, phase_id))
        return solved

    def get_days_since_review(self, phase_id: int, topic_name: str, problem_name: str) -> int:
        """Get days since last review. Returns 100 if never reviewed."""
        from datetime import datetime

        for phase in self.data['leetcode']['phases']:
            if phase['id'] == phase_id:
                for topic in phase['topics']:
                    if topic['name'] == topic_name:
                        for problem in topic['problems']:
                            if isinstance(problem, dict) and problem.get('name') == problem_name:
                                last_reviewed = problem.get('last_reviewed')
                                if not last_reviewed:
                                    return 100  # Never reviewed

                                # Calculate days since last review
                                last_date = datetime.strptime(last_reviewed, "%Y-%m-%d")
                                today = datetime.now()
                                days = (today - last_date).days
                                return max(days, 1)  # Minimum 1 day
        return 100  # Not found or never reviewed

    def update_last_reviewed(self, phase_id: int, topic_name: str, problem_name: str):
        """Update last_reviewed field for a problem"""
        today = datetime.now().strftime("%Y-%m-%d")

        for phase in self.data['leetcode']['phases']:
            if phase['id'] == phase_id:
                for topic in phase['topics']:
                    if topic['name'] == topic_name:
                        for problem in topic['problems']:
                            if isinstance(problem, dict) and problem.get('name') == problem_name:
                                problem['last_reviewed'] = today
                                self.save()
                                return
        # If not found, problem might be old string format - no update needed


class CollapsiblePhase(Static):
    """Collapsible widget for a LeetCode phase"""

    def __init__(self, phase: Dict, phase_idx: int, progress_data: ProgressData):
        super().__init__()
        self.phase = phase
        self.phase_idx = phase_idx
        self.progress_data = progress_data
        self.expanded = (phase_idx == 0)  # First phase expanded by default

    def compose(self) -> ComposeResult:
        phase = self.phase
        solved = phase['solved']
        target = phase['target']
        percentage = int((solved / target * 100)) if target > 0 else 0

        arrow = "▼" if self.expanded else "▶"

        with Collapsible(
            title=f"{phase['name']} - {solved}/{target} ({percentage}%)",
            collapsed=not self.expanded,
            classes="phase_collapsible"
        ):
            # Progress bar
            bar = ProgressBar(total=target, show_eta=False, classes="phase_progress")
            bar.update(progress=solved)
            yield bar

            # Topics
            for topic in phase['topics']:
                topic_solved = topic['solved']
                topic_target = topic['target']
                topic_pct = int((topic_solved / topic_target * 100)) if topic_target > 0 else 0

                bar_length = 15
                filled = int(bar_length * topic_pct / 100)
                bar_str = "█" * filled + "░" * (bar_length - filled)

                status = "✓" if topic_solved >= topic_target else ""

                # Show topic with problems if any solved
                if topic_solved > 0 and topic['problems']:
                    with Collapsible(
                        title=f"{topic['name']}: {topic_solved}/{topic_target} [{bar_str}] {status}",
                        collapsed=True,
                        classes="topic_collapsible"
                    ):
                        for i, problem in enumerate(topic['problems'], 1):
                            yield Label(f"  {i}. {problem}", classes="problem_item")
                else:
                    yield Label(
                        f"  • {topic['name']}: {topic_solved}/{topic_target} [{bar_str}] {status}",
                        classes="topic_label"
                    )


class CollapsibleSystemsModule(Static):
    """Collapsible widget for a Systems module"""

    def __init__(self, module: Dict, module_idx: int, progress_data: ProgressData):
        super().__init__()
        self.module = module
        self.module_idx = module_idx
        self.progress_data = progress_data
        self.expanded = (module_idx == 0)  # First module expanded by default

    def compose(self) -> ComposeResult:
        module = self.module
        total = len(module['topics'])
        completed = sum(1 for t in module['topics'] if t['completed'])
        percentage = int((completed / total * 100)) if total > 0 else 0

        bar_length = 10
        filled = int(bar_length * percentage / 100)
        bar_str = "█" * filled + "░" * (bar_length - filled)

        with Collapsible(
            title=f"{module['name']} - {completed}/{total} [{bar_str}] {percentage}%",
            collapsed=not self.expanded,
            classes="module_collapsible"
        ):
            for topic in module['topics']:
                checkbox = "[✓]" if topic['completed'] else "[ ]"

                # Show subtopics if available
                if 'subtopics' in topic and topic['subtopics']:
                    with Collapsible(
                        title=f"{checkbox} {topic['name']}",
                        collapsed=True,
                        classes="topic_collapsible"
                    ):
                        for subtopic in topic['subtopics']:
                            yield Label(f"  • {subtopic}", classes="subtopic_item")
                else:
                    yield Label(f"  {checkbox} {topic['name']}", classes="topic_label")


class CollapsibleBitLevel(Static):
    """Collapsible widget for a Bit-Systems level"""

    def __init__(self, level: Dict, level_idx: int, progress_data: ProgressData):
        super().__init__()
        self.level = level
        self.level_idx = level_idx
        self.progress_data = progress_data
        self.expanded = (level_idx == 0)  # First level expanded by default

    def compose(self) -> ComposeResult:
        level = self.level
        solved = level['exercises_solved']
        total = level['total_exercises']
        percentage = int((solved / total * 100)) if total > 0 else 0
        completed = level['completed']

        bar_length = 10
        filled = int(bar_length * percentage / 100)
        bar_str = "█" * filled + "░" * (bar_length - filled)

        # Mark as CRITICAL for level 4
        critical_mark = " ⚠️  CRITICAL" if level['id'] == 4 else ""
        complete_mark = " ✓" if completed else ""

        with Collapsible(
            title=f"Level {level['id']}: {level['name']}{critical_mark}{complete_mark} - {solved}/{total} [{bar_str}] {percentage}%",
            collapsed=not self.expanded,
            classes="level_collapsible"
        ):
            if level['exercises']:
                for exercise in level['exercises']:
                    yield Label(f"  ✓ {exercise}", classes="exercise_item")
            else:
                yield Label(f"  No exercises completed yet", classes="empty_label")


class CollapsibleProblemClass(Static):
    """Collapsible widget for a Bit-Systems problem class"""

    def __init__(self, problem_class: Dict, class_idx: int, progress_data: ProgressData):
        super().__init__()
        self.problem_class = problem_class
        self.class_idx = class_idx
        self.progress_data = progress_data
        self.expanded = (class_idx == 0)

    def compose(self) -> ComposeResult:
        pc = self.problem_class
        solved = pc['exercises_solved']
        total = pc['total_exercises']
        percentage = int((solved / total * 100)) if total > 0 else 0
        completed = pc['completed']

        bar_length = 10
        filled = int(bar_length * percentage / 100)
        bar_str = "█" * filled + "░" * (bar_length - filled)

        complete_mark = " ✓" if completed else ""

        with Collapsible(
            title=f"Class {pc['id']}: {pc['name']}{complete_mark} - {solved}/{total} [{bar_str}] {percentage}%",
            collapsed=not self.expanded,
            classes="class_collapsible"
        ):
            if pc['exercises']:
                for exercise in pc['exercises']:
                    yield Label(f"  ✓ {exercise}", classes="exercise_item")
            else:
                yield Label(f"  No exercises completed yet", classes="empty_label")


class ViewSolutionsScreen(Screen):
    """Interactive screen for viewing saved solutions"""

    BINDINGS = [
        Binding("up", "navigate_up", "Up", show=False),
        Binding("down", "navigate_down", "Down", show=False),
        Binding("j", "navigate_down", "Down", show=False),
        Binding("k", "navigate_up", "Up", show=False),
        Binding("enter", "select", "Select"),
        Binding("e", "edit_selected", "Edit"),
        Binding("q", "back", "Back"),
        Binding("escape", "back", "Back"),
    ]

    def __init__(self, session_solutions: List[Tuple[str, str]]):
        super().__init__()
        self.session_solutions = session_solutions
        self.selected_index = 0
        self.current_filepath = None

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="view_content"):
            yield Label("Saved Solutions", classes="section_title")
            yield Label("↑↓/jk to navigate | Enter/(e) to edit | (q) to go back", id="view_instructions")

            with VerticalScroll(id="solutions_area"):
                if self.session_solutions:
                    for i, (filename, filepath) in enumerate(self.session_solutions):
                        label_text = f"{'>' if i == 0 else ' '} {i+1}. {filename}"
                        yield Label(label_text, id=f"sol_{i}", classes="solution_item")
                else:
                    yield Label("No solutions saved yet", id="empty_message")

            with VerticalScroll(id="content_area"):
                yield Label("", id="file_content")

        yield Footer()

    def on_mount(self):
        """Automatically select and show first solution"""
        if self.session_solutions:
            self.show_solution_at_index(0)

    def update_selection_display(self):
        """Update the visual selection indicator"""
        for i in range(len(self.session_solutions)):
            label = self.query_one(f"#sol_{i}", Label)
            filename = self.session_solutions[i][0]
            prefix = ">" if i == self.selected_index else " "
            label.update(f"{prefix} {i+1}. {filename}")

    def show_solution_at_index(self, idx: int):
        """Show content of solution at given index"""
        if 0 <= idx < len(self.session_solutions):
            self.selected_index = idx
            filename, filepath = self.session_solutions[idx]
            self.current_filepath = filepath

            # Update selection display
            self.update_selection_display()

            # Read and display file content
            try:
                with open(filepath, 'r') as f:
                    content = f.read()

                content_label = self.query_one("#file_content", Label)
                content_label.update(f"File: {filename}\n{'='*50}\n\n{content}")

            except Exception as e:
                content_label = self.query_one("#file_content", Label)
                content_label.update(f"Error reading file: {e}")

    def action_navigate_up(self):
        """Navigate to previous solution"""
        if self.selected_index > 0:
            self.show_solution_at_index(self.selected_index - 1)

    def action_navigate_down(self):
        """Navigate to next solution"""
        if self.selected_index < len(self.session_solutions) - 1:
            self.show_solution_at_index(self.selected_index + 1)

    def action_select(self):
        """Select current item - opens editor"""
        self.action_edit_selected()

    def action_edit_selected(self):
        """Edit the currently selected/viewed solution"""
        if self.current_filepath:
            # Suspend the app to run vim
            with self.app.suspend():
                subprocess.run(["vim", str(self.current_filepath)])

            # Refresh content display after editing
            try:
                with open(self.current_filepath, 'r') as f:
                    content = f.read()

                filename = Path(self.current_filepath).name
                content_label = self.query_one("#file_content", Label)
                content_label.update(f"File: {filename}\n{'='*50}\n\n{content}")
            except Exception as e:
                pass

    def action_back(self):
        """Go back to solve mode"""
        self.app.pop_screen()


class SearchProblemScreen(ModalScreen[Optional[Tuple]]):
    """Find and select a tracked LeetCode problem by name."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    CSS = """
    SearchProblemScreen {
        align: center middle;
    }

    SearchProblemScreen #search_dialog {
        width: 72;
        height: auto;
        max-height: 26;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }

    SearchProblemScreen #search_title {
        text-style: bold;
        margin-bottom: 1;
    }

    SearchProblemScreen #search_results {
        height: auto;
        min-height: 5;
        max-height: 12;
        margin: 1 0;
    }

    SearchProblemScreen #search_buttons {
        height: 3;
        align-horizontal: right;
    }

    SearchProblemScreen #search_buttons Button {
        width: auto;
        min-width: 12;
        margin-left: 1;
    }
    """

    def __init__(self, problems: List[Tuple]):
        super().__init__()
        self.problems = problems

    def compose(self) -> ComposeResult:
        yield Container(
            Label("Search tracked problems", id="search_title"),
            Input(placeholder="Example: Move Zeroes", id="search_input"),
            Label("Type part of a problem name.", id="search_results"),
            Horizontal(
                Button("Load", id="search_load", variant="primary"),
                Button("Cancel", id="search_cancel"),
                id="search_buttons",
            ),
            id="search_dialog",
        )

    def on_mount(self) -> None:
        self.query_one("#search_input", Input).focus()

    def _matches(self, query: str) -> List[Tuple]:
        normalized = query.strip().lower()
        if not normalized:
            return []
        return [problem for problem in self.problems if normalized in problem[0].lower()]

    def _show_matches(self, query: str) -> None:
        results = self.query_one("#search_results", Label)
        matches = self._matches(query)
        if not query.strip():
            results.update("Type part of a problem name.")
        elif not matches:
            results.update("No tracked problems match.")
        else:
            preview = [
                f"{problem[0]}  ·  {problem[3]}  ·  {problem[4]}"
                for problem in matches[:8]
            ]
            if len(matches) > 8:
                preview.append(f"...and {len(matches) - 8} more")
            results.update("\n".join(preview))

    def _load_match(self) -> None:
        query = self.query_one("#search_input", Input).value.strip()
        matches = self._matches(query)
        exact_match = next(
            (problem for problem in matches if problem[0].lower() == query.lower()),
            None,
        )

        if exact_match:
            self.dismiss(exact_match)
        elif len(matches) == 1:
            self.dismiss(matches[0])
        elif not matches:
            self.query_one("#search_results", Label).update(
                "No tracked problems match."
            )
        else:
            self.query_one("#search_results", Label).update(
                f"{len(matches)} problems match. Type a more specific name.\n\n"
                + "\n".join(problem[0] for problem in matches[:8])
            )

    @on(Input.Changed, "#search_input")
    def search_changed(self, event: Input.Changed) -> None:
        self._show_matches(event.value)

    @on(Input.Submitted, "#search_input")
    def search_submitted(self) -> None:
        self._load_match()

    @on(Button.Pressed, "#search_load")
    def load_pressed(self) -> None:
        self._load_match()

    @on(Button.Pressed, "#search_cancel")
    def cancel_pressed(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class SolutionPreviewScreen(ModalScreen[None]):
    """Read-only, syntax-highlighted view of a saved solution."""

    BINDINGS = [
        Binding("s", "close", "Close", priority=True),
        Binding("q", "close", "Close", priority=True),
        Binding("escape", "close", "Close", priority=True),
    ]

    CSS = """
    SolutionPreviewScreen {
        align: center middle;
    }

    SolutionPreviewScreen #solution_preview_dialog {
        width: 90%;
        height: 90%;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }

    SolutionPreviewScreen #solution_preview_title {
        height: 1;
        text-style: bold;
    }

    SolutionPreviewScreen #solution_preview_path {
        height: 1;
        color: $text-muted;
        margin-bottom: 1;
    }

    SolutionPreviewScreen #solution_preview_editor {
        height: 1fr;
    }

    SolutionPreviewScreen #solution_preview_buttons {
        height: 3;
        align-horizontal: right;
        margin-top: 1;
    }

    SolutionPreviewScreen #solution_preview_close {
        width: auto;
        min-width: 12;
    }
    """

    def __init__(
        self,
        problem_name: str,
        solution_path: Path,
        language: str,
    ):
        super().__init__()
        self.problem_name = problem_name
        self.solution_path = solution_path
        self.language = language

    def compose(self) -> ComposeResult:
        config = LANGUAGES[self.language]
        editor = TextArea(
            text=self.solution_path.read_text(),
            language=None,
            theme="vscode_dark",
            read_only=True,
            show_line_numbers=True,
            soft_wrap=False,
            id="solution_preview_editor",
        )
        register_cpp_highlighting(editor)
        editor.language = config["editor_language"]

        yield Container(
            Label(
                f"Saved Solution — {self.problem_name} ({config['display_name']})",
                id="solution_preview_title",
            ),
            Label(str(self.solution_path), id="solution_preview_path"),
            editor,
            Horizontal(
                Button("Close", id="solution_preview_close", variant="primary"),
                id="solution_preview_buttons",
            ),
            id="solution_preview_dialog",
        )

    def on_mount(self) -> None:
        self.query_one("#solution_preview_editor", TextArea).focus()

    @on(Button.Pressed, "#solution_preview_close")
    def close_pressed(self) -> None:
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)


class SolveModeScreen(Screen):
    """Full screen for spaced repetition practice with split-screen editor"""

    BINDINGS = [
        Binding("g", "generate", "Generate"),
        Binding("ctrl+f", "search", "Search", priority=True),
        Binding("l", "language", "Language"),
        Binding("s", "solutions", "Solutions"),
        Binding("o", "open_url", "Open URL"),
        Binding("v", "visualize", "Visualize"),
        Binding("ctrl+s", "save", "Save"),
        Binding("q", "back", "Back"),
    ]

    CSS = """
    SolveModeScreen #split_container {
        height: 100%;
    }

    SolveModeScreen #problem_panel {
        width: 50%;
        height: 100%;
        border-right: solid green;
    }

    SolveModeScreen #code_panel {
        width: 50%;
        height: 100%;
    }

    SolveModeScreen #problem_scroll {
        height: 1fr;
        padding: 1 2;
    }

    SolveModeScreen #problem_text {
        width: 100%;
    }

    SolveModeScreen #code_editor {
        height: 1fr;
    }

    SolveModeScreen .section_title {
        background: $boost;
        padding: 1;
        text-style: bold;
    }
    """

    def __init__(self, progress_data: ProgressData):
        super().__init__()
        self.progress_data = progress_data
        self.current_problem = None
        self.current_problem_text = ""  # Store problem description for toggle
        self.current_solution_file = None
        self.current_editor_language = self.progress_data.get_preferred_language()
        self.last_problem_name = None  # Track last shown problem to avoid immediate repeats

    def compose(self) -> ComposeResult:
        yield Header()

        with Horizontal(id="split_container"):
            # Left panel: Problem description
            with Container(id="problem_panel"):
                yield Label("Problem Description", classes="section_title")
                with VerticalScroll(id="problem_scroll"):
                    yield Label("Press (g) to generate a random question from solved problems", id="problem_text")

            # Right panel: Code editor
            with Container(id="code_panel"):
                preferred_language = self.progress_data.get_preferred_language()
                yield Label(
                    f"Solution Editor ({LANGUAGE_NAMES[preferred_language]})",
                    id="solution_editor_title",
                    classes="section_title",
                )
                code_editor = TextArea(
                    text=self._empty_editor_text(preferred_language),
                    language=None,
                    theme="vscode_dark",
                    show_line_numbers=True,
                    tab_behavior="indent",
                    soft_wrap=False,
                    id="code_editor"
                )
                register_cpp_highlighting(code_editor)
                code_editor.language = LANGUAGES[preferred_language]["editor_language"]
                yield code_editor

        yield Footer()

    def on_mount(self):
        """Configure editor after mounting"""
        code_editor = self.query_one("#code_editor", TextArea)
        code_editor.indent_width = 4
        code_editor.indent_type = "spaces"

    def action_generate(self):
        """Generate random question from solved problems with weighted selection"""
        solved_problems = self.progress_data.get_all_solved_problems()

        if not solved_problems:
            problem_text = self.query_one("#problem_text", Label)
            problem_text.update("No solved problems found. Solve some problems first!")
            return

        # Filter out last shown problem to avoid immediate repeats
        candidates = solved_problems
        if self.last_problem_name and len(solved_problems) > 1:
            candidates = [p for p in solved_problems if p[0] != self.last_problem_name]

        # Weighted random selection based on days since last review
        weights = []
        for problem in candidates:
            problem_name, pattern, url, topic_name, phase_name, phase_id = problem
            days_since_review = self.progress_data.get_days_since_review(phase_id, topic_name, problem_name)

            # Weight calculation:
            # - Never reviewed: weight = 100 (highest priority)
            # - 1 day ago: weight = 1
            # - 7 days ago: weight = 7
            # - Recently reviewed problems have lower chance
            weight = days_since_review if days_since_review > 0 else 100
            weights.append(weight)

        # Pick problem using weighted random
        selected_problem = random.choices(candidates, weights=weights)[0]
        self._load_problem(selected_problem)

    def action_search(self):
        """Search solved problems by name and load the selected problem."""
        solved_problems = self.progress_data.get_all_solved_problems()
        if not solved_problems:
            self.notify("No solved problems found", severity="warning")
            return

        def handle_result(problem: Optional[Tuple]):
            if problem:
                self._load_problem(problem)

        self.app.push_screen(SearchProblemScreen(solved_problems), handle_result)

    def action_language(self):
        """Choose the language to use when the next problem is loaded."""
        current_language = self.progress_data.get_preferred_language()

        def handle_result(language: Optional[str]):
            if language:
                self.progress_data.set_preferred_language(language)
                language_name = LANGUAGE_NAMES[language]

                if self.current_problem:
                    self.notify(
                        f"Preferred language set to {language_name}; applies when you load the next problem",
                        severity="information",
                    )
                else:
                    self.current_editor_language = language
                    self._configure_editor_language(language)
                    self.query_one("#code_editor", TextArea).text = self._empty_editor_text(language)
                    self.notify(
                        f"Preferred language set to {language_name}",
                        severity="information",
                    )

        self.app.push_screen(
            LanguagePreferenceScreen(current_language),
            handle_result,
        )

    def _load_problem(self, problem: Tuple):
        """Load a selected problem into Solve mode."""
        problem_name, pattern, url, topic_name, phase_name, phase_id = problem
        self.last_problem_name = problem_name  # Remember for next generation

        # Mark as reviewed today
        self.progress_data.update_last_reviewed(phase_id, topic_name, problem_name)

        self.current_problem = {
            'name': problem_name,
            'pattern': pattern,
            'url': url,
            'topic': topic_name,
            'phase': phase_name,
            'phase_id': phase_id
        }

        language = self.progress_data.get_preferred_language()
        language_config = LANGUAGES[language]
        self.current_editor_language = language
        self._configure_editor_language(language)

        # Update problem description panel with text wrapping
        problem_text = self.query_one("#problem_text", Label)
        code_template = ""

        if url:
            problem_text.update("Fetching problem description...")
            problem_data = fetch_problem_description(
                url,
                language_config["leetcode_slug"],
            )

            if problem_data:
                # Wrap text to fit left panel (approx 60 chars wide)
                wrapped_desc = self.wrap_text(problem_data['description'], width=60)

                display_text = f"{problem_data['title']}\n{'=' * 60}\n\n"
                display_text += wrapped_desc
                display_text += f"\n\nTopic: {topic_name} | Phase: {phase_name}"
                if pattern:
                    display_text += f"\nPattern: {pattern}"
                display_text += "\n\nPress (o) to open in browser | Ctrl+S to save | (g) for next"
                problem_text.update(display_text)

                # Store for toggle
                self.current_problem_text = display_text

                # Get code template if available
                code_template = problem_data.get('code_template', '')
            else:
                fallback = f"Problem: {problem_name}\nTopic: {topic_name}\nPhase: {phase_name}\n"
                if pattern:
                    fallback += f"Pattern: {pattern}\n"
                fallback += f"\nFailed to fetch description\nURL: {url}"
                problem_text.update(fallback)
                self.current_problem_text = fallback
        else:
            basic_info = f"Problem: {problem_name}\nTopic: {topic_name}\nPhase: {phase_name}\n"
            if pattern:
                basic_info += f"Pattern: {pattern}\n"
            problem_text.update(basic_info)
            self.current_problem_text = basic_info

        # Setup code editor with template
        code_editor = self.query_one("#code_editor", TextArea)
        slug = self.extract_slug_from_url(url) if url else self.slugify_name(problem_name)
        solutions_dir = Path(__file__).parent.parent / "LEETCODE" / "solutions"
        self.current_solution_file = solutions_dir / f"{slug}{language_config['extension']}"

        # Load existing solution if available, otherwise create template
        if self.current_solution_file.exists():
            code_editor.text = self.current_solution_file.read_text()
        else:
            code_editor.text = self.build_solution_template(
                language,
                problem_name,
                topic_name,
                phase_name,
                pattern,
                code_template,
            )

    def _empty_editor_text(self, language: str) -> str:
        """Return a language-appropriate empty editor prompt."""
        prefix = LANGUAGES[language]["comment_prefix"]
        return f"{prefix} Load a problem to start solving\n"

    def _configure_editor_language(self, language: str) -> None:
        """Update the editor label and its currently available highlighter."""
        config = LANGUAGES[language]
        self.query_one("#solution_editor_title", Label).update(
            f"Solution Editor ({config['display_name']})"
        )
        self.query_one("#code_editor", TextArea).language = config["editor_language"]

    def build_solution_template(
        self,
        language: str,
        problem_name: str,
        topic_name: str,
        phase_name: str,
        pattern: str,
        code_template: str,
    ) -> str:
        """Build a small language-appropriate header plus LeetCode starter code."""
        prefix = LANGUAGES[language]["comment_prefix"]
        header = [
            f"{prefix} {problem_name}",
            f"{prefix} Topic: {topic_name}",
            f"{prefix} Phase: {phase_name}",
        ]
        if pattern:
            header.append(f"{prefix} Pattern: {pattern}")

        body = code_template.strip() or f"{prefix} Write your solution here"
        return "\n".join(header) + "\n\n" + body + "\n"

    def slugify_name(self, problem_name: str) -> str:
        """Create a stable solution filename when a problem has no URL."""
        return (
            problem_name.lower()
            .replace(" ", "_")
            .replace("(", "")
            .replace(")", "")
            .replace("/", "_")
        )

    def wrap_text(self, text: str, width: int = 60) -> str:
        """Wrap text to fit within specified width"""
        lines = text.split('\n')
        wrapped_lines = []

        for line in lines:
            if len(line) <= width:
                wrapped_lines.append(line)
            else:
                # Split long lines at word boundaries
                words = line.split()
                current_line = ""
                for word in words:
                    if len(current_line) + len(word) + 1 <= width:
                        current_line += (' ' + word if current_line else word)
                    else:
                        if current_line:
                            wrapped_lines.append(current_line)
                        current_line = word
                if current_line:
                    wrapped_lines.append(current_line)

        return '\n'.join(wrapped_lines)

    def extract_slug_from_url(self, url: str) -> str:
        """Extract slug from LeetCode URL and convert to filename"""
        # https://leetcode.com/problems/two-sum/ -> two-sum -> two_sum
        parts = url.rstrip('/').split('/')
        slug = parts[-1] if parts else "unknown"
        return slug.replace('-', '_')

    def action_solutions(self):
        """Open the current problem's saved solution in a read-only modal."""
        if not self.current_problem:
            self.notify("Generate a problem first!", severity="warning")
            return

        if self.current_solution_file is None:
            self.notify("No solution file is associated with this problem", severity="warning")
            return

        if not self.current_solution_file.exists():
            self.notify(
                f"No saved solution found: {self.current_solution_file.name}",
                severity="warning",
            )
            return

        self.app.push_screen(
            SolutionPreviewScreen(
                self.current_problem["name"],
                self.current_solution_file,
                self.current_editor_language,
            )
        )

    def action_open_url(self):
        """Open problem URL in browser"""
        if not self.current_problem or not self.current_problem.get('url'):
            self.notify("No URL available for this problem.", severity="warning")
            return

        url = self.current_problem['url']
        import webbrowser
        webbrowser.open(url)
        self.notify(f"Opened in browser: {url}")

    def action_visualize(self):
        """Open an interactive visualization for the current problem."""
        if not self.current_problem:
            self.notify("Generate a problem first!", severity="warning")
            return

        url = self.current_problem.get("url", "")
        if not url:
            self.notify("This problem has no URL/slug", severity="warning")
            return

        slug = self.extract_slug_from_url(url)
        visualizer = get_visualizer(slug)
        if visualizer is None:
            self.notify("No visualizer is available for this problem yet", severity="warning")
            return

        self.app.push_screen(
            ArrayVisualizerScreen(
                visualizer.title,
                visualizer.trace,
                visualizer.default_values,
            )
        )

    def action_save(self):
        """Save current solution to persistent file"""
        if not self.current_problem:
            self.notify("No problem loaded. Generate a problem first.", severity="warning")
            return

        code_editor = self.query_one("#code_editor", TextArea)

        if self.current_solution_file is None:
            self.notify("No solution file is associated with this problem", severity="warning")
            return

        self.current_solution_file.parent.mkdir(parents=True, exist_ok=True)
        self.current_solution_file.write_text(code_editor.text)

        self.notify(f"Saved: {self.current_solution_file.name}", severity="information")

    def action_back(self):
        """Go back to main dashboard"""
        self.app.pop_screen()


class AddProblemScreen(ModalScreen[bool]):
    """Modal screen for adding a solved problem"""

    BINDINGS = [
        Binding("escape", "dismiss", "Cancel"),
    ]

    def __init__(self, progress_data: ProgressData):
        super().__init__()
        self.progress_data = progress_data

    def compose(self) -> ComposeResult:
        yield Container(
            Label("Add Solved Problem", id="title"),
            Label("Phase (1-5):"),
            Input(placeholder="1", id="phase_input"),
            Label("Topic:"),
            Input(placeholder="Arrays, Strings, etc.", id="topic_input"),
            Label("Problem Name:"),
            Input(placeholder="Two Sum", id="problem_input"),
            Horizontal(
                Button("Add", variant="primary", id="add_btn"),
                Button("Cancel", variant="default", id="cancel_btn"),
                classes="buttons"
            ),
            id="add_problem_dialog"
        )

    @on(Button.Pressed, "#add_btn")
    def add_problem(self):
        """Handle add button press"""
        phase_input = self.query_one("#phase_input", Input)
        topic_input = self.query_one("#topic_input", Input)
        problem_input = self.query_one("#problem_input", Input)

        try:
            phase_id = int(phase_input.value)
            topic_name = topic_input.value.strip()
            problem_name = problem_input.value.strip()

            if 1 <= phase_id <= 5 and topic_name and problem_name:
                self.progress_data.add_problem(phase_id, topic_name, problem_name)
                self.dismiss(True)
        except ValueError:
            pass

    @on(Button.Pressed, "#cancel_btn")
    def cancel(self):
        """Handle cancel button press"""
        self.dismiss(False)


class LanguagePreferenceScreen(ModalScreen[Optional[str]]):
    """Choose the default language used for solutions."""

    BINDINGS = [
        Binding("c", "choose_cpp", "C++"),
        Binding("p", "choose_python", "Python"),
        Binding("escape", "cancel", "Cancel"),
    ]

    CSS = """
    LanguagePreferenceScreen {
        align: center middle;
    }

    LanguagePreferenceScreen #language_dialog {
        width: 52;
        height: auto;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }

    LanguagePreferenceScreen #language_title {
        text-style: bold;
        margin-bottom: 1;
    }

    LanguagePreferenceScreen #language_buttons {
        height: 3;
        align-horizontal: center;
    }

    LanguagePreferenceScreen #language_buttons Button {
        width: auto;
        min-width: 13;
        margin: 0 1;
    }
    """

    def __init__(self, current_language: str):
        super().__init__()
        self.current_language = current_language

    def compose(self) -> ComposeResult:
        current_name = LANGUAGE_NAMES[self.current_language]
        yield Container(
            Label("Preferred solution language", id="language_title"),
            Label(f"Current: {current_name}"),
            Horizontal(
                Button("C++", id="language_cpp", variant="primary"),
                Button("Python", id="language_python"),
                Button("Cancel", id="language_cancel"),
                id="language_buttons",
            ),
            id="language_dialog",
        )

    @on(Button.Pressed, "#language_cpp")
    def cpp_pressed(self) -> None:
        self.dismiss("cpp")

    @on(Button.Pressed, "#language_python")
    def python_pressed(self) -> None:
        self.dismiss("python")

    @on(Button.Pressed, "#language_cancel")
    def cancel_pressed(self) -> None:
        self.dismiss(None)

    def action_choose_cpp(self) -> None:
        self.dismiss("cpp")

    def action_choose_python(self) -> None:
        self.dismiss("python")

    def action_cancel(self) -> None:
        self.dismiss(None)


class DashboardScreen(Screen):
    """Main dashboard screen"""

    BINDINGS = [
        Binding("a", "add_problem", "Add Problem"),
        Binding("r", "refresh", "Refresh"),
        Binding("s", "solve", "Solve"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, progress_data: ProgressData):
        super().__init__()
        self.progress_data = progress_data

    def compose(self) -> ComposeResult:
        yield Header()

        data = self.progress_data.data
        meta = data['meta']
        leetcode = data['leetcode']
        systems = data['systems']
        bit_systems = data.get('bit_systems', {})

        # Stats header (compact)
        with Container(id="stats_header"):
            yield Label(f"Interview Prep Progress Tracker")
            yield Label(f"Started: {meta['start_date']}\n")
            yield Label(f"Days Active: {meta['total_days_active']}  \nStreak:  {meta['streak_days']} days")

        # Main content area
        with VerticalScroll(id="main_content"):
            # LeetCode section
            yield Label("━━━ ━━━ LEETCODE PROGRESS ━━━ ━━━", classes="section_title")

            total_solved = leetcode['total_solved']
            total_target = leetcode['total_target']
            overall_pct = int((total_solved / total_target * 100)) if total_target > 0 else 0

            yield Label(f"Overall: {total_solved}/{total_target} ({overall_pct}%)", classes="overall_label")

            overall_bar = ProgressBar(total=total_target, show_eta=False, classes="overall_progress")
            overall_bar.update(progress=total_solved)
            yield overall_bar

            # Phases
            for i, phase in enumerate(leetcode['phases']):
                yield CollapsiblePhase(phase, i, self.progress_data)

            # Systems section
            yield Label("━━━ ━━━ SYSTEMS PROGRESS ━━━ ━━━", classes="section_title")

            # Modules
            for i, module in enumerate(systems['modules']):
                yield CollapsibleSystemsModule(module, i, self.progress_data)

            # Bit-Systems section
            if bit_systems:
                yield Label("━━━ ━━━ BIT-SYSTEMS PROGRESS ━━━ ━━━", classes="section_title")

                levels_completed = bit_systems.get('levels_completed', 0)
                total_levels = bit_systems.get('total_levels', 8)
                bit_pct = int((levels_completed / total_levels * 100)) if total_levels > 0 else 0

                yield Label(f"Overall: {levels_completed}/{total_levels} levels complete ({bit_pct}%)", classes="overall_label")

                bit_bar = ProgressBar(total=total_levels, show_eta=False, classes="overall_progress")
                bit_bar.update(progress=levels_completed)
                yield bit_bar

                # The 8 Levels
                yield Label("The 8 Levels:", classes="subsection_label")
                for i, level in enumerate(bit_systems.get('levels', [])):
                    yield CollapsibleBitLevel(level, i, self.progress_data)

                # Problem Classes (if unlocked)
                if bit_systems.get('problem_classes_unlocked', False):
                    yield Label("🔓 Problem Classes (Interview Patterns):", classes="subsection_label")
                    for i, pc in enumerate(bit_systems.get('problem_classes', [])):
                        yield CollapsibleProblemClass(pc, i, self.progress_data)
                else:
                    yield Label("🔒 Problem Classes (Complete all 8 levels to unlock)", classes="locked_label")

        yield Footer()

    def action_add_problem(self):
        """Show add problem modal"""
        def handle_result(added: bool):
            if added:
                self.app.pop_screen()
                self.app.push_screen(DashboardScreen(self.progress_data))

        self.app.push_screen(AddProblemScreen(self.progress_data), handle_result)

    def action_solve(self):
        """Show solve mode screen"""
        self.app.push_screen(SolveModeScreen(self.progress_data))

    def action_refresh(self):
        """Refresh the dashboard"""
        self.progress_data.data = self.progress_data.load()
        self.app.pop_screen()
        self.app.push_screen(DashboardScreen(self.progress_data))

    def action_quit(self):
        """Quit the application"""
        self.app.exit()


class ProgressTrackerApp(App):
    """Main application"""

    CSS_PATH = "dashboard.tcss"

    def __init__(self):
        super().__init__()
        self.progress_data = ProgressData()

    def on_mount(self):
        """Mount the main dashboard screen"""
        self.push_screen(DashboardScreen(self.progress_data))


if __name__ == "__main__":
    app = ProgressTrackerApp()
    app.run()
