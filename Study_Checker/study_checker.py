import contextlib
import json
import math
import os
import shutil
import sys
import tempfile
import calendar
from datetime import date, timedelta

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
    from tkinter import font as tkfont
except ImportError:
    # Many Linux/Homebrew Pythons ship without Tk; say how to get it instead of a bare traceback.
    sys.exit(
        "Study Checker needs Python's Tk support (tkinter), which isn't installed.\n"
        "  Debian/Ubuntu: sudo apt install python3-tk\n"
        "  Fedora:        sudo dnf install python3-tkinter\n"
        "  macOS (brew):  brew install python-tk\n"
        "  Otherwise, install Python from python.org, which includes Tk."
    )

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _data_dir():
    # Running from source: keep the data next to the script.
    if not getattr(sys, "frozen", False):
        return SCRIPT_DIR
    # Packaged app: the bundle is read-only (macOS) or a temp dir (Windows onefile),
    # so store data in the per-user location instead.
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    path = os.path.join(base, "StudyChecker")
    os.makedirs(path, mode=0o700, exist_ok=True)
    return path


DATA_FILE = os.path.join(_data_dir(), "study_data.json")
ICON_FILE = os.path.join(getattr(sys, "_MEIPASS", SCRIPT_DIR), "study_checker.ico")

CATEGORIES = ["School", "Coding", "Hacking"]
GOALS = {"School": 40, "Coding": 20, "Hacking": 15}
CATEGORY_COLORS = {"School": "#3b82f6", "Coding": "#22c55e", "Hacking": "#a855f7"}
MAX_HOURS = 24  # per category per day
# Color emoji can crash older Tk builds on X11 (BadLength), so Linux gets plain text.
FLAME = "" if sys.platform.startswith("linux") else "🔥 "


def _valid_hours(v):
    return (
        isinstance(v, (int, float))
        and not isinstance(v, bool)
        and math.isfinite(v)
        and 0 <= v <= MAX_HOURS
    )


def _backup_bad_file():
    backup = DATA_FILE + ".corrupt"
    try:
        shutil.copy2(DATA_FILE, backup)
        return backup
    except OSError:
        return None


def _read_data():
    """Read and validate the data file. Returns (clean, dropped).

    The file is plain JSON that can be hand-edited or damaged, so nothing in it is trusted.
    Raises OSError/ValueError (bad JSON, bad UTF-8, wrong shape) if it can't be used at all.
    """
    if not os.path.exists(DATA_FILE):
        return {}, 0

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise ValueError("expected a JSON object")

    clean, dropped = {}, 0
    for key, entry in raw.items():
        try:
            date.fromisoformat(key)
        except (TypeError, ValueError):
            dropped += 1
            continue
        if not isinstance(entry, dict):
            dropped += 1
            continue
        clean[key] = {}
        for cat in CATEGORIES:
            v = entry.get(cat, 0)
            if not _valid_hours(v):
                dropped += 1
                v = 0
            clean[key][cat] = float(v)
    return clean, dropped


def load_data():
    """Return (data, problem). problem is a message for the user, or None if the file was fine.

    A bad file starts empty (after being backed up) and bad entries are dropped.
    """
    try:
        clean, dropped = _read_data()
    except (OSError, ValueError) as e:
        backup = _backup_bad_file()
        saved = f"A copy was saved as:\n{backup}" if backup else "It could not be backed up."
        return {}, f"{os.path.basename(DATA_FILE)} couldn't be read ({e}).\n\n{saved}\n\nStarting with an empty log."

    if dropped:
        backup = _backup_bad_file()
        saved = f"The original was copied to:\n{backup}" if backup else "It could not be backed up."
        return clean, f"{dropped} invalid value(s) in {os.path.basename(DATA_FILE)} were ignored.\n\n{saved}"
    return clean, None


@contextlib.contextmanager
def _file_lock():
    """Cross-process lock so two running copies can't interleave a read-modify-write.

    The OS drops it if the process dies, so there's no stale lock file to clean up.
    """
    with open(DATA_FILE + ".lock", "a+b") as lock:
        if sys.platform == "win32":
            import msvcrt

            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if sys.platform == "win32":
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            # elsewhere the flock is released when the file closes


def update_day(key, values):
    """Set one day (or clear it, if every value is zero) on top of what's on disk right now.

    Merging into the current file, not this process's older snapshot, is what stops a second
    running copy from erasing the first one's entries. Returns the merged data.
    """
    with _file_lock():
        try:
            data, dropped = _read_data()
        except ValueError as e:
            # Don't overwrite a file we can't understand; the user's data may still be in it.
            raise OSError(
                f"{os.path.basename(DATA_FILE)} was changed on disk and can't be read ({e}). "
                "Not overwriting it."
            ) from e
        if dropped:
            _backup_bad_file()
        if any(v > 0 for v in values.values()):
            data[key] = values
        else:
            data.pop(key, None)
        save_data(data)
        return data


