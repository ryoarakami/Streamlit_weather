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
#    ★★ 수정된 아이콘 통일 함수 ★★
# --------------------------
def normalize_icon_code(code):
    """밤 아이콘을 낮으로 통일하고, 짙은 구름(04d/04n)은 03d 아이콘으로 통일"""
    
    if not code:
        return code

    # 1) 밤 → 낮 통합
    if code.endswith("n"):
        code = code[:-1] + "d"

    # 2) 짙은 구름 → 일반 구름 처리
    if code == "04d": # 이미 위에 "n"이 처리되었으므로 "04n"은 "04d"로 변경된 상태
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
        st.session_state.search_performed = False
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
        'lat': lat, # 지도용 데이터 추가
        'lon': lon, # 지도용 데이터 추가
        'weather_data': weather_data,
        'pollution_response': pollution_response
    }

    st.session_state.search_performed = True
    st.rerun()


# --- 주간 날씨 분석 함수 (이전 코드에서 가져와서 포함) ---
def get_weekly_summary_text(daily_summary, pollution_response):
    
    # 1. 온도 분석 (주간 최고 온도 평균 기준)
    avg_max_temp = daily_summary['최고온도'].mean()
    temp_advice = ""
    
    if avg_max_temp >= 27:
        temp_advice = "이번 주는 **날이 더워요**. 반팔이나 시원한 옷을 입어주세요. 🥵"
    elif 16 <= avg_max_temp < 27:
        temp_advice = "이번 주는 **활동하기 좋은 날씨**예요. 가벼운 겉옷은 선택사항입니다. 😊"
    elif 5 <= avg_max_temp < 16:
        temp_advice = "이번 주는 **날이 쌀쌀해요**. 긴팔이나 외투를 챙기는 것이 좋을 거예요. 🧥"
    else: # avg_max_temp < 5
        temp_advice = "이번 주는 **날이 추워요**. 따뜻하고 두꺼운 외투와 방한용품을 챙겨주세요. 🥶"

    # 2. 일교차 분석 (평균 일교차 기준)
    daily_summary['일교차'] = daily_summary['최고온도'] - daily_summary['최저온도']
    avg_temp_diff = daily_summary['일교차'].mean()
    diff_advice = ""
    
    if avg_temp_diff >= 10:
        diff_advice = f"🌡️ **일교차가 평균 {avg_temp_diff:.1f}°C**로 매우 커요. 얇은 옷을 여러 겹 껴입어 체온 조절에 신경 써주세요."

    # 3. 강수 분석 (강수확률 50% 이상인 날이 과반 기준)
    total_days = len(daily_summary)
    # df.shape[0] 대신 len(df) 사용
    rainy_days = len(daily_summary[daily_summary['평균강수확률'] >= 50.0])
    rain_advice = ""
    
    if rainy_days >= (total_days / 2):
        rain_advice = "🌧️ **비 또는 눈 소식이 잦아요**. 외출 시 꼭 우산을 챙겨주세요."
        
    # 4. 대기질 분석 (현재 AQI 기준)
    air_advice = ""
    if pollution_response and 'list' in pollution_response:
        aqi = pollution_response['list'][0]['main']['aqi']
        aqi_status_kr, _ = AQI_STATUS.get(aqi, ("알 수 없음", "❓"))
        
        if aqi >= 3: # 나쁨(3), 상당히 나쁨(4), 매우 나쁨(5)
            air_advice = f"😷 현재 **대기 질이 '{aqi_status_kr}' 수준**이에요. 외출 시 KF94 마스크를 챙겨주세요."

    # 5. 종합 조언 생성
    summary_list = [temp_advice]
    
    if diff_advice:
        summary_list.append(diff_advice)

    if rain_advice:
        summary_list.append(rain_advice)
    
    if air_advice:
        summary_list.append(air_advice)

    # 비/눈/대기질 이슈가 없고 온도가 적당할 때 일반 날씨 조언 추가
    if not rain_advice and not air_advice and 16 <= avg_max_temp < 27:
        summary_list.append("☀️ **맑고 좋은 날씨**가 예상되니, 즐거운 한 주 보내세요!")
        
    return "\n\n".join(summary_list)


