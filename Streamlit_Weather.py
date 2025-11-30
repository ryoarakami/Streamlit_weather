import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go 
import datetime

# OpenWeatherMap API 설정 및 URL
API_KEY = "f2907b0b1e074198de1ba6fb1928665f" 
BASE_URL = "http://api.openweathermap.org/data/2.5/forecast"
GEO_URL = "http://api.openweathermap.org/geo/1.0/direct"
AIR_POLLUTION_URL = "http://api.openweathermap.org/data/2.5/air_pollution"

# --- 날씨 및 상태 정의 ---
WEATHER_TRANSLATION = {
    "clear sky": "맑음", "few clouds": "구름 조금", "scattered clouds": "구름 많음",
    "broken clouds": "구름 낌", "overcast clouds": "흐림", "light rain": "약한 비",
    "moderate rain": "보통 비", "heavy intensity rain": "폭우", "very heavy rain": "강한 폭우",
    "extreme rain": "극심한 비", "freezing rain": "진눈깨비", "light snow": "약한 눈",
    "snow": "눈", "heavy snow": "함박눈", "sleet": "진눈깨비", "shower rain": "소나기",
    "thunderstorm": "천둥 번개", "mist": "안개", "smoke": "연기", "haze": "안개",
    "sand": "모래", "dust": "황사/먼지", "fog": "짙은 안개", "squalls": "돌풍",
    "tornado": "태풍",
}

AQI_STATUS = {
    1: ("좋음", "🟢"), 2: ("보통", "🟡"), 3: ("나쁨", "🟠"),
    4: ("상당히 나쁨", "🔴"), 5: ("매우 나쁨", "⚫"),
}

def contains_hangul(text):
    return any(0xAC00 <= ord(char) <= 0xD7A3 for char in text)

# --------------------------
#   ★★ 수정된 아이콘 통일 함수 ★★
# --------------------------
def normalize_icon_code(code):
    """밤 아이콘을 낮으로 통일하고, 짙은 구름(04d/04n)은 03d 아이콘으로 통일"""
    
    if not code:
        return code

    # 1) 밤 → 낮 통합
    if code.endswith("n"):
        code = code[:-1] + "d"

    # 2) 짙은 구름 → 일반 구름 처리
    if code in ["04d", "04n"]:
        code = "03d"

    return code


# 세션 상태 관리
def initialize_session_state():
    if 'search_performed' not in st.session_state:
        st.session_state.search_performed = False
    if 'city_data' not in st.session_state:
        st.session_state.city_data = None


def fetch_weather_data(city_name):
    """날씨 및 미세먼지 데이터를 가져와 세션 상태에 저장"""
    
    if not API_KEY:
        st.error("OpenWeatherMap API Key가 설정되어 있지 않습니다.")
        return

    search = f"{city_name},KR" if contains_hangul(city_name) else city_name

    # 1) 지역 검색
    geo_response = requests.get(GEO_URL, params={'q': search, 'limit': 1, 'appid': API_KEY}).json()

    if not geo_response:
        st.error(f"'{city_name}' 지역을 찾을 수 없습니다.")
        return
    
    lat = geo_response[0]['lat']
    lon = geo_response[0]['lon']
    display_city_name = geo_response[0].get('local_names', {}).get('ko', city_name)

    # 2) 날씨 데이터
    weather_data = requests.get(BASE_URL, params={'lat': lat, 'lon': lon, 'appid': API_KEY, 'units': 'metric', 'lang': 'en'}).json()

    # 3) 미세먼지 데이터
    pollution_response = requests.get(AIR_POLLUTION_URL, params={'lat': lat, 'lon': lon, 'appid': API_KEY}).json()

    # 저장
    st.session_state.city_data = {
        'display_city_name': display_city_name,
        'weather_data': weather_data,
        'pollution_response': pollution_response
    }

    st.session_state.search_performed = True
    st.rerun()


# ----------------------------
# Streamlit App UI
# ----------------------------

initialize_session_state()

st.title("국내 날씨 및 미세먼지 예보 🌤️💨")
st.markdown("---")

if not st.session_state.search_performed:

    input_city = st.text_input("지명 입력", "서울")

    if st.button("검색"):
        fetch_weather_data(input_city)

else:
    
    data = st.session_state.city_data['weather_data']
    pollution_response = st.session_state.city_data['pollution_response']
    city = st.session_state.city_data['display_city_name']

    st.markdown(f"## {city}")

    current = data['list'][0]
    temp = current['main']['temp']

    # ------------------------------
    # 아이콘 변환 적용된 부분
    # ------------------------------
    icon = normalize_icon_code(current['weather'][0]['icon'])

    st.markdown(f"""
    <div style="display:flex;gap:20px;align-items:center;">
        <h1 style="font-size:5em;">{temp:.0f}°</h1>
        <img src="http://openweathermap.org/img/wn/{icon}@2x.png" style="width:100px;">
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # 미세먼지 표시
    st.markdown("### 💨 현재 대기질")

    if pollution_response:
        aqi = pollution_response['list'][0]['main']['aqi']
        status, emoji = AQI_STATUS.get(aqi, ("알 수 없음", "❓"))
        st.write(f"**{emoji}  {status}**")

    st.markdown("---")
