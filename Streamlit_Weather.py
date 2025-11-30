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


#-----------------

weather_kr = {
    "clear sky": "맑음", "few clouds": "조금 구름",
    "scattered clouds": "구름 많음", "broken clouds": "흐림",
    "overcast clouds": "흐림", "light rain": "약한 비",
    "moderate rain": "비", "heavy intensity rain": "강한 비",
    "light snow": "약한 눈", "snow": "눈",
    "mist": "안개", "fog": "짙은 안개", "thunderstorm": "천둥"
}

aqi_now = {
    1: ("좋음", "🟢"), 2: ("보통", "🟡"), 3: ("나쁨", "🟠"),
    4: ("매우 나쁨", "🔴"), 5: ("최악", "⚫")
}

weeks = {
    "Mon": "월", "Tue": "화", "Wed": "수", "Thu": "목", 
    "Fri": "금", "Sat": "토", "Sun": "일"
}


#-----------------


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


#-----------------


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
        msg.append(f"일교차가 {d:.1f}°C 폭으로 큽니다. 아침/저녁 기온 변화에 주의하세요.")

    rain_days = (df["강수"] >= 50).sum()
    if rain_days >= len(df) / 2:
        msg.append("비 소식이 많은 주간입니다. 우산을 챙겨가세요.")

    if air and "list" in air:
        aqi = air["list"][0]["main"]["aqi"]
        if aqi >= 3:
            txt, _ = aqi_now.get(aqi)
            msg.append(f"미세먼지 농도가 {txt} 수준입니다. 마스크 착용을 권장합니다.")

    return "\n\n".join(msg)


#-----------------검색


init_state()

st.title("오늘의 날씨는")
st.divider()

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


#-----------------


df = pd.DataFrame(w["list"])
df["dt"] = pd.to_datetime(df["dt_txt"])
df["temp"] = df["main"].apply(lambda x: x["temp"])
df["feel"] = df["main"].apply(lambda x: x["feels_like"])
df["low_temp"] = df["main"].apply(lambda x: x["temp_min"])
df["high_temp"] = df["main"].apply(lambda x: x["temp_max"])
df["icon"] = df["weather"].apply(lambda x: x[0]["icon"])
df["rainy"] = df["pop"] * 100
df = df[["dt", "temp", "feel", "low_temp", "high_temp", "icon", "rainy"]]


daily = df.groupby(df["dt"].dt.date).agg(
    날짜=("dt", "first"),
    최고=("high_temp", "max"),
    최저=("low_temp", "min"),
    대표=("icon", lambda x: x.mode()[0]),
    강수=("rainy", "mean")
).reset_index(drop=True)

# 날짜 컬럼을 datetime 타입으로 맞추기
daily["날짜"] = pd.to_datetime(daily["날짜"])

now = w["list"][0]
t = now["main"]["temp"]
fl = now["main"]["feels_like"]
desc = weather_kr.get(now["weather"][0]["description"], "")
icon = fix_icon(now["weather"][0]["icon"])

today_max = daily.loc[0, "최고"]
today_min = daily.loc[0, "최저"]

current_dt = pd.to_datetime(now["dt_txt"])
day_name_en = current_dt.strftime("%a")
day_name = weeks.get(day_name_en, day_name_en) 
current_date_time = current_dt.strftime(f"%m/%d({day_name}), %H시")


#----------------- 현재 날씨


col1, col2 = st.columns([1,2])
with col1:
    st.image(f"http://openweathermap.org/img/wn/{icon}@2x.png", width=100)
    st.write(f"**{desc}**")
with col2:
    st.markdown(f"### **{int(t)}°**")
    col3, col4 = st.columns([1, 1])
    with col3:
        st.markdown(f"**↑ {int(today_max)}°** / **↓ {int(today_min)}°**")
    st.write(f"**체감온도 {int(fl)}°**")
    st.write(f"**{current_date_time}**")



st.divider() #-----------------오늘 시간별 날씨


tlist = w["list"][:8]
cols = st.columns(len(tlist))

for i, item in enumerate(tlist):
    with cols[i]:
        with st.container():
            tt = pd.to_datetime(item["dt_txt"]).strftime("%H시")
            ti = item["main"]["temp"]
            p = item["pop"] * 100
            ic = fix_icon(item["weather"][0]["icon"])
            st.caption(f"{tt}")
            st.image(f"http://openweathermap.org/img/wn/{ic}.png", width=40)
            st.markdown(f"**{int(ti)}°**")
            st.caption(f"💧 {int(p)}%")


st.divider() #-----------------미세먼지


st.subheader("미세먼지 농도")
info = air["list"][0]
aqi = info["main"]["aqi"]
txt, em = aqi_now.get(aqi, ("?", ""))
pm25 = info["components"].get("pm2_5", 0)
pm10 = info["components"].get("pm10", 0)
st.write(f"AQI {em} | {txt}")
st.write(f"PM2.5: {pm25:.1f}, PM10: {pm10:.1f}")


st.divider() #-----------------이번주 날씨


header_cols = st.columns([1, 1, 1, 1, 1])
with header_cols[0]: st.markdown("##### **날짜**")
with header_cols[1]: st.markdown("##### **강수량**")
with header_cols[2]: st.markdown("##### **날씨**")
with header_cols[3]: st.markdown("##### **최고온도**")
with header_cols[4]: st.markdown("##### **최저온도**")

daily["요일"] = daily["날짜"].dt.strftime("%a").map(weeks)
daily.loc[0, "요일"] = "오늘"

for _, row in daily.iterrows():
    c1, c2, c3, c4, c5 = st.columns([1,1,1,1,1])
    with c1: st.write(row["요일"])
    with c2: st.write(f"💧 {int(row['강수'])}%")
    with c3: st.image(f"http://openweathermap.org/img/wn/{fix_icon(row['대표'])}.png", width=40)
    with c4: st.write(f"**{int(row['최고'])}°**")
    with c5: st.write(f"{int(row['최저'])}°")


st.divider() #-----------------날짜 업데이트


unique_dates = sorted(df["dt"].dt.date.unique())
daily_tick_points = [
    datetime.datetime.combine(d, datetime.time(12))
    for d in unique_dates
]

daily_labels_kr = []
for i, d in enumerate(unique_dates):
    wd_en = d.strftime("%a")
    wd_kr = weeks.get(wd_en, wd_en)
    if i == 0:
        wd_kr = "오늘"
    daily_labels_kr.append(wd_kr)


#-----------------


st.subheader("이번주 온도")
fig = go.Figure()
fig.add_trace(go.Scatter(x=df["dt"], y=df["temp"], mode="lines+markers", name="온도"))
fig.add_trace(go.Scatter(x=df["dt"], y=df["feel"], mode="lines+markers", name="체감온도"))

fig.update_layout(
    xaxis={
        'type': 'date', 
        'tickmode': 'array',
        'tickvals': daily_tick_points,
        'ticktext': daily_labels_kr, 
        'tickangle': 0
    },
)
st.plotly_chart(fig, use_container_width=True)

st.info(weekly_summary(daily, air))


st.divider() #-----------------


st.subheader("다른 지역 조회")
new_city = st.text_input("지역 입력", city)
if st.button("조회"):
    load_weather(new_city)
st.map(pd.DataFrame({"lat": [lat], "lon": [lon]}))















