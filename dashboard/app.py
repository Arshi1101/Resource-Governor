import os
import re
import sqlite3
import sys
import time
from datetime import datetime

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from governor import config as cfg


def make_icon():
    im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, 63, 63), radius=12, fill=(15, 94, 99, 255))
    d.line([(10, 44), (22, 30), (32, 38), (44, 18), (54, 30)],
           fill=(255, 255, 255, 255), width=6, joint="curve")
    return im


st.set_page_config(page_title="Resource Governor", page_icon=make_icon(),
                   layout="wide", initial_sidebar_state="collapsed")

dashboard_component = components.declare_component(
    'resource_governor_dashboard',
    path=os.path.abspath(os.path.join(os.path.dirname(__file__), 'component')),
)

st.markdown("""
<style>
[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], footer, #MainMenu { display: none !important; }
.block-container { padding: 0 !important; max-width: 100% !important; }
[data-testid="stVerticalBlock"] { gap: 0 !important; }
iframe { width: 100% !important; height: 100vh !important; border: 0 !important; display: block; }
</style>
""", unsafe_allow_html=True)

TZ = datetime.now().astimezone().tzinfo
LIVE_WINDOW_MINUTES = 10
LIVE_REFRESH_SECONDS = 5
QNAME = {0: 'Q0 · Normal', 1: 'Q1 · Reduced', 2: 'Q2 · Lowest'}


def query(sql, params=()):
    if not os.path.exists(cfg.DB_PATH):
        return pd.DataFrame()
    try:
        with sqlite3.connect(cfg.DB_PATH, timeout=5) as con:
            frame = pd.read_sql_query(sql, con, params=params)
    except sqlite3.Error:
        return pd.DataFrame()
    if 'ts' in frame.columns:
        frame['time'] = pd.to_datetime(frame['ts'], unit='s', utc=True).dt.tz_convert(TZ).dt.tz_localize(None)
    return frame


def queue_level(action, note):
    matches = re.findall(r'Q(\d)', str(note or ''))
    if matches:
        level = int(matches[-1])
        return level if level in QNAME else None
    action = str(action or '')
    if action.startswith('throttle_L'):
        try:
            level = int(action.rsplit('L', 1)[1])
            return level if level in QNAME else None
        except ValueError:
            return None
    return None


def safe_num(value, digits=None):
    if pd.isna(value):
        return None
    value = float(value)
    return round(value, digits) if digits is not None else value


