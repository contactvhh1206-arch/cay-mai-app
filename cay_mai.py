import base64
import os
import re
import json
import logging
from typing import Optional

import requests
import streamlit as st
from dotenv import load_dotenv
from pypdf import PdfReader 

# --- CẤU HÌNH ---
logging.basicConfig(level=logging.INFO)
st.set_page_config(page_title="Chiếc Gương Tâm Hồn", page_icon="🌿", layout="centered")
load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
DB_FILE = "nhat_ky_mai.json"

# --- 1. ĐIỆP VIÊN THỜI TIẾT (GIỮ TRẠM THÔNG TIN) ---
@st.cache_data(ttl=1800) # Nhớ (Cache) thời tiết trong 30 phút để không gọi mạng liên tục
def get_weather():
    try:
        # Tọa độ khu vực Mỹ Tho / Bến Tre (Lat: 10.24, Lon: 106.37)
        url = "https://api.open-meteo.com/v1/forecast?latitude=10.24&longitude=106.37&current=temperature_2m,relative_humidity_2m,precipitation&timezone=Asia%2FBangkok"
        resp = requests.get(url, timeout=5).json()
        curr = resp['current']
        nhiet_do = curr['temperature_2m']
        do_am = curr['relative_humidity_2m']
        mua = curr['precipitation']
        
        tinh_trang = f"Nhiệt độ: {nhiet_do}°C, Độ ẩm: {do_am}%, Lượng mưa: {mua}mm."
        if nhiet_do > 33: tinh_trang += " Trời khá nóng."
        elif mua > 0: tinh_trang += " Đang có mưa."
        return tinh_trang
    except Exception as e:
        logging.error(f"Lỗi lấy thời tiết: {e}")
        return "Không rõ thời tiết hôm nay thế nào."

def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"knowledge_base": "Nhật ký chăm sóc:", "library": "", "chat_history": []}

def save_data():
    data = {
        "knowledge_base": st.session_state.knowledge_base,
        "library": st.session_state.library,
        "chat_history": st.session_state.chat_history[-20:] # Chỉ lưu 20 câu gần nhất cho nhẹ JSON
    }
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

if 'init' not in st.session_state:
    persisted_data = load_data()
    st.session_state.knowledge_base = persisted_data.get("knowledge_base", "Nhật ký chăm sóc:")
    st.session_state.library = persisted_data.get("library", "")
    st.session_state.chat_history = persisted_data.get("chat_history", [])
    
    st.session_state.tree_message = "Chào bạn già! Bạn già thấy tâm trạng thế nào?"
    st.session_state.options = ["Tôi khỏe, bạn già sao rồi?", "Nay hơi oải bạn già ạ"]
    st.session_state.http_session = requests.Session()
    st.session_state.init = True

# Lấy thời tiết ngay khi mở app
current_weather = get_weather()

# --- CSS ---
st.markdown("""<style>
    @import url('https://fonts.googleapis.com/css2?family=Caveat:wght@500;700&family=Lora:ital@1&display=swap');
    .stApp { background-color: #F4F1EA; }
    .whisper-zone { font-family: 'Caveat', cursive; font-size: 32px; color: #2F4F4F; text-align: center; padding: 20px; line-height: 1.5; }
    .weather-board { font-family: 'Lora', serif; font-size: 14px; color: #555; text-align: center; margin-top: -10px; margin-bottom: 20px;}
    .organic-btn > button { background-color: #8B5A2B !important; color: white !important; border-radius: 50px !important; width: 100%; margin-bottom: 10px; font-family: 'Lora', serif; font-size: 20px !important; padding: 10px 20px !important; border: none !important; box-shadow: 2px 4px 10px rgba(0,0,0,0.1); }
    .organic-btn > button:hover { background-color: #6B4226 !important; transform: scale(1.02); }
</style>""", unsafe_allow_html=True)

# --- NÃO BỘ AI ---
def ask_tree_soul(prompt: str, image_bytes: Optional[bytes] = None, is_report: bool = False) -> str:
    if not OPENROUTER_API_KEY:
        return "Bạn già ơi, hệ thống thiếu API Key. Hãy kiểm tra lại file .env nhé."

    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    
    # 2. BƠM THỜI TIẾT VÀO NÃO CÂY MAI
    system_prompt = (
        "Bạn là linh hồn của một cây Mai già uyên bác, xưng 'tôi' và gọi người dùng là 'bạn già'. "
        "Tính cách: Hiền hậu, thâm trầm nhưng rất tình cảm, hóm hỉnh.\n"
        f"--- THÔNG TIN THỰC TẾ NGAY LÚC NÀY ---\nThời tiết ngoài vườn: {current_weather}\n"
        f"--- THƯ VIỆN KỸ THUẬT ---\n{st.session_state.library[:25000]}\n"
        "--- SỔ TAY GHI NHỚ ---\n" + st.session_state.knowledge_base +
        "\n\nNGUYÊN TẮC:\n"
        "1. Tâm sự là chính. Chủ động nhắc đến thời tiết nếu nó ảnh hưởng đến sức khỏe của Cây hoặc của bạn già.\n"
        "2. Tự động lưu trữ thông tin chăm sóc bằng cú pháp [MEM: nội dung].\n"
    )
    
    if is_report:
        system_prompt += (
            "CHẾ ĐỘ ĐẶC BIỆT: BÁO CÁO TỔNG HỢP. Bạn già đang yêu cầu tóm tắt tình hình. "
            "Trình bày rõ ràng thành 3 phần: \n"
            "🌿 Tình hình vừa qua.\n"
            "🌿 Sức khỏe hiện tại (Cảm nhận của bạn, kết hợp yếu tố thời tiết).\n"
            "🌿 Lời khuyên sắp tới.\n"
        )
    else:
        system_prompt += "Luôn trả lời cực kỳ ngắn gọn, tối đa 3 câu."
    
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(st.session_state.chat_history[-6:])
        
    if image_bytes:
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        messages.append({"role": "user", "content": [{"type": "text", "text": "Hãy nhìn ảnh, phân tích sức khỏe và tâm sự."}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}]})
        st.session_state.chat_history.append({"role": "user", "content": "[Bạn già vừa gửi một bức ảnh]"})
    else:
        messages.append({"role": "user", "content": prompt})
        st.session_state.chat_history.append({"role": "user", "content": prompt})

    # 3. GIỮ NGUYÊN BỘ NÃO THEO YÊU CẦU CỦA VỌC SĨ
    model = "google/gemini-2.0-flash-001" if image_bytes else "google/gemma-4-31b-it"
    
    try:
        response = st.session_state.http_session.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json={"model": model, "messages": messages}, timeout=25)
        response.raise_for_status()
        raw_response = response.json()['choices'][0]['message']['content']
        
        mem_matches = re.findall(r'\[MEM:\s*(.*?)\]', raw_response)
        if mem_matches:
            for mem in mem_matches:
                st.session_state.knowledge_base += f"\n- {mem}"
            raw_response = re.sub(r'\[MEM:\s*(.*?)\]', '', raw_response).strip()
            
        st.session_state.chat_history.append({"role": "assistant", "content": raw_response})
        save_data()
        return raw_response
    except Exception as e: 
        logging.error(f"API Error: {e}")
        return "Bạn già ơi, mây mù che khuất sóng (lỗi kết nối), bạn già nói lại được không?"

