import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, 'data', 'governor.db')

SAMPLE_INTERVAL = 1.0
MODE = 'adaptive'
DRY_RUN = False

WARMUP_SAMPLES = 60
EWMA_ALPHA = 0.02
Z_THRESHOLD = 3.0
SUSTAIN_SAMPLES = 10
COOLDOWN_SECONDS = 30
CPU_FLOOR = 50.0
MEM_FLOOR_MB = 800.0
MIN_STD_CPU = 5.0
MIN_STD_MEM = 100.0
RECOVER_Z = 1.5

STATIC_CPU = 80.0
STATIC_MEM_MB = 1000.0

PROTECTED = {'system', 'system idle process', 'registry', 'smss.exe', 'csrss.exe',
             'wininit.exe', 'services.exe', 'lsass.exe', 'winlogon.exe', 'dwm.exe',
             'kernel_task', 'launchd', 'windowserver', 'loginwindow', 'systemd',
             'streamlit.exe', 'python:streamlit', 'python:victim.py'}

POLICY_PATH = os.path.join(ROOT, 'policy.json')
BASELINE_PATH = os.path.join(ROOT, 'data', 'baselines.json')

SEASONAL = True
SEASON_BLOCK_HOURS = 4
PROTECT_FOREGROUND = True
BATTERY_AWARE = True

LEAK_WINDOW = 120
LEAK_MIN_MB_PER_MIN = 20.0
LEAK_MIN_R2 = 0.9
VERIFY_AFTER = 15

DESKTOP_NOTIFY = True
WEBHOOK_URL = ''

LADDER_MAC = [0, 5, 19]
CLASSES = {
    'interactive': {'base': 0, 'max': 1},
    'normal':      {'base': 0, 'max': 2},
    'background':  {'base': 1, 'max': 2},
}
PROMOTE_AFTER_CALM = 60
BOOST_SECONDS = 300
