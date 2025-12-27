
import time
import importlib.util
import threading
import sys
from datetime import datetime

# Load battery-check.py
spec = importlib.util.spec_from_file_location("battery_check", "battery-check.py")
bc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bc)

# Mock battery_percent_and_status to fail on the SECOND call (first call in loop)
original_func = bc.battery_percent_and_status
call_count = 0

def mocked_func():
    global call_count
    call_count += 1
    if call_count == 2:
        print("MOCK: Triggering simulated error...")
        raise RuntimeError("Simulierter transienter Fehler im Loop")
    if call_count > 5:
        print("MOCK: Stopping test...")
        raise KeyboardInterrupt()
    return original_func()

bc.battery_percent_and_status = mocked_func

# Mock time.sleep to not wait too long
def mocked_sleep(seconds):
    print(f"(Sleeping for {seconds}s - mocked)")
    pass

bc.time.sleep = mocked_sleep

if __name__ == "__main__":
    try:
        print("Starting main test...")
        bc.main(interval_sec=0.1, capacity_mwh=50000)
    except KeyboardInterrupt:
        print("Main stopped as expected")
    except Exception as e:
        print(f"Main crashed unexpectedly: {e}")
    print("Finished testing loop resilience.")
