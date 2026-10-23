import os, re, sys, time, sqlite3
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import altair as alt
import pandas as pd
import streamlit as st
from governor import config as cfg
from governor import feedback

st.set_page_config(page_title='Resource Governor: live', layout='wide')
st.title('Resource Governor: live')
TZ = datetime.now().astimezone().tzinfo
window = st.sidebar.slider('History window (minutes)', 1, 60, 10)
refresh = st.sidebar.selectbox('Refresh every (seconds)', [1, 2, 5], index=0)
QNAME = {0: 'Q0 Normal', 1: 'Q1 Reduced', 2: 'Q2 Lowest'}
EV_COLS = ['ts', 'pid', 'key', 'metric', 'value', 'z', 'action', 'old_prio', 'new_prio', 'note']


def q(sql, params=()):
    if not os.path.exists(cfg.DB_PATH):
        return pd.DataFrame()
    con = sqlite3.connect(cfg.DB_PATH, timeout=5)
    try:
        df = pd.read_sql_query(sql, con, params=params)
    finally:
        con.close()
    if 'ts' in df:
        df['time'] = pd.to_datetime(df['ts'], unit='s', utc=True).dt.tz_convert(TZ).dt.tz_localize(None)
    return df


def level_of(action, note):
    nums = re.findall(r'Q(\d)', note or '')
    if nums:
        return int(nums[-1])
    if str(action).startswith('throttle_L'):
        return int(str(action)[-1])
    return None


@st.fragment(run_every='%ds' % refresh)
def live():
    now = time.time()
    since = now - window * 60
    s = q('SELECT * FROM samples WHERE ts >= ?', (since,))
    m = q('SELECT * FROM meta WHERE ts >= ?', (since,))
    ev = q('SELECT * FROM events WHERE ts >= ? ORDER BY ts', (now - 86400,))
    if s.empty:
        st.info('Waiting for data. Start the governor: python -m governor.main')
        return
    if ev.empty:
        ev = pd.DataFrame(columns=EV_COLS + ['time'])
    ev['level'] = [level_of(a, n) for a, n in zip(ev.action, ev.note)]
    sched = ev[ev.level.notna()]

    last = sched.sort_values('ts').groupby('pid').tail(1).set_index('pid').level.to_dict()
    cur = s[s.ts >= now - 15].sort_values('ts').drop_duplicates('pid', keep='last').copy()
    cur['queue'] = cur.pid.map(last).fillna(0).astype(int)
    cur['cpu'] = cur.cpu.round(1)

    w = ev[ev.ts >= since]
    a, b, c, d, e = st.columns(5)
    a.metric('Demotions', int(w.action.str.startswith('throttle_L').sum()))
    b.metric('Promotions', int((w.action == 'promote').sum()))
    c.metric('Aging boosts', int((w.action == 'boost').sum()))
    d.metric('Verified effective', int((w.action == 'verify_effective').sum()))
    e.metric('Governor CPU (avg %)', '%.2f' % m.gov_cpu.mean() if not m.empty else '-')

    st.subheader('Scheduling queues, right now')
    for lv, col in enumerate(st.columns(3)):
        sub = cur[cur.queue == lv].sort_values('cpu', ascending=False)
        col.markdown('**%s**' % QNAME[lv])
        col.metric('Processes', len(sub))
        col.dataframe(sub[['key', 'pid', 'cpu']].rename(columns={'key': 'program', 'cpu': 'CPU %'}).head(12),
                      hide_index=True, use_container_width=True)

    st.subheader('Queue level over time')
    tl = sched[sched.ts >= since].copy()
    if tl.empty:
        st.caption('No queue changes in this window yet.')
    else:
        tl['proc'] = tl.key + ' #' + tl.pid.astype(str)
        ids = tl.proc.value_counts().head(8).index
        tl = tl[tl.proc.isin(ids)][['time', 'proc', 'level']]
        end = tl.sort_values('time').groupby('proc').tail(1).copy()
        end['time'] = pd.Timestamp.now()
        tl = pd.concat([tl, end])
        st.altair_chart(alt.Chart(tl).mark_line(interpolate='step-after', point=True).encode(
            x=alt.X('time:T', title=None),
            y=alt.Y('level:Q', scale=alt.Scale(domain=[0, 2], reverse=True),
                    axis=alt.Axis(values=[0, 1, 2], title='queue')),
            color=alt.Color('proc:N', title='process')), use_container_width=True)

    st.subheader('Queue movements')
    mv = w[w.level.notna() | w.action.str.startswith('verify_')]
    if mv.empty:
        st.caption('Nothing has moved in this window.')
    else:
        st.dataframe(mv.sort_values('ts', ascending=False)[['time', 'pid', 'key', 'action', 'note']],
                     hide_index=True, use_container_width=True)

    st.subheader('CPU % (100 = one core), top programs')
    top = s.groupby('key').cpu.max().nlargest(8).index
    st.line_chart(s[s.key.isin(top)].pivot_table(index='time', columns='key', values='cpu', aggfunc='max'))

    if not m.empty:
        st.subheader('Governor overhead')
        st.line_chart(m.set_index('time')[['gov_cpu', 'cycle_ms']])
        st.subheader('Teach the governor')
    recent = w[w.action.str.startswith('throttle_L')].sort_values('ts', ascending=False).drop_duplicates('key').head(6)
    if recent.empty:
        st.caption('Interventions will appear here for you to review.')
    for _, r in recent.iterrows():
        col1, col2, col3 = st.columns([3, 1, 1])
        col1.write('%s at %s, CPU %.0f%%' % (r.key, r.time.strftime('%H:%M:%S'), r.value))
        if col2.button('False alarm', key='fa%s' % r.ts):
            feedback.submit(r.key, 'false_alarm')
            st.toast('Noted. %s will be judged less strictly.' % r.key)
        if col3.button('Real issue', key='ri%s' % r.ts):
            feedback.submit(r.key, 'real_issue')
            st.toast('Noted. %s will be judged more strictly.' % r.key)

live()
