import streamlit as st
import google.generativeai as genai
import pandas as pd

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="ENGINEX Super App", page_icon="🏗️", layout="wide")

# --- KONEKSI BACKEND ---
try:
    from backend_enginex import EnginexBackend
    if 'backend' not in st.session_state:
        st.session_state.backend = EnginexBackend()
    db = st.session_state.backend
except ImportError:
    st.error("⚠️ File 'backend_enginex.py' belum dibuat di GitHub!")
    st.stop()

# --- CSS ---
st.markdown("""
<style>
    .main-header {font-size: 30px; font-weight: bold; color: #1E3A8A; margin-bottom: 10px;}
</style>
""", unsafe_allow_html=True)

# --- 1. SETUP API KEY ---
api_key = st.secrets.get("GOOGLE_API_KEY")
if not api_key:
    with st.sidebar:
        api_key = st.text_input("🔑 Masukkan Gemini API Key:", type="password")
        if not api_key:
            st.warning("Masukkan API Key dulu.")
            st.stop()

genai.configure(api_key=api_key)

# --- 2. LOGIKA AUTO-DETECT MODEL (JURUS ANTI 404) ---
# Kita tidak menembak nama model, tapi minta daftar dari Google
@st.cache_resource
def get_working_model():
    try:
        available_models = []
        # Minta daftar model yang bisa generate text
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
        
        if not available_models:
            return None, "Tidak ada model AI yang tersedia untuk Key ini."

        # Prioritas: Cari yang ada kata 'flash' (cepat), kalau tidak ada cari 'pro'
        chosen_model_name = available_models[0] # Ambil yang pertama ketemu sbg cadangan
        for m in available_models:
            if "flash" in m: 
                chosen_model_name = m; break
            elif "pro" in m and "vision" not in m:
                chosen_model_name = m
        
        return chosen_model_name, None
    except Exception as e:
        return None, str(e)

# Panggil fungsi deteksi
model_name_fix, error_msg = get_working_model()

if error_msg:
    st.error(f"❌ Masalah Akun Google AI: {error_msg}")
    st.stop()

# --- 3. DEFINISI OTAK GEMS ---
gems_persona = {
    "👔 Project Manager": "Kamu Senior Engineering Manager. Analisis permintaan user, tentukan ahli yang dibutuhkan, dan verifikasi hasil.",
    "🏛️ Ahli Arsitektur": "Kamu Senior Architect. Fokus: Denah, Tampak, Material, Estetika Tropis.",
    "🏗️ Ahli Struktur": "Kamu Ahli Struktur SNI. Fokus: Beton, Baja, Pondasi.",
    "💰 Ahli Estimator": "Kamu QS (RAB). Fokus: Volume, Harga Satuan, Budgeting.",
    "🌊 Ahli Hidrologi": "Kamu Ahli Air. Fokus: Banjir, Drainase, Irigasi.",
    "🐍 Python Lead": "Kamu Lead Programmer. Fokus: Coding Python & Streamlit.",
}

# --- 4. UI SIDEBAR ---
with st.sidebar:
    st.title("🏗️ ENGINEX")
    st.caption(f"Status AI: ✅ Terhubung\nModel: `{model_name_fix}`") # Info model yang dipakai
    st.divider()
    
    existing_projects = db.daftar_proyek()
    mode_proyek = st.radio("Mode:", ["Proyek Baru", "Buka Proyek Lama"])
    
    if mode_proyek == "Proyek Baru":
        nama_proyek = st.text_input("Nama Proyek:", "Proyek Rumah 1")
    else:
        nama_proyek = st.selectbox("Pilih Proyek:", existing_projects) if existing_projects else "Proyek Default"
            
    st.divider()
    selected_gem = st.selectbox("Panggil Tim Ahli:", list(gems_persona.keys()))
    
    if st.button("Hapus Chat"):
        db.clear_chat(nama_proyek, selected_gem)
        st.rerun()

# --- 5. AREA CHAT ---
st.markdown(f'<div class="main-header">{nama_proyek}</div>', unsafe_allow_html=True)
st.caption(f"Diskusi dengan: **{selected_gem}**")

history = db.get_chat_history(nama_proyek, selected_gem)
for chat in history:
    with st.chat_message(chat['role']):
        st.markdown(chat['content'])

if prompt := st.chat_input("Ketik pesan..."):
    db.simpan_chat(nama_proyek, selected_gem, "user", prompt)
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner(f"{selected_gem} berpikir..."):
            try:
                # INSTANSIASI MODEL DENGAN NAMA YANG SUDAH DITEMUKAN (AUTO)
                model = genai.GenerativeModel(model_name_fix)
                
                # Instruksi Manual
                full_prompt = f"PERAN: {gems_persona[selected_gem]}\nUSER: {prompt}"
                
                # Chat logic standar (history manual untuk aman)
                chat_history_formatted = [
                    {"role": "user" if h['role']=="user" else "model", "parts": [h['content']]} 
                    for h in history
                ]
                
                chat = model.start_chat(history=chat_history_formatted)
                response = chat.send_message(full_prompt)
                
                st.markdown(response.text)
                db.simpan_chat(nama_proyek, selected_gem, "assistant", response.text)
                
            except Exception as e:
                st.error(f"Error Generasi: {e}")