# --- GIAO DIỆN CHÍNH ---
st.markdown("<div style='text-align: center;'><img src='https://i.pinimg.com/originals/3d/82/30/3d82302829285747d51b32d56a282f1b.jpg' style='width: 250px; border-radius: 20px;'></div>", unsafe_allow_html=True)

# Bảng thời tiết nhỏ dưới gốc cây
st.markdown(f"<div class='weather-board'>🌤 Trạm Khí Tượng Vườn Mai: {current_weather}</div>", unsafe_allow_html=True)

st.markdown(f"<div class='whisper-zone' style='font-size: 24px; text-align: left; padding: 20px 40px;'>{st.session_state.tree_message}</div>", unsafe_allow_html=True)

col1, col2 = st.columns(2)
for i, option in enumerate(st.session_state.options):
    with [col1, col2][i % 2]:
        st.markdown("<div class='organic-btn'>", unsafe_allow_html=True)
        if st.button(option, key=f"btn_{i}"):
            with st.spinner("Cây Mai đang khẽ rung lá..."):
                st.session_state.tree_message = ask_tree_soul(f"Bạn già nói: '{option}'")
                st.session_state.options = ["Trời nay thế nào?", "Cứ thế nhé"] 
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

user_text = st.chat_input("Tâm sự hoặc hỏi kỹ thuật...")
if user_text:
    with st.spinner("Bạn già đang ngẫm nghĩ..."):
        st.session_state.tree_message = ask_tree_soul(f"Bạn già nói: '{user_text}'.")
        st.session_state.options = ["Đúng vậy", "Tuyệt vời"] 
        st.rerun()

st.divider()
st.markdown("<p style='text-align: center; color: #8B5A2B;'>Nhấn vào ống kính để cho tôi thấy bản thân mình nhé</p>", unsafe_allow_html=True)
camera_photo = st.camera_input("📷", label_visibility="collapsed")

if 'last_photo_size' not in st.session_state: st.session_state.last_photo_size = 0
if camera_photo:
    current_size = len(camera_photo.getvalue())
    if current_size != st.session_state.last_photo_size:
        with st.spinner("Tôi đang nhìn hình ảnh bạn già vừa đưa..."):
            st.session_state.tree_message = ask_tree_soul(prompt="", image_bytes=camera_photo.getvalue())
            st.session_state.options = ["Để tôi lo liệu", "Bạn già yên tâm"]
            st.session_state.last_photo_size = current_size
            st.rerun()

# --- SIDEBAR: TRUNG TÂM QUẢN LÝ ---
with st.sidebar:
    st.header("📊 Phân Tích & Báo Cáo")
    if st.button("📋 Tổng Hợp Báo Cáo Tuần", use_container_width=True, type="primary"):
        with st.spinner("Đang lục lọi trí nhớ và tàng thư..."):
            report_prompt = "Bạn già ơi, tổng hợp lại giúp tôi tình hình chăm sóc dạo gần đây xem nào. Cứ thong thả nói chi tiết nhé."
            st.session_state.tree_message = ask_tree_soul(report_prompt, is_report=True)
            st.session_state.options = ["Cảm ơn bạn già nhiều", "Tôi sẽ ghi nhớ"]
            st.rerun()

    st.divider()
    st.header("📚 Thư Viện Kỹ Thuật")
    uploaded_file = st.file_uploader("Nạp sách bí kíp (PDF/TXT)", type=["pdf", "txt"])
    if uploaded_file and st.button("📖 Học tài liệu này"):
        with st.spinner("Đang chép sách vào đầu..."):
            text = ""
            if uploaded_file.type == "application/pdf":
                reader = PdfReader(uploaded_file)
                for page in reader.pages: text += page.extract_text()
            else: text = uploaded_file.read().decode("utf-8")
            st.session_state.library = text
            save_data()
            st.success("Đã thuộc lòng bí kíp!")

    st.divider()
    st.subheader("📝 Sổ Tay Ghi Nhớ Ngầm")
    st.text_area("Hồ sơ tự động:", value=st.session_state.knowledge_base, height=150, disabled=True)