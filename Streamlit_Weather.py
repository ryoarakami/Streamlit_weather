import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import datetime

API_KEY = st.secrets["api_keys"]["openweathermap"]

BASE_URL = "http://api.openweathermap.org/data/2.5/forecast"
GEO_URL = "http://api.openweathermap.org/geo/1.0/direct"
AIR_URL = "http://api.openweathermap.org/data/2.5/air_pollution"


#-----------------
# 기본 매핑 테이블
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
# 유틸 함수
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


#-----------------
# 개선된 load_weather (자연스럽고 간결한 버전)
#-----------------

def load_weather(city):
    ss = st.session_state

    # 한국어 지역명 → 자동 KR
    query = f"{city},KR" if has_kr(city) else city

    # 위치 찾기
    geo = requests.get(
        GEO_URL,
        params={"q": query, "limit": 1, "appid": API_KEY}
    ).json()

    if not geo:
        st.error("지역을 찾을 수 없습니다.")
        ss.searched = False
        return

    lat = geo[0]["lat"]
    lon = geo[0]["lon"]
    name_kr = geo[0].get("local_names", {}).get("ko", city)

    # 날씨
    weather = requests.get(
        BASE_URL,
        params={"lat": lat, "lon": lon, "appid": API_KEY, "units": "metric", "lang": "en"}
    ).json()

    # 대기질
    air_quality = requests.get(
        AIR_URL,
        params={"lat": lat, "lon": lon, "appid": API_KEY}
    ).json()

    # 세션 저장
    ss.data = {
        "name": name_kr,
        "lat": lat,
        "lon": lon,
        "weather": weather,
        "air": air_quality
    }
    ss.searched = True
    st.rerun()


#-----------------
# 주간 요약 생성
#-----------------

def weekly_summary(df, air_quality):
    avg_max = df["최고"].mean()
    msg = []

    if avg_max >= 27:
        msg.append("이번 주는 무더위가 예상돼요. 온열질환을 주의해주세요.")
    elif avg_max >= 16:
        msg.append("이번 주는 활동하기 좋은 날씨에요.")
    elif avg_max >= 5:
        msg.append("이번 주는 쌀쌀한 편입니다. 가벼운 외투를 챙겨가주세요.")
    else:
        msg.append("이번 주는 추운 날씨가 예상됩니다. 두꺼운 옷이 좋을거 같아요.")

    df["일교차"] = df["최고"] - df["최저"]
    avg_gap = df["일교차"].mean()
    if avg_gap >= 10:
        msg.append(f"일교차가 {avg_gap:.1f}°C 폭으로 큽니다. 아침/저녁 기온 변화에 주의해주세요.")

    rainy_days = (df["강수"] >= 50).sum()
    if rainy_days >= len(df) / 2:
        msg.append("비 소식이 많은 주간입니다. 우산을 챙겨가주세요.")

    if air_quality and "list" in air_quality:
        aqi = air_quality["list"][0]["main"]["aqi"]
        if aqi >= 3:
            txt, _ = aqi_now.get(aqi)
            msg.append(f"미세먼지 농도가 {txt} 수준입니다. 마스크 착용을 권장드립니다.")

    return "\n\n".join(msg)


#-----------------
# 초기 UI
#-----------------

init_state()

st.title("오늘의 날씨는")
st.divider()

if not st.session_state.searched:
    city_input = st.text_input("지역 입력", "서울")
    if st.button("조회"):
        load_weather(city_input)
    st.stop()

data = st.session_state.data
weather = data["weather"]
air_quality = data["air"]
city = data["name"]
lat, lon = data["lat"], data["lon"]

st.header(city)


#-----------------
# 데이터 정리
#-----------------

forecast_df = pd.DataFrame(weather["list"])

forecast_df["dt"] = pd.to_datetime(forecast_df["dt_txt"])
forecast_df["temp"] = forecast_df["main"].apply(lambda x: x["temp"])
forecast_df["feel"] = forecast_df["main"].apply(lambda x: x["feels_like"])
forecast_df["low_temp"] = forecast_df["main"].apply(lambda x: x["temp_min"])
forecast_df["high_temp"] = forecast_df["main"].apply(lambda x: x["temp_max"])
forecast_df["icon"] = forecast_df["weather"].apply(lambda x: x[0]["icon"])
forecast_df["rainy"] = forecast_df["pop"] * 100

forecast_df = forecast_df[["dt", "temp", "feel", "low_temp", "high_temp", "icon", "rainy"]]


#-----------------
# 일별 집계
#-----------------

daily_df = forecast_df.groupby(forecast_df["dt"].dt.date).agg(
    날짜=("dt", "first"),
    최고=("high_temp", "max"),
    최저=("low_temp", "min"),
    아이콘=("icon", lambda x: x.mode()[0]),
    강수=("rainy", "mean")
).reset_index(drop=True)