# ----------------------------
# Streamlit App UI
# ----------------------------

initialize_session_state()

st.title("국내 날씨 및 미세먼지 예보 🌤️💨")
st.markdown("---")

if not st.session_state.search_performed:

    input_city = st.text_input("지명 입력", "서울")

    if st.button("날씨 및 미세먼지 정보 가져오기 (검색)"):
        if input_city:
            fetch_weather_data(input_city)
        else:
            st.warning("도시 이름을 입력해 주세요.")
else:
    
    data = st.session_state.city_data['weather_data']
    pollution_response = st.session_state.city_data['pollution_response']
    city = st.session_state.city_data['display_city_name']
    lat = st.session_state.city_data['lat']
    lon = st.session_state.city_data['lon']


    # 1. 상단 현재 날씨 정보
    st.markdown(f"## {city}")
    
    current_weather = data['list'][0]
    current_temp = current_weather['main']['temp']
    
    forecast_list_24hr = data['list'][:8] 
    min_temp = min(item['main']['temp_min'] for item in forecast_list_24hr)
    max_temp = max(item['main']['temp_max'] for item in forecast_list_24hr)
    
    feels_like = current_weather['main']['feels_like']
    current_desc_en = current_weather['weather'][0]['description']
    current_desc_kr = WEATHER_TRANSLATION.get(current_desc_en, current_desc_en)
    
    # 아이콘 통일 로직 적용
    icon = normalize_icon_code(current_weather['weather'][0]['icon'])
    
    current_dt_utc = pd.to_datetime(current_weather['dt_txt']).tz_localize('UTC')
    current_time_kst = current_dt_utc.tz_convert('Asia/Seoul').strftime('%m월 %d일, 오후 %I:%M')

    st.markdown(f"""
    <div style="display: flex; align-items: center; justify-content: flex-start; gap: 20px;">
        <h1 style="font-size: 5em; margin: 0;">{current_temp:.0f}°</h1>
        <img src="http://openweathermap.org/img/wn/{icon}@2x.png" alt="날씨 아이콘" style="width: 100px; height: 100px;"/>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(f"**{current_desc_kr}**")
    st.markdown(f"⬆️{max_temp:.0f}° / ⬇️{min_temp:.0f}°")
    st.markdown(f"체감온도 {feels_like:.0f}°")
    st.markdown(f"{current_time_kst}")
    st.markdown("---")
    
    # 2. 미세먼지 정보
    st.markdown("### 💨 현재 대기 질 정보")
    if pollution_response and 'list' in pollution_response:
        current_air = pollution_response['list'][0]
        aqi = current_air['main']['aqi']
        aqi_status_kr, aqi_emoji = AQI_STATUS.get(aqi, ("알 수 없음", "❓"))
        components = current_air['components']
        st.markdown(f"""
        <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px;">
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
            
            # 아이콘 통일 로직 적용
            weather_icon_code = normalize_icon_code(item['weather'][0]['icon'])
            
            pop = item['pop'] * 100
            st.markdown(f"""
            <div style="text-align: center; padding: 5px;">
                <p style="font-weight: bold; margin-bottom: 5px;">{time_str}</p>
                <img src="http://openweathermap.org/img/wn/{weather_icon_code}.png" alt="날씨 아이콘" style="width: 40px; height: 40px;"/>
                <p style="font-size: 1.1em; margin-top: 5px; margin-bottom: 5px;">{temp:.0f}°</p>
                <p style="font-size: 0.8em; color: #888; margin: 0;">💧 {pop:.0f}%</p>
            </div>
            """, unsafe_allow_html=True)
    st.markdown("---")
    
    # 4. 일별 요약 (주간 예보)
    st.markdown("### 📅 주간 날씨 예보")
    
    # 데이터프레임 생성
    df_full = pd.DataFrame(
        [{
            '날짜/시간': pd.to_datetime(item['dt_txt']),
            '요일': pd.to_datetime(item['dt_txt']).tz_localize('UTC').tz_convert('Asia/Seoul').strftime('%a'), 
            '예상온도 (°C)': item['main']['temp'],
            '체감온도 (°C)': item['main']['feels_like'],
            '최저온도_raw': item['main']['temp_min'],
            '최고온도_raw': item['main']['temp_max'],
            '날씨_아이콘': item['weather'][0]['icon'],
            '강수확률': item['pop'] * 100
        } for item in data['list']]
    )
    
    # 일별 요약
    daily_summary = df_full.groupby(df_full['날짜/시간'].dt.date).agg(
        요일=('요일', 'first'),
        최고온도=('최고온도_raw', np.max),
        최저온도=('최저온도_raw', np.min),
        대표날씨_아이콘=('날씨_아이콘', lambda x: x.mode()[0]),
        평균강수확률=('강수확률', np.mean)
    ).reset_index()
    
    KOREAN_WEEKDAYS_MAP = {0: '월', 1: '화', 2: '수', 3: '목', 4: '금', 5: '토', 6: '일'}
    today = datetime.datetime.now().date()
    daily_summary['평균강수확률'] = daily_summary['평균강수확률'].round(0) 
    daily_summary['요일'] = daily_summary['날짜/시간'].apply(lambda x: 
                                     '오늘' if x == today else 
                                     '내일' if x == today + datetime.timedelta(days=1) else 
                                     KOREAN_WEEKDAYS_MAP[x.weekday()])

    # 주간 날씨 테이블 헤더
    st.markdown(f"""
    <div style="display: flex; align-items: center; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #ddd; margin-bottom: 5px; font-weight: bold; color: #555;">
        <div style="width: 15%;">요일</div>
        <div style="width: 15%; text-align: left; font-size: 0.9em;">강수확률</div>
        <div style="width: 20%; text-align: center;">날씨</div>
        <div style="width: 25%; text-align: right;">최고 온도</div>
        <div style="width: 25%; text-align: right;">최저 온도</div>
    </div>
    """, unsafe_allow_html=True)
    
    for index, row in daily_summary.iterrows():
        day_label = row['요일']
        max_t = row['최고온도']
        min_t = row['최저온도']
        
        # 아이콘 통일 로직 적용
        weather_icon_code = normalize_icon_code(row['대표날씨_아이콘'])

        avg_pop = row['평균강수확률']
        
        # 데이터 행
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
    
    # 5. 5일 온도 변화 그래프
    st.markdown("### 📈 5일 온도 변화 그래프")
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_full['날짜/시간'], y=df_full['예상온도 (°C)'], 
                             mode='lines+markers', name='예상온도 (°C)', line=dict(color='orange')))
    fig.add_trace(go.Scatter(x=df_full['날짜/시간'], y=df_full['체감온도 (°C)'], 
                             mode='lines+markers', name='체감온도 (°C)', line=dict(color='blue', dash='dot')))
    fig.update_layout(
        xaxis=dict(title="날짜", tickformat="%m-%d", tickangle=0,),
        yaxis_title="온도 (°C)", hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=20, r=20, t=30, b=20)
    )
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("---")

    # 6. 주간 날씨 분석 및 조언
    st.markdown("### 💡 이번 주 날씨 조언")
    
    summary_text = get_weekly_summary_text(daily_summary, pollution_response)
    
    st.info(summary_text)
    st.markdown("---")

    # 7. 다른 지역 검색
    st.markdown("### 📍 다른 지역 검색")
    
    new_city_name_input = st.text_input("새로운 지명 입력", city, key="new_city_input")
    if st.button("날씨 정보 다시 가져오기"):
        if new_city_name_input:
            fetch_weather_data(new_city_name_input)
        else:
            st.warning("도시 이름을 입력해 주세요.")

    # 8. 현재 위치 지도
    st.markdown("### 🗺️ 현재 위치 지도")
    map_data = pd.DataFrame({'lat': [lat], 'lon': [lon]})
    st.map(map_data, zoom=10)
    st.caption(f"**지도 중심 위치:** 위도 {lat:.2f}, 경도 {lon:.2f}")

