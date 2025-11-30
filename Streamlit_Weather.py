import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import datetime

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

def has_kr(s):
    return any(0xAC00 <= ord(c) <= 0xD7A3 for c in s)


def fix_icon(code):
    if not code:
        return code
    if code.endswith("n"):
        code = code[:-1] + "d"
    if code == "04d":
        return "03d"
    return code


def init_state():
    ss = st.session_state
    ss.setdefault("searched", False)
    ss.setdefault("data", None)


def load_weather(city):
    ss = st.session_state
    q = f"{city},KR" if has_kr(city) else city

    geo = requests.get(GEO_URL, params={"q": q, "limit": 1, "appid": API_KEY}).json()
    if not geo:
        st.error("지역을 찾을 수 없습니다.")
        ss.searched = False
        return

    lat, lon = geo[0]["lat"], geo[0]["lon"]
    name_kr = geo[0].get("local_names", {}).get("ko", city)

    w = requests.get(BASE_URL, params={
        "lat": lat, "lon": lon, "appid": API_KEY,
        "units": "metric", "lang": "en"
    }).json()

    air = requests.get(AIR_URL, params={
        "lat": lat, "lon": lon, "appid": API_KEY
    }).json()

    ss.data = {"name": name_kr, "lat": lat, "lon": lon, "w": w, "air": air}
    ss.searched = True
    st.rerun()


def weekly_summary(df, air):
    avg_max = df["최고"].mean()
    msg = []

    if avg_max >= 27:
        msg.append("이번 주는 더운 편입니다. 시원한 복장을 추천합니다.")
    elif avg_max >= 16:
        msg.append("날씨가 활동하기 좋습니다.")
    elif avg_max >= 5:
        msg.append("날씨가 쌀쌀한 편입니다. 가벼운 외투를 챙기세요.")
    else:
        msg.append("추운 날씨가 예상됩니다. 따뜻하게 입으세요.")

    df["일교차"] = df["최고"] - df["최저"]
    d = df["일교차"].mean()
    if d >= 10:
        msg.append(f"평균 일교차가 {d:.1f}°C로 큽니다.")

    rain_days = (df["강수"] >= 50).sum()
    if rain_days >= len(df) / 2:
        msg.append("비 소식이 많은 주간입니다. 우산을 챙기세요.")

    if air and "list" in air:
        aqi = air["list"][0]["main"]["aqi"]
        if aqi >= 3:
            txt, _ = AQI_TEXT.get(aqi, ("알 수 없음", ""))
            msg.append(f"대기 질이 '{txt}' 수준입니다. 마스크 착용을 추천합니다.")

    return "\n\n".join(msg)


# -------------------------------------------------------

init_state()

st.title("국내 날씨 / 미세먼지")

if not st.session_state.searched:
    city_in = st.text_input("지역 입력", "서울")
    if st.button("조회"):
        load_weather(city_in)
    st.stop()

data = st.session_state.data
w = data["w"]
air = data["air"]
city = data["name"]
lat, lon = data["lat"], data["lon"]

st.header(city)

now = w["list"][0]
t = now["main"]["temp"]
fl = now["main"]["feels_like"]
desc = W_DESC.get(now["weather"][0]["description"], "")
icon = fix_icon(now["weather"][0]["icon"])

tlist = w["list"][:8]
tmin = min(x["main"]["temp_min"] for x in tlist)
tmax = max(x["main"]["temp_max"] for x in tlist)

st.markdown(
    f"""
    <div style="display:flex;align-items:center;gap:10px;">
        <h1 style="margin:0">{int(t)}°</h1>
        <img src="http://openweathermap.org/img/wn/{icon}@2x.png" width="70">
    </div>
    """,
    unsafe_allow_html=True
)

st.write(desc)
st.write(f"최고 {tmax:.0f}° / 최저 {tmin:.0f}°")
st.write(f"체감온도 {fl:.0f}°")
st.divider()

# 3. 시간별 예보
st.markdown("### ⏰ 시간별 예보")
forecast_list_24hr = data['list'][:8]

