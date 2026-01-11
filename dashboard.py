#!/usr/bin/env python3
"""
Interview Prep Progress Tracker - Interactive Dashboard
"""

import json
import random
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import (
    Header, Footer, Static, ProgressBar, Button,
    Label, Input, Collapsible
)
from textual.binding import Binding
from textual.screen import Screen, ModalScreen
from textual import on


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

    def get_all_solved_problems(self) -> List[Tuple[str, str, str, int]]:
        """Get all solved problems as list of (problem_name, topic_name, phase_name, phase_id)"""
        solved = []
        for phase in self.data['leetcode']['phases']:
            phase_name = phase['name']
            phase_id = phase['id']
            for topic in phase['topics']:
                topic_name = topic['name']
                for problem in topic['problems']:
                    solved.append((problem, topic_name, phase_name, phase_id))
        return solved


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


class SolveModeScreen(Screen):
    """Full screen for spaced repetition practice"""

    BINDINGS = [
        Binding("g", "generate", "Generate"),
        Binding("e", "edit", "Edit"),
        Binding("v", "view", "View"),
        Binding("n", "next", "Next"),
        Binding("q", "back", "Back"),
    ]

    def __init__(self, progress_data: ProgressData):
        super().__init__()
        self.progress_data = progress_data
        self.current_problem = None
        self.current_problem_text = ""  # Track current display text
        self.session_solutions = []  # List of (problem_name, file_path) tuples
        self.temp_dir = Path(tempfile.mkdtemp(prefix="leetcode_solve_"))

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="solve_content"):
            yield Label("Solve Mode - Spaced Repetition", classes="section_title")
            yield Label("Press (g) to generate a random question from solved problems", id="solve_instructions")
            with Container(id="problem_display"):
                yield Label("", id="problem_text")

        yield Footer()

    def action_generate(self):
        """Generate random question from solved problems"""
        solved_problems = self.progress_data.get_all_solved_problems()

        if not solved_problems:
            # No solved problems yet
            problem_text = self.query_one("#problem_text", Label)
            problem_text.update("No solved problems found. Solve some problems first!")
            return

        # Pick random problem
        problem_name, topic_name, phase_name, phase_id = random.choice(solved_problems)
        self.current_problem = {
            'name': problem_name,
            'topic': topic_name,
            'phase': phase_name,
            'phase_id': phase_id
        }

        # Update display
        self.current_problem_text = (
            f"Problem: {problem_name}\n"
            f"Topic: {topic_name}\n"
            f"Phase: {phase_name}"
        )
        problem_text = self.query_one("#problem_text", Label)
        problem_text.update(self.current_problem_text)

    def action_edit(self):
        """Open vim editor for solution"""
        # Determine filename
        if self.current_problem:
            # Clean problem name for filename (remove spaces, special chars)
            problem_name = self.current_problem['name']
            clean_name = problem_name.replace(" ", "_").replace("(", "").replace(")", "").replace("/", "_")
            filename = f"{clean_name}.py"
        else:
            # No problem generated, use generic name
            filename = "solution.py"

        # Create temp file path
        file_path = self.temp_dir / filename

        # Check if this problem already has a solution file
        existing_solution = next((sol for sol in self.session_solutions if sol[0] == filename), None)
        if existing_solution:
            file_path = Path(existing_solution[1])

        # Suspend the app to run vim
        with self.app.suspend():
            editor = subprocess.run(["vim", str(file_path)])

        # If file exists and has content, track it
        if file_path.exists() and file_path.stat().st_size > 0:
            if not existing_solution:
                self.session_solutions.append((filename, str(file_path)))

                # Only show saved message once (when first saved)
                # Remove any existing saved message first
                base_text = self.current_problem_text.split("\n\n[Solution saved")[0]
                self.current_problem_text = f"{base_text}\n\n[Solution saved to: {filename}]"
                problem_text = self.query_one("#problem_text", Label)
                problem_text.update(self.current_problem_text)

    def action_view(self):
        """View solutions from this session"""
        if not self.session_solutions:
            self.current_problem_text = "No solutions saved in this session yet."
            problem_text = self.query_one("#problem_text", Label)
            problem_text.update(self.current_problem_text)
            return

        # Push to interactive view screen
        self.app.push_screen(ViewSolutionsScreen(self.session_solutions))

    def action_next(self):
        """Generate next random question"""
        self.action_generate()

    def action_back(self):
        """Go back to main dashboard"""
        # Clean up temp files
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
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
