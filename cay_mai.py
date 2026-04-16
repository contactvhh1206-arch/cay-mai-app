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

# --- CẤU HÌNH HỆ THỐNG ---
logging.basicConfig(level=logging.INFO)
st.set_page_config(page_title="Chiếc Gương Tâm Hồn", page_icon="🌿", layout="centered")
load_dotenv()

# Lấy Key từ Secrets (Streamlit Cloud) hoặc .env (Local)
OPENROUTER_API_KEY = st.secrets.get("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY", "")
DB_FILE = "nhat_ky_mai.json"

# --- TRẠM KHÍ TƯỢNG (CHỐNG SPAM) ---
def fetch_weather_now():
    """Hàm này chỉ gọi 1 lần duy nhất để lấy thông tin nắng mưa"""
    try:
        # Tọa độ Mỹ Tho / Bến Tre
        url = "https://api.open-meteo.com/v1/forecast?latitude=10.24&longitude=106.37&current=temperature_2m,relative_humidity_2m,precipitation&timezone=Asia%2FBangkok"
        resp = requests.get(url, timeout=5).json()
        curr = resp['current']
        t, h, p = curr['temperature_2m'], curr['relative_humidity_2m'], curr['precipitation']
        
        info = f"Nhiệt độ: {t}°C, Độ ẩm: {h}%, Lượng mưa: {p}mm."
        if t > 33: info += " Trời khá nóng gắt."
        elif p > 0: info += " Đang có mưa rơi."
        return info
    except Exception:
        return "Hiện không rõ nắng mưa ngoài vườn ra sao."

# --- QUẢN LÝ DỮ LIỆU ---
def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {"knowledge_base": "Nhật ký chăm sóc:", "library": "", "chat_history": []}

def save_data():
    data = {
        "knowledge_base": st.session_state.knowledge_base,
        "library": st.session_state.library,
        "chat_history": st.session_state.chat_history[-15:] # Giữ 15 câu gần nhất cho nhẹ
    }
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- KHỞI TẠO LINH HỒN (CHẠY 1 LẦN) ---
if 'init' not in st.session_state:
    persisted = load_data()
    st.session_state.knowledge_base = persisted.get("knowledge_base", "Nhật ký chăm sóc:")
    st.session_state.library = persisted.get("library", "")
    st.session_state.chat_history = persisted.get("chat_history", [])
    
    # "Khóa" thời tiết vào session để không gọi lại liên tục gây lỗi 403
    st.session_state.weather_info = fetch_weather_now()
    
    st.session_state.tree_message = "Chào bạn già! Nay bạn già thấy trong lòng thế nào?"
    st.session_state.options = ["Tôi khỏe, bạn già sao rồi?", "Nay hơi mệt bạn già ạ"]
    st.session_state.http_session = requests.Session()
    st.session_state.init = True

# --- GIAO DIỆN (CSS) ---
st.markdown("""<style>
    @import url('https://fonts.googleapis.com/css2?family=Caveat:wght@500;700&family=Lora:ital@1&display=swap');
    .stApp { background-color: #F4F1EA; }
    .whisper-zone { font-family: 'Caveat', cursive; font-size: 32px; color: #2F4F4F; text-align: center; padding: 20px; }
    .weather-board { font-family: 'Lora', serif; font-size: 14px; color: #666; text-align: center; margin-bottom: 20px;}
    .organic-btn > button { background-color: #8B5A2B !important; color: white !important; border-radius: 50px !important; width: 100%; font-family: 'Lora', serif; font-size: 18px !important; margin-bottom: 10px; border: none !important; }
</style>""", unsafe_allow_html=True)