# 카드 그룹 전체 컨테이너
st.markdown(
    """
    <div style="display: flex; justify-content: space-between; gap: 12px; padding: 10px 0;">
    """,
    unsafe_allow_html=True
)

for item in forecast_list_24hr:
    time_str = (
        pd.to_datetime(item['dt_txt'])
        .tz_localize('UTC')
        .tz_convert('Asia/Seoul')
        .strftime('%H시')
    )
    temp = item['main']['temp']
    weather_icon_code = normalize_icon_code(item['weather'][0]['icon'])
    pop = item['pop'] * 100

    # 카드 1개
    st.markdown(
        f"""
        <div style="
            flex: 1;
            background: #fafafa;
            border: 1px solid #ddd;
            border-radius: 10px;
            padding: 10px 0;
            text-align: center;
            color: #000;
            box-shadow: 0 1px 2px rgba(0,0,0,0.08);
        ">
            <div style="font-weight: bold; font-size: 1.1em; margin-bottom: 6px;">
                {time_str}
            </div>

            <img src="http://openweathermap.org/img/wn/{weather_icon_code}.png"
                 style="width: 45px; height: 45px; margin: 4px 0;" />

            <div style="font-size: 1.1em; font-weight: bold; margin: 3px 0;">
                {temp:.0f}°
            </div>

            <div style="font-size: 0.85em; color: #555;">
                💧 {pop:.0f}%
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# 컨테이너 종료
st.markdown("</div>", unsafe_allow_html=True)
st.markdown("---")


# 미세먼지
st.subheader("대기질")
if air and "list" in air:
    info = air["list"][0]
    aqi = info["main"]["aqi"]
    txt, em = AQI_TEXT.get(aqi, ("?", ""))
    pm25 = info["components"].get("pm2_5", 0)
    pm10 = info["components"].get("pm10", 0)

    st.write(f"AQI {em} | {txt}")
    st.write(f"PM2.5: {pm25:.1f},  PM10: {pm10:.1f}")
else:
    st.write("대기질 정보 없음.")
st.divider()

# 주간 요약
st.subheader("주간 예보")

df = pd.DataFrame([
    {
        "dt": pd.to_datetime(x["dt_txt"]),
        "temp": x["main"]["temp"],
        "feel": x["main"]["feels_like"],
        "최저_raw": x["main"]["temp_min"],
        "최고_raw": x["main"]["temp_max"],
        "icon": x["weather"][0]["icon"],
        "강수": x["pop"] * 100
    }
    for x in w["list"]
])

daily = df.groupby(df["dt"].dt.date).agg(
    최고=("최고_raw", "max"),
    최저=("최저_raw", "min"),
    대표=("icon", lambda x: x.mode()[0]),
    강수=("강수", "mean")
).reset_index()

for _, r in daily.iterrows():
    ic = fix_icon(r["대표"])
    st.markdown(
        f"""
        <div style="display:flex;align-items:center; gap:20px;">
            <div><b>{r['dt'].strftime("%m-%d")}</b></div>
            <img src="http://openweathermap.org/img/wn/{ic}.png" width="40">
            <div>최고 {int(r['최고'])}° / 최저 {int(r['최저'])}°</div>
            <div>💧 {r['강수']:.0f}%</div>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.write("---")

# 그래프
st.subheader("온도 변화")
fig = go.Figure()
fig.add_trace(go.Scatter(x=df["dt"], y=df["temp"], mode="lines+markers", name="온도"))
fig.add_trace(go.Scatter(x=df["dt"], y=df["feel"], mode="lines+markers", name="체감온도"))
st.plotly_chart(fig, use_container_width=True)

st.subheader("주간 조언")
st.info(weekly_summary(daily, air))

st.subheader("다른 지역 조회")
new_city = st.text_input("지역 입력", city)
if st.button("조회 다시"):
    load_weather(new_city)

st.subheader("위치 지도")
st.map(pd.DataFrame({"lat": [lat], "lon": [lon]}))

