import json
import math
import time
import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import messagebox, ttk

STATS_FILE = Path("pomodoro_stats.json")
BG, RING_BG, TEXT = "#1e2028", "#3a3d4a", "#f2f2f2"
COLORS = {"Focus": "#e5534b", "Short break": "#4caf7a", "Long break": "#4c8bf5"}

class PomodoroTimer:
    def __init__(self, focus: int = 25, short: int = 5, long: int = 15, long_every: int = 4):
        self.minutes = {"Focus": focus, "Short break": short, "Long break": long}
        self.long_every = long_every
        self.mode = "Focus"
        self.completed = 0
        self.running = False
        self.remaining = float(self.total)

    @property
    def total(self) -> int:
        return self.minutes[self.mode] * 60

    def toggle(self) -> None:
        self.running = not self.running

    def reset(self) -> None:
        self.running = False
        self.remaining = float(self.total)

    def set_minutes(self, focus: int, short: int, long: int) -> None:
        """Change durations; restart the current phase only if it hasn't begun."""
        untouched = self.remaining == self.total
        self.minutes = {"Focus": focus, "Short break": short, "Long break": long}
        if untouched:
            self.remaining = float(self.total)

    def tick(self, seconds: float) -> str | None:
        """Advance time. Returns the phase that just finished, or None."""
        if not self.running:
            return None
        self.remaining -= seconds
        if self.remaining > 0:
            return None
        finished = self.mode
        if finished == "Focus":
            self.completed += 1
            long_break = self.completed % self.long_every == 0
            self._switch("Long break" if long_break else "Short break")
        else:
            self._switch("Focus")
        return finished

    def skip(self) -> None:
        """Jump to the next phase without counting it as completed."""
        self._switch("Short break" if self.mode == "Focus" else "Focus")

    def _switch(self, mode: str) -> None:
        self.mode = mode
        self.running = False  
        self.remaining = float(self.total)

def load_stats() -> dict[str, int]:
    try:
        data = json.loads(STATS_FILE.read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def record_session() -> int:
    """Add one finished focus session to today's count and return the new count."""
    stats = load_stats()
    today = date.today().isoformat()
    stats[today] = stats.get(today, 0) + 1
    try:
        STATS_FILE.write_text(json.dumps(stats, indent=2))
    except OSError:
        pass  
    return stats[today]


def read_minutes(var: tk.IntVar, default: int) -> int:
    try:
        return min(max(var.get(), 1), 120)
    except tk.TclError:  
        return default

class PomodoroApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.timer = PomodoroTimer()
        self.today = load_stats().get(date.today().isoformat(), 0)
        self.last_tick = time.monotonic()
        self.vars = {
            "Focus": tk.IntVar(value=25),
            "Short break": tk.IntVar(value=5),
            "Long break": tk.IntVar(value=15),
        }
        self.build_ui()
        self.loop()

    def build_ui(self) -> None:
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("TButton", padding=8)

        self.canvas = tk.Canvas(self.root, width=280, height=280, bg=BG, highlightthickness=0)
        self.canvas.pack(padx=20, pady=(20, 5))
        self.canvas.create_oval(20, 20, 260, 260, outline=RING_BG, width=14)
        self.arc = self.canvas.create_arc(
            20, 20, 260, 260, start=90, extent=-359.99, style=tk.ARC, width=14
        )
        self.time_text = self.canvas.create_text(140, 125, fill=TEXT, font=("Helvetica", 44, "bold"))
        self.mode_text = self.canvas.create_text(140, 175, fill=TEXT, font=("Helvetica", 14))

        self.stats_label = ttk.Label(self.root)
        self.stats_label.pack()

        buttons = ttk.Frame(self.root)
        buttons.pack(pady=12)
        self.start_btn = ttk.Button(buttons, text="Start", command=self.toggle)
        self.start_btn.grid(row=0, column=0, padx=4)
        ttk.Button(buttons, text="Reset", command=self.reset).grid(row=0, column=1, padx=4)
        ttk.Button(buttons, text="Skip", command=self.skip).grid(row=0, column=2, padx=4)

        settings = ttk.Frame(self.root)
        settings.pack(pady=(0, 20))
        for col, (mode, var) in enumerate(self.vars.items()):
            ttk.Label(settings, text=f"{mode} (min)").grid(row=0, column=col, padx=6)
            box = ttk.Spinbox(
                settings, from_=1, to=120, width=4, textvariable=var, command=self.apply_settings
            )
            box.grid(row=1, column=col, padx=6)
            box.bind("<Return>", lambda _event: self.apply_settings())
            box.bind("<FocusOut>", lambda _event: self.apply_settings())

    def toggle(self) -> None:
        self.timer.toggle()
        self.last_tick = time.monotonic()
        self.refresh()

    def reset(self) -> None:
        self.timer.reset()
        self.refresh()

    def skip(self) -> None:
        self.timer.skip()
        self.refresh()

    def apply_settings(self) -> None:
        current = self.timer.minutes
        values = [read_minutes(var, current[mode]) for mode, var in self.vars.items()]
        self.timer.set_minutes(*values)
        self.refresh()

    def loop(self) -> None:
        now = time.monotonic()
        finished = self.timer.tick(now - self.last_tick)
        self.last_tick = now
        self.refresh()
        self.root.after(200, self.loop)
        if finished:
            self.notify(finished)

    def notify(self, finished: str) -> None:
        if finished == "Focus":
            self.today = record_session()
            self.refresh()
            message = f"Focus session complete! Up next: {self.timer.mode.lower()}."
        else:
            message = "Break's over. Ready to focus?"
        self.root.bell()
        self.root.lift()
        messagebox.showinfo("Pomodoro", message)
        self.last_tick = time.monotonic()

    def refresh(self) -> None:
        timer = self.timer
        minutes, seconds = divmod(max(0, math.ceil(timer.remaining)), 60)
        clock = f"{minutes:02d}:{seconds:02d}"
        fraction = timer.remaining / timer.total

        self.canvas.itemconfig(self.time_text, text=clock)
        self.canvas.itemconfig(self.mode_text, text=timer.mode)
        self.canvas.itemconfig(self.arc, extent=-min(359.99, 360 * fraction), outline=COLORS[timer.mode])
        self.start_btn.config(text="Pause" if timer.running else "Start")
        self.stats_label.config(text=f"Focus sessions today: {self.today}")
        self.root.title(f"{clock} · {timer.mode}")  # visible even when minimized


def main() -> None:
    root = tk.Tk()
    PomodoroApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
