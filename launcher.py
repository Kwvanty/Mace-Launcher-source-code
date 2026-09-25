import os
import subprocess
import sys
import shutil

# Папка, где находится launcher.py
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# run.py находится рядом с launcher.py
run_file = os.path.join(BASE_DIR, "run.py")

if not os.path.isfile(run_file):
    sys.exit(1)

# Определяем путь к Python
embedded_python = os.path.join(BASE_DIR, "python", "python.exe")
if os.path.isfile(embedded_python):
    python_exe = embedded_python
else:
    python_exe = shutil.which("python")

if not python_exe:
    sys.exit(1)

try:
    # Флаг CREATE_NO_WINDOW принудительно скрывает консоль для всех дочерних скриптов (run.py, gui.py и т.д.)
    creation_flags = 0
    if os.name == "nt":
        creation_flags = subprocess.CREATE_NO_WINDOW

    subprocess.Popen(
        [python_exe, run_file],
        cwd=BASE_DIR,
        creationflags=creation_flags
    )
except Exception:
    sys.exit(1)