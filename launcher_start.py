import os
import sys
import subprocess

def main():
    base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    runtime_dir = os.path.join(base_dir, "runtime")
    pythonw = os.path.join(runtime_dir, "pythonw.exe")
    python_exe = os.path.join(runtime_dir, "python.exe")
    exe_to_use = pythonw if os.path.exists(pythonw) else python_exe

    target_script = os.path.join(base_dir, "bridge_loader.py")
    subprocess.Popen([exe_to_use, target_script], cwd=base_dir)

if __name__ == "__main__":
    main()