def save_data(data):
    # Write to a temp file and swap it in, so a crash mid-write can't truncate the real one.
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(DATA_FILE), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, allow_nan=False)
        os.replace(tmp, DATA_FILE)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


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
            if not math.isfinite(hrs):
                messagebox.showerror("Invalid input", f"'{raw}' isn't a valid number for {cat}.")
                return
            if hrs < 0:
                messagebox.showerror("Invalid input", f"{cat} hours can't be negative.")
                return
            if hrs > MAX_HOURS:
                messagebox.showerror("Invalid input", f"{cat} hours can't exceed {MAX_HOURS} in a day.")
                return
            result[cat] = hrs
        self.on_save(self.target_date, result)
        self.destroy()


class StudyCheckerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Study Checker")
        self.resizable(False, False)
        self._set_icon()
        self._fonts = {}  # keep references, or Tk drops the fonts when they're collected

        self.data, problem = load_data()
        if problem:
            self.after(200, lambda: messagebox.showwarning("Study Checker", problem, parent=self))
        today = date.today()
        self.view_year = today.year
        self.view_month = today.month

        self._build_stats_bar()
        self._build_nav_bar()
        self._build_calendar_frame()
        self._build_summary_frame()

        self.render_all()
        self.bind("<FocusIn>", self._on_focus_in)

    def _set_icon(self):
        # .ico only works with iconbitmap on Windows; on macOS/Linux it errors or is ignored.
        if sys.platform != "win32" or not os.path.exists(ICON_FILE):
            return
        try:
            self.iconbitmap(ICON_FILE)
        except tk.TclError:
            pass

    def font(self, size, bold=False):
        """Platform default UI font (Segoe UI on Windows, system font on macOS) at a given size."""
        key = (size, bold)
        if key not in self._fonts:
            f = tkfont.nametofont("TkDefaultFont").copy()
            f.configure(size=size, weight="bold" if bold else "normal")
            self._fonts[key] = f
        return self._fonts[key]

    def _build_stats_bar(self):
        frame = ttk.Frame(self, padding=(12, 10, 12, 0))
        frame.grid(row=0, column=0, columnspan=2, sticky="ew")

        self.stats_var = tk.StringVar()
        ttk.Label(frame, textvariable=self.stats_var, font=self.font(10, bold=True)).grid(
            row=0, column=0, sticky="w"
        )

    def _build_nav_bar(self):
        frame = ttk.Frame(self, padding=(12, 10, 12, 6))
        frame.grid(row=1, column=0, sticky="ew")

        ttk.Button(frame, text="<", width=3, command=self.prev_month).grid(row=0, column=0)
        self.month_label_var = tk.StringVar()
        ttk.Label(frame, textvariable=self.month_label_var, font=self.font(12, bold=True)).grid(
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
            msg = f"{FLAME}{streak}-day streak! Nice work today."
        else:
            msg = f"{FLAME}{streak}-day streak — log today to keep it alive."
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
            ttk.Label(self.cal_frame, text=name, font=self.font(9, bold=True)).grid(
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
        tk.Label(cell, text=str(day.day), bg=cell["bg"], fg=fg, font=self.font(9, bold=True)).pack(
            anchor="nw", padx=4, pady=2
        )

        marks = tk.Frame(cell, bg=cell["bg"])
        marks.pack(anchor="w", padx=4)
        for cat in CATEGORIES:
            done = logged.get(cat, 0) > 0
            mark = "✓" if done else "·"
            color = CATEGORY_COLORS[cat] if done else "#cbd5e1"
            tk.Label(
                marks, text=f"{cat[0]}{mark}", bg=cell["bg"], fg=color, font=self.font(8)
            ).pack(side="left", padx=1)

        for widget in (cell, *cell.winfo_children(), *marks.winfo_children()):
            widget.bind("<Button-1>", lambda e, d=day: self.open_day_dialog(d))

    def open_day_dialog(self, target_date):
        key = target_date.isoformat()
        existing = self.data.get(key, {})
        DayDialog(self, target_date, existing, self.on_day_saved)

    def on_day_saved(self, target_date, values):
        try:
            self.data = update_day(target_date.isoformat(), values)
        except OSError as e:
            # self.data is untouched, so the screen still matches what's on disk.
            messagebox.showerror("Couldn't save", f"Your changes were not saved:\n{e}")
            return
        self.render_all()

    def render_all(self):
        self.render_calendar()
        self.render_summary()
        self.render_stats()

    def refresh_from_disk(self):
        """Pick up changes another running copy saved. Quietly does nothing if the file can't be read."""
        try:
            with _file_lock():
                data, _ = _read_data()
        except (OSError, ValueError):
            return
        if data != self.data:
            self.data = data
            self.render_all()

    def _on_focus_in(self, event):
        if event.widget is self:  # FocusIn also fires for every child widget
            self.refresh_from_disk()

    def render_summary(self):
        for widget in self.summary_frame.winfo_children():
            widget.destroy()

        start, end = week_bounds(date.today())
        ttk.Label(
            self.summary_frame,
            text=f"This Week\n{start.strftime('%b %d')} – {end.strftime('%b %d')}",
            font=self.font(10, bold=True),
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
