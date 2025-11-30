import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import datetime

# ---------------------------
# 설정
# ---------------------------
API_KEY = "f2907b0b1e074198de1ba6fb1928665f"
BASE_URL = "http://api.openweathermap.org/data/2.5/forecast"
GEO_URL = "http://api.openweathermap.org/geo/1.0/direct"
AIR_URL = "http://api.openweathermap.org/data/2.5/air_pollution"

W_DESC = {
    "clear sky": "맑음", "few clouds": "조금 구름",
    "scattered clouds": "구름 많음", "broken clouds": "흐림",
    "overcast clouds": "흐림", "light rain": "약한 비",
    "moderate rain": "비", "heavy intensity rain": "강한 비",
    "light snow": "약한 눈", "snow": "눈",
    "mist": "안개", "fog": "짙은 안개", "thunderstorm": "천둥"
}

AQI_TEXT = {
    1: ("좋음", "🟢"), 2: ("보통", "🟡"), 3: ("나쁨", "🟠"),
    4: ("매우 나쁨", "🔴"), 5: ("최악", "⚫")
}

KR_WEEKDAYS = {0: '월', 1: '화', 2: '수', 3: '목', 4: '금', 5: '토', 6: '일'}

# ---------------------------
# 유틸
# ---------------------------

def fix_icon(code: str) -> str:
    if not code:
        return code
    if code.endswith('n'):
        code = code[:-1] + 'd'
    if code == '04d':
        return '03d'
    return code


def init_state():
    ss = st.session_state
    ss.setdefault('searched', False)
    ss.setdefault('data', None)


# ---------------------------
# 데이터 페치
# ---------------------------

def load_weather(city: str):
    """지오코드, 예보, 대기질 정보를 받아 세션에 저장한다."""
    ss = st.session_state
    try:
        q = f"{city},KR" if any(0xAC00 <= ord(c) <= 0xD7A3 for c in city) else city
        geo_resp = requests.get(GEO_URL, params={"q": q, "limit": 1, "appid": API_KEY}, timeout=8)
        geo = geo_resp.json()
        if not geo:
            st.error(f"'{city}' 지역을 찾을 수 없습니다.")
            ss.searched = False
            return

        lat, lon = geo[0]["lat"], geo[0]["lon"]
        name_kr = geo[0].get("local_names", {}).get("ko", city)

        w_resp = requests.get(BASE_URL, params={"lat": lat, "lon": lon, "appid": API_KEY, "units": "metric", "lang": "en"}, timeout=8)
        w = w_resp.json()

        air_resp = requests.get(AIR_URL, params={"lat": lat, "lon": lon, "appid": API_KEY}, timeout=8)
        air = air_resp.json()

        ss.data = {"name": name_kr, "lat": lat, "lon": lon, "w": w, "air": air}
        ss.searched = True
    except requests.RequestException as e:
        st.error("네트워크 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.")
        ss.searched = False


# ---------------------------
# 데이터 처리
# ---------------------------

def process_forecast(w: dict):
    """API 응답(w)에서 시간별 df와 일별 요약(daily)을 반환한다."""
    items = w.get('list', [])
    df = pd.DataFrame([
        {
            'dt': pd.to_datetime(it['dt_txt']).tz_localize('UTC').tz_convert('Asia/Seoul'),
            'temp': it['main']['temp'],
            'feel': it['main']['feels_like'],
            '최저_raw': it['main']['temp_min'],
            '최고_raw': it['main']['temp_max'],
            'icon': it['weather'][0]['icon'],
            '강수': it.get('pop', 0) * 100
        }
        for it in items
    ])

    daily = df.groupby(df['dt'].dt.date).agg(
        최고=('최고_raw', 'max'),
        최저=('최저_raw', 'min'),
        대표=('icon', lambda x: x.mode()[0] if not x.mode().empty else x.iloc[0]),
        강수=('강수', 'mean')
    ).reset_index().rename(columns={'dt': '날짜'})

    # 요일/라벨 유지 (오늘/내일/요일)
    today = datetime.datetime.now().date()
    daily['요일'] = daily['index'] = daily['dt'] = daily['날짜'] if '날짜' in daily else daily['index']
    # 위는 안전장치; 아래처럼 실제 요일 값을 계산
    daily['요일'] = daily['날짜'].apply(lambda x: '오늘' if x == today else ('내일' if x == today + datetime.timedelta(days=1) else KR_WEEKDAYS[x.weekday()]))
    daily['강수'] = daily['강수'].round(0)

    return df, daily


