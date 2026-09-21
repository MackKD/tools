# PyInstaller build recipe for all platforms. Run from this folder:
#
#     pyinstaller --noconfirm study_checker.spec
#
# Windows: dist/StudyChecker.exe   Linux: dist/StudyChecker   macOS: dist/StudyChecker.app
import sys

WIN = sys.platform == "win32"
MAC = sys.platform == "darwin"

# Only Windows loads the .ico at runtime (see _set_icon); the file's own icon is set below.
datas = [("study_checker.ico", ".")] if WIN else []
icon = "study_checker.icns" if MAC else "study_checker.ico"

a = Analysis(["study_checker.py"], datas=datas)
pyz = PYZ(a.pure)

if MAC:
    # A one-file windowed build is deprecated on macOS; ship a proper .app bundle instead.
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="StudyChecker", console=False, icon=icon)
    coll = COLLECT(exe, a.binaries, a.datas, name="StudyChecker")
    app = BUNDLE(coll, name="StudyChecker.app", icon=icon)
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="StudyChecker", console=False, icon=icon)
