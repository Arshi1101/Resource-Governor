import argparse, os, random, time
ap = argparse.ArgumentParser()
ap.add_argument('--mode', choices=['cpu', 'mem'], default='cpu')
ap.add_argument('--calm', type=float, default=90)
ap.add_argument('--spike', type=float, default=90)
ap.add_argument('--tail', type=float, default=0)
a = ap.parse_args()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def busy(sec):
    end = time.time() + sec
    while time.time() < end:
        pass

hold = [os.urandom(20 * 1024 * 1024)] if a.mode == 'mem' else []
end = time.time() + a.calm
while time.time() < end:
    busy(random.uniform(0.05, 0.15))
    time.sleep(0.9)

os.makedirs(os.path.join(ROOT, 'data'), exist_ok=True)
with open(os.path.join(ROOT, 'data', 'spike_marker.txt'), 'w') as f:
    f.write(str(time.time()))

end = time.time() + a.spike
while time.time() < end:
    if a.mode == 'cpu':
        busy(0.5)
    else:
        hold.append(os.urandom(20 * 1024 * 1024))
        time.sleep(1)

end = time.time() + a.tail
while time.time() < end:
    busy(random.uniform(0.05, 0.15))
    time.sleep(0.9)