# ---------------------------
# 주간 조언 (유지)
# ---------------------------

def weekly_summary(daily: pd.DataFrame, air: dict) -> str:
    avg_max = daily['최고'].mean()
    msg = []

    if avg_max >= 27:
        msg.append("이번 주는 더운 편입니다. 시원한 복장을 추천합니다.")
    elif avg_max >= 16:
        msg.append("날씨가 활동하기 좋습니다.")
    elif avg_max >= 5:
        msg.append("날씨가 쌀쌀한 편입니다. 가벼운 외투를 챙기세요.")
    else:
        msg.append("추운 날씨가 예상됩니다. 따뜻하게 입으세요.")

    daily['일교차'] = daily['최고'] - daily['최저']
    d = daily['일교차'].mean()
    if d >= 10:
        msg.append(f"평균 일교차가 {d:.1f}°C로 큽니다.")

    rain_days = (daily['강수'] >= 50).sum()
    if rain_days >= len(daily) / 2:
        msg.append("비 소식이 많은 주간입니다. 우산을 챙기세요.")

    if air and 'list' in air:
        aqi = air['list'][0]['main']['aqi']
        if aqi >= 3:
            txt, _ = AQI_TEXT.get(aqi, ("알 수 없음", ""))
            msg.append(f"대기 질이 '{txt}' 수준입니다. 마스크 착용을 추천합니다.")

    return "\n\n".join(msg)


# ---------------------------
# UI
# ---------------------------

init_state()
ss = st.session_state

st.title("국내 날씨 / 미세먼지")

# --- 상단 검색 (원본 UI 유지) ---
city_in = st.text_input("지역 입력", "서울")
if st.button("조회", key='top_search'):
    if city_in:
        load_weather(city_in)
        if not st.session_state.searched:
            st.stop()
    else:
        st.warning("도시 이름을 입력해 주세요.")

if not ss.searched:
    st.stop()

# --- 데이터 로드 ---
data = ss.data
w = data['w']
air = data.get('air')
city = data['name']
lat, lon = data['lat'], data['lon']

# --- 상단 현재 날씨 ---
st.header(city)

now = w['list'][0]
t = now['main']['temp']
fl = now['main']['feels_like']
desc_en = now['weather'][0]['description']
desc = W_DESC.get(desc_en, desc_en)
icon = fix_icon(now['weather'][0]['icon'])

# 24시간 최고/최저
tlist = w['list'][:8]
tmin = min(x['main']['temp_min'] for x in tlist)
tmax = max(x['main']['temp_max'] for x in tlist)

# 시간 포맷 (KST)
dt_utc = pd.to_datetime(now['dt_txt']).tz_localize('UTC')
weekday_kr = KR_WEEKDAYS[dt_utc.tz_convert('Asia/Seoul').weekday()]
time_date = dt_utc.tz_convert('Asia/Seoul').strftime('%m월 %d일')
time_time = dt_utc.tz_convert('Asia/Seoul').strftime('오후 %I:%M')
display_time = f"{time_date} {weekday_kr}요일, {time_time}"

