import subprocess
import time
import sys

print("Starte Test von battery-check.py mit 5s Intervall...")
p = subprocess.Popen([sys.executable, 'battery-check.py', '5'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

start_t = time.time()
while time.time() - start_t < 15:
    line = p.stdout.readline()
    if line:
        print(line.strip())
    if p.poll() is not None:
        break

p.terminate()
print("Test beendet.")
