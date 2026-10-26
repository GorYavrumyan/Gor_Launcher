import os
import sys
import subprocess


def main():
    base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    runtime_dir = os.path.join(base_dir, "runtime")
    target_script = os.path.join(base_dir, "bridge_loader.py")

    if os.name == "nt":
        # Windows: встроенный Python из runtime/ (pythonw - без окна консоли)
        pythonw = os.path.join(runtime_dir, "pythonw.exe")
        python_exe = os.path.join(runtime_dir, "python.exe")
        exe_to_use = pythonw if os.path.exists(pythonw) else python_exe
        if not os.path.exists(exe_to_use):
            exe_to_use = sys.executable
        subprocess.Popen([exe_to_use, target_script], cwd=base_dir)
    else:
        # Linux / macOS: системный Python (или venv в runtime/ / .venv/)
        candidates = [
            os.path.join(base_dir, ".venv", "bin", "python3"),
            os.path.join(runtime_dir, "bin", "python3"),
        ]
        exe_to_use = next((p for p in candidates if os.path.exists(p)), None) or sys.executable or "python3"
        subprocess.Popen([exe_to_use, target_script], cwd=base_dir, start_new_session=True)


if __name__ == "__main__":
    main()