daily_df["날짜"] = pd.to_datetime(daily_df["날짜"])

daily_df["요일"] = daily_df["날짜"].dt.strftime("%a").map(weeks)
daily_df.loc[0, "요일"] = "오늘"


#-----------------
# 현재 날씨
#-----------------

current = weather["list"][0]
temp_now = current["main"]["temp"]
feel_now = current["main"]["feels_like"]
desc_now = weather_kr.get(current["weather"][0]["description"], "")
icon_now = fix_icon(current["weather"][0]["icon"])

today_max = daily_df.loc[0, "최고"]
today_min = daily_df.loc[0, "최저"]

current_dt = pd.to_datetime(current["dt_txt"])
weekday = weeks.get(current_dt.strftime("%a"))
time_label = current_dt.strftime(f"%m/%d({weekday}), %H시")

col1, col2 = st.columns([1,2])
with col1:
    st.image(f"http://openweathermap.org/img/wn/{icon_now}@2x.png", width=100)
    st.write(f"**{desc_now}**")
with col2:
    st.markdown(f"### **{int(temp_now)}°**")
    st.write(f"**↑ {int(today_max)}° / ↓ {int(today_min)}°**")
    st.write(f"**체감온도 {int(feel_now)}°**")
    st.write(f"**{time_label}**")


st.divider()


#-----------------
# 시간별 예보
#-----------------

tlist = weather["list"][:8]
cols = st.columns(len(tlist))

for i, item in enumerate(tlist):
    with cols[i]:
        tt = pd.to_datetime(item["dt_txt"]).strftime("%H시")
        ti = item["main"]["temp"]
        p = item["pop"] * 100
        ic = fix_icon(item["weather"][0]["icon"])

        st.caption(tt)
        st.image(f"http://openweathermap.org/img/wn/{ic}.png", width=40)
        st.markdown(f"**{int(ti)}°**")
        st.caption(f"💧 {int(p)}%")


st.divider()


#-----------------
# 미세먼지
#-----------------

st.subheader("미세먼지 농도")
info = air_quality["list"][0]
aqi = info["main"]["aqi"]
txt, emoji = aqi_now.get(aqi, ("?", ""))

st.write(f"AQI {emoji} | {txt}")
st.write(f"PM2.5: {info['components'].get('pm2_5', 0):.1f}, "
         f"PM10: {info['components'].get('pm10', 0):.1f}")


st.divider()


#-----------------
# 주간 표 렌더러
#-----------------

def render_daily_row(row):
    cols = st.columns([1, 1, 1, 1, 1])
    cols[0].write(row["요일"])
    cols[1].write(f"{int(row['강수'])}%")
    cols[2].image(f"http://openweathermap.org/img/wn/{fix_icon(row['아이콘'])}.png", width=35)
    cols[3].write(f"**{int(row['최고'])}°**")
    cols[4].write(f"{int(row['최저'])}°")


header_cols = st.columns([1, 1, 1, 1, 1])
header_cols[0].markdown("##### **요일**")
header_cols[1].markdown("##### **강수량**")
header_cols[2].markdown("##### **날씨**")
header_cols[3].markdown("##### **최고온도**")
header_cols[4].markdown("##### **최저온도**")

for _, row in daily_df.iterrows():
    render_daily_row(row)


st.divider()


#-----------------
# 날짜 축 라벨
#-----------------

unique_dates = sorted(forecast_df["dt"].dt.date.unique())
tick_points = [datetime.datetime.combine(d, datetime.time(12)) for d in unique_dates]

tick_labels = []
for i, d in enumerate(unique_dates):
    wd = d.strftime("%a")
    label = weeks.get(wd, wd)
    if i == 0:
        label = "오늘"
    tick_labels.append(label)


#-----------------
# 온도 변화 그래프
#-----------------

st.subheader("이번주 온도 변화")
fig = go.Figure()
fig.add_trace(go.Scatter(x=forecast_df["dt"], y=forecast_df["temp"], mode="lines+markers", name="온도"))
fig.add_trace(go.Scatter(x=forecast_df["dt"], y=forecast_df["feel"], mode="lines+markers", name="체감온도"))

fig.update_layout(
    xaxis={'type': 'date', 'tickmode': 'array', 'tickvals': tick_points, 'ticktext': tick_labels},
    margin=dict(t=30)
)

st.plotly_chart(fig, use_container_width=True)

st.info(weekly_summary(daily_df, air_quality))


st.divider()


#-----------------
# 다른 지역 조회
#-----------------

st.subheader("다른 지역 조회")
new_city = st.text_input("지역 입력", city)
if st.button("조회"):
    load_weather(new_city)

st.map(pd.DataFrame({"lat": [lat], "lon": [lon]}))