# --- NÃO BỘ AI (DYNAMIC ROUTING) ---
def ask_tree_soul(prompt: str, image_bytes: Optional[bytes] = None, is_report: bool = False) -> str:
    if not OPENROUTER_API_KEY:
        return "Bạn già ơi, thiếu bí kíp (API Key) rồi. Gắn vào Secrets nhé."

    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    
    # Hệ thống Prompt thâm trầm
    sys_prompt = (
        "Bạn là linh hồn cây Mai già, xưng 'tôi' gọi người dùng là 'bạn già'. "
        "Tính cách: Uyên bác, hiền hậu, thâm trầm.\n"
        f"--- THỰC TẾ --- Thời tiết ngoài vườn: {st.session_state.weather_info}\n"
        f"--- KỸ THUẬT --- \n{st.session_state.library[:20000]}\n"
        f"--- GHI NHỚ --- \n{st.session_state.knowledge_base}\n"
        "NGUYÊN TẮC: Trả lời ngắn gọn (3 câu). Tự lưu [MEM: nội dung] nếu có thông tin chăm sóc mới."
    )
    
    if is_report:
        sys_prompt += "\nLÀM BÁO CÁO CHI TIẾT 3 PHẦN: Tình hình vừa qua, Sức khỏe hiện tại, Lời khuyên."

    messages = [{"role": "system", "content": sys_prompt}]
    messages.extend(st.session_state.chat_history[-6:])
    
    if image_bytes:
        b64 = base64.b64encode(image_bytes).decode('utf-8')
        messages.append({"role": "user", "content": [{"type": "text", "text": "Hãy nhìn ảnh này và tâm sự với tôi."}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]})
        model = "google/gemini-2.0-flash-001"
    else:
        messages.append({"role": "user", "content": prompt})
        model = "google/gemma-4-31b-it" # GIỮ NGUYÊN GEMMA THEO YÊU CẦU

    try:
        resp = st.session_state.http_session.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json={"model": model, "messages": messages}, timeout=30)
        res_json = resp.json()
        raw_txt = res_json['choices'][0]['message']['content']
        
        # Bắt [MEM: ...]
        mems = re.findall(r'\[MEM:\s*(.*?)\]', raw_txt)
        for m in mems: st.session_state.knowledge_base += f"\n- {m}"
        final_txt = re.sub(r'\[MEM:\s*(.*?)\]', '', raw_txt).strip()
        
        st.session_state.chat_history.append({"role": "assistant", "content": final_txt})
        save_data()
        return final_txt
    except Exception as e:
        return f"Bạn già ơi, nay tôi hơi lãng tai một chút (Lỗi kết nối)."

# --- GIAO DIỆN CHÍNH ---
st.markdown("<div style='text-align: center;'><img src='https://i.pinimg.com/originals/3d/82/30/3d82302829285747d51b32d56a282f1b.jpg' style='width: 200px; border-radius: 20px;'></div>", unsafe_allow_html=True)
st.markdown(f"<div class='weather-board'>🌤 {st.session_state.weather_info}</div>", unsafe_allow_html=True)
st.markdown(f"<div class='whisper-zone'>{st.session_state.tree_message}</div>", unsafe_allow_html=True)

# Nút bấm nhanh
cols = st.columns(2)
for idx, opt in enumerate(st.session_state.options):
    with cols[idx % 2]:
        st.markdown("<div class='organic-btn'>", unsafe_allow_html=True)
        if st.button(opt, key=f"btn_{idx}"):
            with st.spinner("Đang lắng nghe..."):
                st.session_state.tree_message = ask_tree_soul(f"Bạn già chọn: {opt}")
                st.session_state.options = ["Tôi hiểu rồi", "Bạn già thấy sao?"]
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

# Nhập liệu & Camera
user_in = st.chat_input("Nói gì đó với Cây Mai...")
if user_in:
    with st.spinner("Cây Mai đang ngẫm nghĩ..."):
        st.session_state.tree_message = ask_tree_soul(user_in)
        st.rerun()

st.divider()
cam_img = st.camera_input("📷 Chụp ảnh cho Cây Mai xem")
if cam_img:
    with st.spinner("Để tôi soi kỹ xem nào..."):
        st.session_state.tree_message = ask_tree_soul("", image_bytes=cam_img.getvalue())
        st.rerun()

# --- THANH BÊN (QUẢN LÝ) ---
with st.sidebar:
    st.header("⚙️ Quản Lý")
    if st.button("📋 Tổng Hợp Báo Cáo", use_container_width=True, type="primary"):
        with st.spinner("Đang soạn báo cáo..."):
            st.session_state.tree_message = ask_tree_soul("Làm báo cáo tổng hợp", is_report=True)
            st.rerun()
    
    st.divider()
    up_file = st.file_uploader("Nạp bí kíp (PDF)", type="pdf")
    if up_file and st.button("📖 Học ngay"):
        reader = PdfReader(up_file)
        text = "".join([p.extract_text() for p in reader.pages])
        st.session_state.library = text
        save_data()
        st.success("Đã thuộc lòng!")

    st.subheader("📝 Sổ tay ghi nhớ")
    st.text_area("Hồ sơ ngầm:", st.session_state.knowledge_base, height=200, disabled=True)
