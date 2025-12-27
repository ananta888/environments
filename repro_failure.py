
import subprocess
import os

def run(cmd):
    return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)

if __name__ == "__main__":
    print("Testing failing command...")
    try:
        # 'powercfg' with invalid argument should fail
        run(["powercfg", "/invalid_arg"])
    except Exception as e:
        print(f"Caught expected exception: {type(e).__name__}: {e}")

    print("\nTesting non-existent command...")
    try:
        run(["non_existent_command_12345"])
    except Exception as e:
        print(f"Caught expected exception: {type(e).__name__}: {e}")
