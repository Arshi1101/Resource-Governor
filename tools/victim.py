import csv, os, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.makedirs(os.path.join(ROOT, 'data'), exist_ok=True)
with open(os.path.join(ROOT, 'data', 'victim_log.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['ts', 'ops'])
    while True:
        t, n = time.time(), 0
        while time.time() - t < 1.0:
            x = 0
            for _ in range(20000):
                x += 1
            n += 1
        w.writerow([time.time(), n])
        f.flush()
