import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import base64
import datetime

API_KEY = "f2907b0b1e074198de1ba6fb1928665f" 
BASE_URL = "http://api.openweathermap.org/data/2.5/forecast"
GEO_URL = "http://api.openweathermap.org/geo/1.0/direct"
AIR_POLLUTION_URL = "http://api.openweathermap.org/data/2.5/air_pollution"

# ... (WEATHER_TRANSLATION, AQI_STATUS, WEATHER_ICONS, contains_hangul 함수는 동일)

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

WEATHER_ICONS = {
    "01d": "☀️", "01n": "🌙", "02d": "🌤️", "02n": "☁️",
    "03d": "☁️", "03n": "☁️", "04d": "☁️", "04n": "☁️",
    "09d": "🌧️", "09n": "🌧️", "10d": "🌦️", "10n": "🌧️",
    "11d": "⛈️", "11n": "⛈️", "13d": "🌨️", "13n": "🌨️",
    "50d": "🌫️", "50n": "🌫️",
}

def contains_hangul(text):
    for char in text:
        if 0xAC00 <= ord(char) <= 0xD7A3:
            return True
    return False

def get_base64_image(image_file):
    with open(image_file, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()

def set_background(image_file='assets/background.jpg'):
    if image_file:
        try:
            bin_str = get_base64_image(image_file)
            st.markdown(
                f"""
                <style>
                .stApp {{
                    background-image: url("data:image/png;base64,{bin_str}");
                    background-size: cover;
                    background-attachment: fixed;
                }}
                </style>
                """,
                unsafe_allow_html=True
            )
        except FileNotFoundError:
            st.warning(f"경로에 '{image_file}' 파일을 찾을 수 없습니다. 기본 배경이 사용됩니다.")
            st.markdown(
                f"""
                <style>
                .stApp {{
                    background-color: #ADD8E6;
                }}
                </style>
                """,
                unsafe_allow_html=True
            )
    else:
         st.markdown(
            f"""
            <style>
            .stApp {{
                background-color: #ADD8E6;
            }}
            </style>
            """,
            unsafe_allow_html=True
        )

# --- 세션 상태 초기화 및 검색 함수 ---

# 검색 상태를 관리하는 함수
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

    search = city_name
    if contains_hangul(city_name):
        search = f"{city_name},KR"
    
    # 1. 지리 정보 가져오기
    geo_params = {'q': search, 'limit': 1, 'appid': API_KEY}
    geo_response = requests.get(GEO_URL, params=geo_params).json()
    
    if not geo_response:
        st.session_state.search_performed = False
        st.error(f"'{city_name}'에 대한 지리 정보를 찾을 수 없습니다. 도시 이름을 확인해 주세요.")
        return
    
    lat = geo_response[0]['lat']
    lon = geo_response[0]['lon']
    display_city_name = geo_response[0].get('local_names', {}).get('ko', city_name)
    
    # 2. 날씨 예보 정보 가져오기
    weather_params = {'lat': lat, 'lon': lon, 'appid': API_KEY, 'units': 'metric', 'lang': 'en'}
    response = requests.get(BASE_URL, params=weather_params)
    weather_data = response.json()

    # 3. 미세먼지 정보 가져오기
    pollution_params = {'lat': lat, 'lon': lon, 'appid': API_KEY}
    pollution_response = requests.get(AIR_POLLUTION_URL, params=pollution_params).json()

    # 데이터 저장
    st.session_state.city_data = {
        'display_city_name': display_city_name,
        'weather_data': weather_data,
        'pollution_response': pollution_response
    }
    st.session_state.search_performed = True
    st.experimental_rerun() # 데이터 로드 후 화면 갱신

# --- Streamlit 앱 시작 ---

initialize_session_state()
set_background()

st.title("국내 날씨 및 미세먼지 예보 🌤️💨")
st.markdown("---")


# 1. 초기/상단 검색 UI (검색 전이나 에러 시에만 표시)
if not st.session_state.search_performed:
    city_name_input = st.text_input("지명 입력", "서울", key="initial_city_input")
    if st.button("날씨 및 미세먼지 정보 가져오기 (검색)"):
        if city_name_input:
            fetch_weather_data(city_name_input)
        else:
            st.warning("도시 이름을 입력해 주세요.")
else:
    # 2. 검색 후 메인 UI 표시
    
    data = st.session_state.city_data['weather_data']
    pollution_response = st.session_state.city_data['pollution_response']
    display_city_name = st.session_state.city_data['display_city_name']

    # --- UI 구성 시작 ---
    
    # 1. 상단 현재 날씨 정보
    st.markdown(f"## {display_city_name}")
    
    current_weather = data['list'][0]
    current_temp = current_weather['main']['temp']
    
    # 예보 목록에서 24시간 내 최고/최저 기온 계산
    forecast_list_24hr = data['list'][:8] 
    min_temp = min(item['main']['temp_min'] for item in forecast_list_24hr)
    max_temp = max(item['main']['temp_max'] for item in forecast_list_24hr)
    
    feels_like = current_weather['main']['feels_like']
    current_desc_en = current_weather['weather'][0]['description']
    current_desc_kr = WEATHER_TRANSLATION.get(current_desc_en, current_desc_en)
    weather_icon_code = current_weather['weather'][0]['icon']
    
    # 현재 시각을 한국 시간대에 맞춰 포맷 (OpenWeatherMap은 UTC를 기준으로 dt_txt를 제공)
    current_dt_utc = pd.to_datetime(current_weather['dt_txt']).tz_localize('UTC')
    # 한국 시간대 (KST)로 변환 (+9시간)
    current_time_kst = current_dt_utc.tz_convert('Asia/Seoul').strftime('%m월 %d일, 오후 %I:%M')

    # 큰 숫자 온도와 아이콘
    st.markdown(f"""
    <div style="display: flex; align-items: center; justify-content: flex-start; gap: 20px;">
        <h1 style="font-size: 5em; margin: 0;">{current_temp:.0f}°</h1>
        <img src="http://openweathermap.org/img/wn/{weather_icon_code}@2x.png" alt="날씨 아이콘" style="width: 100px; height: 100px;"/>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"**{current_desc_kr}**")
    st.markdown(f"⬆️{max_temp:.0f}° / ⬇️{min_temp:.0f}°")
    st.markdown(f"체감온도 {feels_like:.0f}°")
    st.markdown(f"{current_time_kst}")
    
    st.markdown("---")
    
    # 2. 미세먼지 정보 (단위 오류 수정됨: &micro;g/m&sup3; 사용)
    st.markdown("### 💨 현재 대기 질 정보")
    if pollution_response and 'list' in pollution_response:
        current_air = pollution_response['list'][0]
        aqi = current_air['main']['aqi']
        aqi_status_kr, aqi_emoji = AQI_STATUS.get(aqi, ("알 수 없음", "❓"))
        components = current_air['components']

        st.markdown(f"""
        <div style="display: flex; align-items: center; justify-content: space-between; background-color: rgba(255,255,255,0.1); padding: 10px; border-radius: 10px;">
            <div style="text-align: center;">
                <p style="margin:0; font-size: 1.2em;">AQI {aqi_emoji}</p>
                <p style="margin:0; font-weight: bold;">{aqi_status_kr}</p>
            </div>
            <div style="text-align: center;">
                <p style="margin:0; font-size: 0.9em;">PM2.5</p>
                <p style="margin:0; font-weight: bold;">{components.get('pm2_5', 'N/A'):.1f} &micro;g/m&sup3;</p> 
            </div>
            <div style="text-align: center;">
                <p style="margin:0; font-size: 0.9em;">PM10</p>
                <p style="margin:0; font-weight: bold;">{components.get('pm10', 'N/A'):.1f} &micro;g/m&sup3;</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.warning("미세먼지 정보를 가져오는 데 실패했습니다.")
    
    st.markdown("---")

    # 3. 시간별 예보
    st.markdown("### ⏰ 시간별 예보")
    forecast_list_24hr = data['list'][:8]
    cols = st.columns(len(forecast_list_24hr))
    
    for i, item in enumerate(forecast_list_24hr):
        with cols[i]:
            time_str = pd.to_datetime(item['dt_txt']).tz_localize('UTC').tz_convert('Asia/Seoul').strftime('%H시')
            temp = item['main']['temp']
            weather_icon_code = item['weather'][0]['icon']
            pop = item['pop'] * 100
            
            st.markdown(f"""
            <div style="text-align: center; padding: 5px; border-radius: 5px; background-color: rgba(255,255,255,0.05);">
                <p style="font-weight: bold; margin-bottom: 5px;">{time_str}</p>
                <img src="http://openweathermap.org/img/wn/{weather_icon_code}.png" alt="날씨 아이콘" style="width: 40px; height: 40px;"/>
                <p style="font-size: 1.1em; margin-top: 5px; margin-bottom: 5px;">{temp:.0f}°</p>
                <p style="font-size: 0.8em; color: #888; margin: 0;">💧 {pop:.0f}%</p>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")
    
    # 4. 일별 요약 (주간 예보)
    st.markdown("### 📅 주간 날씨 예보")
    
    df_full = pd.DataFrame(
        [{
            '날짜/시간': pd.to_datetime(item['dt_txt']),
            '요일': pd.to_datetime(item['dt_txt']).tz_localize('UTC').tz_convert('Asia/Seoul').strftime('%a'),
            '최저온도_raw': item['main']['temp_min'],
            '최고온도_raw': item['main']['temp_max'],
            '날씨_아이콘': item['weather'][0]['icon'],
            '강수확률': item['pop'] * 100
        } for item in data['list']]
    )
    
    daily_summary = df_full.groupby(df_full['날짜/시간'].dt.date).agg(
        요일=('요일', 'first'),
        최고온도=('최고온도_raw', np.max),
        최저온도=('최저온도_raw', np.min),
        대표날씨_아이콘=('날씨_아이콘', lambda x: x.mode()[0]),
        평균강수확률=('강수확률', np.mean)
    ).reset_index()
    
    today = datetime.datetime.now().date()
    daily_summary['요일'] = daily_summary['날짜/시간'].apply(lambda x: 
                                    '오늘' if x == today else 
                                    '내일' if x == today + datetime.timedelta(days=1) else 
                                    x.strftime('%a'))

    for index, row in daily_summary.iterrows():
        day_label = row['요일']
        max_t = row['최고온도']
        min_t = row['최저온도']
        weather_icon_code = row['대표날씨_아이콘']
        avg_pop = row['평균강수확률']
        
        st.markdown(f"""
        <div style="display: flex; align-items: center; justify-content: space-between; padding: 8px 0;">
            <div style="width: 15%; font-weight: bold;">{day_label}</div>
            <div style="width: 15%; text-align: left; font-size: 0.9em; color: #888;">💧 {avg_pop:.0f}%</div>
            <div style="width: 20%; text-align: center;">
                <img src="http://openweathermap.org/img/wn/{weather_icon_code}.png" alt="날씨 아이콘" style="width: 40px; height: 40px;"/>
            </div>
            <div style="width: 25%; text-align: right; font-weight: bold;">{max_t:.0f}°</div>
            <div style="width: 25%; text-align: right; color: #888;">{min_t:.0f}°</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("---")

    # 3. 화면 최하단에 새로운 검색바 배치 (이 부분이 핵심)
    st.markdown("---")
    st.markdown("### 📍 다른 지역 검색")
    
    new_city_name_input = st.text_input("새로운 지명 입력", display_city_name, key="new_city_input")
    if st.button("날씨 정보 다시 가져오기"):
        if new_city_name_input:
            fetch_weather_data(new_city_name_input)
        else:
            st.warning("도시 이름을 입력해 주세요.")
