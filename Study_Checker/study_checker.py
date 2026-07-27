import json
import os
import calendar
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, timedelta

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "study_data.json")
ICON_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "study_checker.ico")

CATEGORIES = ["School", "Coding", "Hacking"]
GOALS = {"School": 40, "Coding": 20, "Hacking": 15}
CATEGORY_COLORS = {"School": "#3b82f6", "Coding": "#22c55e", "Hacking": "#a855f7"}

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def week_bounds(d):
    start = d - timedelta(days=d.weekday())
    end = start + timedelta(days=6)
    return start, end


class DayDialog(tk.Toplevel):
    def __init__(self, parent, target_date, existing, on_save):
        super().__init__(parent)
        self.title(target_date.strftime("%A, %B %d, %Y"))
        self.resizable(False, False)
        self.on_save = on_save
        self.target_date = target_date
        self.entries = {}

        container = ttk.Frame(self, padding=16)
        container.grid()

        for i, cat in enumerate(CATEGORIES):
            ttk.Label(container, text=f"{cat} (hrs):").grid(row=i, column=0, sticky="w", pady=4)
            var = tk.StringVar(value=str(existing.get(cat, 0)))
            entry = ttk.Entry(container, textvariable=var, width=8)
            entry.grid(row=i, column=1, pady=4, padx=(8, 0))
            self.entries[cat] = var

        btn_frame = ttk.Frame(container)
        btn_frame.grid(row=len(CATEGORIES), column=0, columnspan=2, pady=(12, 0))
        ttk.Button(btn_frame, text="Save", command=self.save).grid(row=0, column=0, padx=4)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).grid(row=0, column=1, padx=4)

        self.grab_set()

    def save(self):
        result = {}
        for cat, var in self.entries.items():
            raw = var.get().strip()
            try:
                hrs = float(raw) if raw else 0.0
            except ValueError:
                messagebox.showerror("Invalid input", f"'{raw}' isn't a valid number for {cat}.")
                return
            if hrs < 0:
                messagebox.showerror("Invalid input", f"{cat} hours can't be negative.")
                return
            result[cat] = hrs
        self.on_save(self.target_date, result)
        self.destroy()


class StudyCheckerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Study Checker")
        self.resizable(False, False)
        if os.path.exists(ICON_FILE):
            self.iconbitmap(ICON_FILE)

        self.data = load_data()
        today = date.today()
        self.view_year = today.year
        self.view_month = today.month

        self._build_stats_bar()
        self._build_nav_bar()
        self._build_calendar_frame()
        self._build_summary_frame()

        self.render_calendar()
        self.render_summary()
        self.render_stats()

    def _build_stats_bar(self):
        frame = ttk.Frame(self, padding=(12, 10, 12, 0))
        frame.grid(row=0, column=0, columnspan=2, sticky="ew")

        self.stats_var = tk.StringVar()
        ttk.Label(frame, textvariable=self.stats_var, font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, sticky="w"
        )

    def _build_nav_bar(self):
        frame = ttk.Frame(self, padding=(12, 10, 12, 6))
        frame.grid(row=1, column=0, sticky="ew")

        ttk.Button(frame, text="<", width=3, command=self.prev_month).grid(row=0, column=0)
        self.month_label_var = tk.StringVar()
        ttk.Label(frame, textvariable=self.month_label_var, font=("Segoe UI", 12, "bold")).grid(
            row=0, column=1, padx=10
        )
        ttk.Button(frame, text=">", width=3, command=self.next_month).grid(row=0, column=2)
        ttk.Button(frame, text="Today", command=self.log_today).grid(row=0, column=3, padx=(20, 0))

    def _build_calendar_frame(self):
        self.cal_frame = ttk.Frame(self, padding=12)
        self.cal_frame.grid(row=2, column=0, sticky="n")

    def _build_summary_frame(self):
        self.summary_frame = ttk.Frame(self, padding=12, relief="groove", borderwidth=1)
        self.summary_frame.grid(row=2, column=1, sticky="n", padx=(0, 12))

    def _compute_streak(self):
        today = date.today()

        def logged(d):
            entry = self.data.get(d.isoformat())
            return bool(entry) and any(v > 0 for v in entry.values())

        if logged(today):
            start, today_logged = today, True
        elif logged(today - timedelta(days=1)):
            start, today_logged = today - timedelta(days=1), False
        else:
            return 0, False

        streak = 0
        d = start
        while logged(d):
            streak += 1
            d -= timedelta(days=1)
        return streak, today_logged

    def render_stats(self):
        streak, today_logged = self._compute_streak()
        if streak == 0:
            msg = "No streak yet — log today to start one."
        elif today_logged:
            msg = f"🔥 {streak}-day streak! Nice work today."
        else:
            msg = f"🔥 {streak}-day streak — log today to keep it alive."
        self.stats_var.set(msg)

    def prev_month(self):
        self.view_month -= 1
        if self.view_month == 0:
            self.view_month = 12
            self.view_year -= 1
        self.render_calendar()

    def next_month(self):
        self.view_month += 1
        if self.view_month == 13:
            self.view_month = 1
            self.view_year += 1
        self.render_calendar()

    def log_today(self):
        self.view_year, self.view_month = date.today().year, date.today().month
        self.render_calendar()
        self.open_day_dialog(date.today())

    def render_calendar(self):
        for widget in self.cal_frame.winfo_children():
            widget.destroy()

        self.month_label_var.set(calendar.month_name[self.view_month] + f" {self.view_year}")

        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for col, name in enumerate(day_names):
            ttk.Label(self.cal_frame, text=name, font=("Segoe UI", 9, "bold")).grid(
                row=0, column=col, padx=2, pady=2
            )

        cal = calendar.Calendar(firstweekday=0)
        weeks = cal.monthdatescalendar(self.view_year, self.view_month)

        for r, week in enumerate(weeks, start=1):
            for c, day in enumerate(week):
                self._render_day_cell(day, r, c)

    def _render_day_cell(self, day, row, col):
        in_month = day.month == self.view_month
        is_today = day == date.today()
        key = day.isoformat()
        logged = self.data.get(key, {})

        cell = tk.Frame(
            self.cal_frame,
            width=76,
            height=64,
            highlightbackground="#2563eb" if is_today else "#d1d5db",
            highlightthickness=2 if is_today else 1,
            bg="white" if in_month else "#f3f4f6",
        )
        cell.grid(row=row, column=col, padx=2, pady=2)
        cell.grid_propagate(False)

        fg = "black" if in_month else "#9ca3af"
        tk.Label(cell, text=str(day.day), bg=cell["bg"], fg=fg, font=("Segoe UI", 9, "bold")).pack(
            anchor="nw", padx=4, pady=2
        )

        marks = tk.Frame(cell, bg=cell["bg"])
        marks.pack(anchor="w", padx=4)
        for cat in CATEGORIES:
            done = logged.get(cat, 0) > 0
            mark = "✓" if done else "·"
            color = CATEGORY_COLORS[cat] if done else "#cbd5e1"
            tk.Label(
                marks, text=f"{cat[0]}{mark}", bg=cell["bg"], fg=color, font=("Segoe UI", 8)
            ).pack(side="left", padx=1)

        for widget in (cell, *cell.winfo_children(), *marks.winfo_children()):
            widget.bind("<Button-1>", lambda e, d=day: self.open_day_dialog(d))

    def open_day_dialog(self, target_date):
        key = target_date.isoformat()
        existing = self.data.get(key, {})
        DayDialog(self, target_date, existing, self.on_day_saved)

    def on_day_saved(self, target_date, values):
        key = target_date.isoformat()
        if any(v > 0 for v in values.values()):
            self.data[key] = values
        elif key in self.data:
            del self.data[key]
        save_data(self.data)
        self.render_calendar()
        self.render_summary()
        self.render_stats()

    def render_summary(self):
        for widget in self.summary_frame.winfo_children():
            widget.destroy()

        start, end = week_bounds(date.today())
        ttk.Label(
            self.summary_frame,
            text=f"This Week\n{start.strftime('%b %d')} – {end.strftime('%b %d')}",
            font=("Segoe UI", 10, "bold"),
            justify="center",
        ).grid(row=0, column=0, pady=(0, 10))

        totals = {cat: 0.0 for cat in CATEGORIES}
        d = start
        while d <= end:
            entry = self.data.get(d.isoformat(), {})
            for cat in CATEGORIES:
                totals[cat] += entry.get(cat, 0)
            d += timedelta(days=1)

        for i, cat in enumerate(CATEGORIES, start=1):
            goal = GOALS[cat]
            done = totals[cat]
            pct = min(done / goal, 1.0) * 100 if goal else 0

            ttk.Label(self.summary_frame, text=f"{cat}: {done:.1f} / {goal} hrs").grid(
                row=i * 2 - 1, column=0, sticky="w", pady=(6, 0)
            )
            bar = ttk.Progressbar(self.summary_frame, length=200, maximum=100, value=pct)
            bar.grid(row=i * 2, column=0, sticky="w")


if __name__ == "__main__":
    app = StudyCheckerApp()
    app.mainloop()
