# Study Checker

A small desktop app for logging daily study hours (School, Coding, Hacking), with a monthly
calendar, a weekly goal tracker, and a streak counter. Works on Windows, macOS and Linux.

## Run from source

Requires Python 3.8+ with Tk (tkinter). No other dependencies.

```
python study_checker.py
```

If you get a "needs Tk" message:

| OS | Fix |
| --- | --- |
| Debian / Ubuntu | `sudo apt install python3-tk` |
| Fedora | `sudo dnf install python3-tkinter` |
| macOS | Install Python from [python.org](https://www.python.org/downloads/) (the built-in one has an outdated Tk), or `brew install python-tk` |
| Windows | Included with the python.org installer |

## Build a standalone app

```
pip install -r requirements-build.txt
pyinstaller --noconfirm study_checker.spec
```

| OS | Result |
| --- | --- |
| Windows | `dist/StudyChecker.exe` |
| macOS | `dist/StudyChecker.app` |
| Linux | `dist/StudyChecker` |

PyInstaller can't cross-compile, so build on the OS you want to target. The
[GitHub Actions workflow](.github/workflows/build.yml) builds all three on every push and
uploads them as artifacts.

Notes on the built apps:

- **macOS:** the app is unsigned, so Gatekeeper will block the first launch. Right-click the
  app and choose Open. The CI build is Apple Silicon only.
- **Linux:** the binary needs a glibc at least as new as the machine it was built on.

## Where your data is stored

Your log is a plain JSON file, `study_data.json`.

| How you run it | Location |
| --- | --- |
| From source | next to `study_checker.py` |
| Windows app | `%APPDATA%\StudyChecker\` |
| macOS app | `~/Library/Application Support/StudyChecker/` |
| Linux app | `~/.local/share/StudyChecker/` |