def live_data():
    now = time.time()
    since = now - LIVE_WINDOW_MINUTES * 60
    samples = query('SELECT ts, pid, key, cpu FROM samples WHERE ts >= ?', (now - 15,))
    meta = query('SELECT ts, gov_cpu, gov_rss_mb, cycle_ms FROM meta WHERE ts >= ?', (since,))
    events = query('SELECT ts, pid, key, action, note FROM events WHERE ts >= ? ORDER BY ts', (since,))
    queue_events = query(
        'SELECT ts, pid, key, action, note FROM events WHERE ts >= ? ORDER BY ts',
        (now - 86400,),
    )
    event_cols = ['ts', 'pid', 'key', 'action', 'note', 'time']
    if events.empty:
        events = pd.DataFrame(columns=event_cols)
    events['level'] = [queue_level(a, n) for a, n in zip(events.action, events.note)]
    if queue_events.empty:
        queue_events = pd.DataFrame(columns=event_cols)
    queue_events['level'] = [queue_level(a, n) for a, n in zip(queue_events.action, queue_events.note)]
    queue_events = queue_events[queue_events.level.notna()].copy()
    window_events = events

    latest_queue = {}
    if not queue_events.empty:
        latest_queue = queue_events.sort_values('ts').groupby('pid').tail(1).set_index('pid').level.to_dict()
    current = pd.DataFrame()
    if not samples.empty:
        current = samples[samples.ts >= now - 15].sort_values('ts').drop_duplicates('pid', keep='last').copy()
        if not current.empty:
            current['queue'] = current.pid.map(latest_queue).fillna(0).astype(int)

    recent_moves = window_events[window_events.level.notna() | window_events.action.astype(str).str.startswith('verify_')].copy()
    recent_moves = recent_moves.sort_values('ts', ascending=False).head(40)
    queues = []
    for level in range(3):
        group = current[current.queue == level].sort_values('cpu', ascending=False) if not current.empty else current
        queues.append([{'program': str(row.key), 'pid': int(row.pid), 'cpu': safe_num(row.cpu, 1)}
                       for row in group.head(12).itertuples()])

    top = query('SELECT key, MAX(cpu) AS peak FROM samples WHERE ts >= ? GROUP BY key ORDER BY peak DESC LIMIT 4', (since,))
    top_keys = top.key.astype(str).tolist() if not top.empty else []
    cpu_series = []
    if top_keys:
        placeholders = ','.join('?' for _ in top_keys)
        grouped = query(
            'SELECT CAST(ts / 5 AS INTEGER) * 5 AS bucket, key, AVG(cpu) AS cpu '
            f'FROM samples WHERE ts >= ? AND key IN ({placeholders}) '
            'GROUP BY bucket, key ORDER BY bucket',
            (since, *top_keys),
        )
        if not grouped.empty:
            for bucket, frame in grouped.groupby('bucket', sort=True):
                cpu_series.append({'t': float(bucket), 'values': {
                    str(row.key): safe_num(row.cpu, 1) for row in frame.itertuples()
                }})

    q_timeline = []
    if not queue_events.empty:
        changes = queue_events[queue_events.ts >= since].copy()
        changes['proc'] = changes.key.astype(str) + ' #' + changes.pid.astype(str)
        counts = changes.proc.value_counts()
        chosen = set(counts.head(5).index)
        changes = changes[changes.proc.isin(chosen)].sort_values('ts')
        q_timeline = [{'t': safe_num(r.ts), 'proc': str(r.proc), 'level': int(r.level)} for r in changes.itertuples()]

    overhead = []
    if not meta.empty:
        compact_meta = meta.copy()
        compact_meta['bucket'] = (compact_meta.ts // 5).astype(int)
        compact_meta = compact_meta.groupby('bucket', as_index=False).agg(
            ts=('ts', 'last'), gov_cpu=('gov_cpu', 'mean'), cycle_ms=('cycle_ms', 'mean'))
        for row in compact_meta.itertuples():
            overhead.append({'t': safe_num(row.ts), 'cpu': safe_num(row.gov_cpu, 3), 'cycle': safe_num(row.cycle_ms, 3)})

    def move_record(row):
        return {'t': safe_num(row.ts), 'pid': safe_num(row.pid), 'program': str(row.key or ''),
                'action': str(row.action or ''), 'note': str(row.note or '')}

    demotions = int(window_events.action.astype(str).str.startswith('throttle_L').sum()) if not window_events.empty else 0
    return {
        'now': now, 'since': since, 'window': LIVE_WINDOW_MINUTES,
        'samples': int(len(samples)), 'latest_sample': safe_num(samples.ts.max()) if not samples.empty else None,
        'metrics': {
            'demotions': demotions,
            'promotions': int((window_events.action == 'promote').sum()) if not window_events.empty else 0,
            'boosts': int((window_events.action == 'boost').sum()) if not window_events.empty else 0,
            'effective': int((window_events.action == 'verify_effective').sum()) if not window_events.empty else 0,
            'gov_cpu': safe_num(meta.gov_cpu.mean(), 2) if not meta.empty else None,
            'gov_memory': safe_num(meta.gov_rss_mb.mean(), 1) if not meta.empty else None,
            'cycle': safe_num(meta.cycle_ms.mean(), 1) if not meta.empty else None,
        },
        'queues': queues,
        'queue_timeline': q_timeline,
        'moves': [move_record(row) for row in recent_moves.itertuples()],
        'top_keys': top_keys,
        'cpu_series': cpu_series,
        'overhead': overhead,
    }


@st.fragment(run_every=f'{LIVE_REFRESH_SECONDS}s')
def dashboard():
    dashboard_component(live_data=live_data(), key='resource-governor-dashboard')


dashboard()