st.markdown(
    f"""
    <div style="display:flex;align-items:center;gap:10px;">
        <h1 style="margin:0">{int(t)}°</h1>
        <img src="http://openweathermap.org/img/wn/{icon}@2x.png" width="70">
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(f"**{desc}**")
st.markdown(f"⬆️{tmax:.0f}° / ⬇️{tmin:.0f}°")
st.markdown(f"체감온도 {fl:.0f}°")
st.markdown(display_time)
st.divider()

# --- 시간별 예보 (UI 유지) ---
st.subheader("시간별 예보")
cols = st.columns(len(tlist))
for i, item in enumerate(tlist):
    with cols[i]:
        kst_time = pd.to_datetime(item['dt_txt']).tz_localize('UTC').tz_convert('Asia/Seoul').strftime('%H시')
        ti = item['main']['temp']
        p = item.get('pop', 0) * 100
        ic = fix_icon(item['weather'][0]['icon'])
        st.markdown(
            f"""
            <div style="text-align:center; padding:5px;">
                <p style="font-weight:bold; margin-bottom:5px;">{kst_time}</p>
                <img src="http://openweathermap.org/img/wn/{ic}.png" width="40"><br>
                <p style="font-size:1.1em; margin-top:5px; margin-bottom:5px;">{ti:.0f}°</p>
                <p style="font-size:0.8em; color:#888; margin:0;">💧 {p:.0f}%</p>
            </div>
            """,
            unsafe_allow_html=True
        )
st.divider()

# --- 미세먼지: 단순 요약만 표시 (요청대로) ---
st.subheader("대기질 (요약)")
if air and 'list' in air:
    info = air['list'][0]
    aqi = info['main']['aqi']
    txt, em = AQI_TEXT.get(aqi, ("?", ""))
    pm25 = info['components'].get('pm2_5', 0)
    pm10 = info['components'].get('pm10', 0)
    st.write(f"AQI {em} | {txt} — PM2.5: {pm25:.1f} μg/m³, PM10: {pm10:.1f} μg/m³")
else:
    st.write("대기질 정보 없음.")
st.divider()

# --- 주간 요약 (UI 유지) ---
st.subheader("주간 예보")

# 데이터프레임 생성
raw_df = pd.DataFrame([
    {
        'dt': pd.to_datetime(x['dt_txt']).tz_localize('UTC').tz_convert('Asia/Seoul'),
        'temp': x['main']['temp'],
        'feel': x['main']['feels_like'],
        '최저_raw': x['main']['temp_min'],
        '최고_raw': x['main']['temp_max'],
        'icon': x['weather'][0]['icon'],
        '강수': x.get('pop', 0) * 100
    }
    for x in w['list']
])

daily = raw_df.groupby(raw_df['dt'].dt.date).agg(
    최고=('최고_raw', 'max'),
    최저=('최저_raw', 'min'),
    대표=('icon', lambda x: x.mode()[0] if not x.mode().empty else x.iloc[0]),
    강수=('강수', 'mean')
).reset_index()

# UI 출력 (기본 포맷 유지)
for _, r in daily.iterrows():
    ic = fix_icon(r['대표'])
    st.markdown(
        f"""
        <div style="display:flex;align-items:center; gap:20px; padding:8px 0;">
            <div style="width:80px;"><b>{r['index'] if 'index' in r else pd.to_datetime(r['index']) if 'index' in r else r['index'] if 'index' in r else r['index']}</b></div>
            <img src="http://openweathermap.org/img/wn/{ic}.png" width="40">
            <div style="flex:1;">최고 {int(r['최고'])}° / 최저 {int(r['최저'])}°</div>
            <div style="width:80px; text-align:center;">💧 {r['강수']:.0f}%</div>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.write('---')

# --- 온도 그래프 (UI 유지) ---
st.subheader('온도 변화')
fig = go.Figure()
fig.add_trace(go.Scatter(x=raw_df['dt'], y=raw_df['temp'], mode='lines+markers', name='예상온도 (°C)'))
fig.add_trace(go.Scatter(x=raw_df['dt'], y=raw_df['feel'], mode='lines+markers', name='체감온도 (°C)'))
fig.update_layout(xaxis=dict(title='날짜', tickformat='%m-%d'), yaxis_title='온도 (°C)', hovermode='x unified', margin=dict(l=20, r=20, t=30, b=20))
st.plotly_chart(fig, use_container_width=True)

# --- 주간 조언 (유지) ---
st.subheader('주간 조언')
st.info(weekly_summary(daily, air))

# --- 하단: 다른 지역 조회 (UI 유지 - 두 개 버튼 유지) ---
st.subheader('다른 지역 조회')
new_city = st.text_input('지역 입력', city, key='bottom_input')
if st.button('조회 다시', key='bottom_search'):
    if new_city:
        load_weather(new_city)
        st.experimental_rerun()
    else:
        st.warning('도시 이름을 입력해 주세요.')

# --- 지도 (유지) ---
st.subheader('위치 지도')
st.map(pd.DataFrame({'lat': [lat], 'lon': [lon]}), zoom=10)
st.caption(f"지도 중심 위치: 위도 {lat:.2f}, 경도 {lon:.2f}")
