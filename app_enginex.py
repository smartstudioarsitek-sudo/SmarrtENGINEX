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
    st.error("⚠️ File 'backend_enginex.py' belum dibuat! Silakan buat file tersebut di GitHub.")
    st.stop()

# --- CSS PRO ---
st.markdown("""
<style>
    .main-header {font-size: 30px; font-weight: bold; color: #1E3A8A; margin-bottom: 10px;}
    .chat-box {border: 1px solid #ddd; padding: 15px; border-radius: 10px; height: 400px; overflow-y: scroll;}
    div.stButton > button {width: 100%;}
</style>
""", unsafe_allow_html=True)

# --- 1. SETUP API KEY (WAJIB) ---
# Cek Secrets atau Input Manual
api_key = st.secrets.get("GOOGLE_API_KEY")
if not api_key:
    with st.sidebar:
        api_key = st.text_input("🔑 Masukkan Gemini API Key:", type="password")
        if not api_key:
            st.warning("Masukkan API Key untuk mengaktifkan AI.")
            st.stop()

genai.configure(api_key=api_key)

# --- 2. DEFINISI OTAK GEMS (TIM AHLI) ---
gems_persona = {
    "👔 Project Manager (Verifikator)": """
        Kamu adalah Senior Engineering Manager. TUGAS UTAMA:
        1. Menganalisis permintaan user (misal: "Saya mau bangun hotel").
        2. Menentukan Gem mana yang harus dipanggil (misal: "Panggil Arsitek untuk denah, lalu Struktur untuk pondasi").
        3. VERIFIKASI: Mengecek hasil kerja Gem lain. Jika ada kode terpotong atau hitungan salah, kamu harus minta revisi.
    """,
    "🏛️ Ahli Arsitektur (Design)": "Kamu Senior Architect. Fokus: Konsep, Denah, Tampak, Material, Estetika Tropis.",
    "🏗️ Ahli Struktur (Sipil)": "Kamu Ahli Struktur SNI. Fokus: Beton, Baja, Pondasi, Etabs/SAP2000.",
    "💰 Ahli Estimator (RAB)": "Kamu Quantity Surveyor (QS). Fokus: Volume, Harga Satuan, Budgeting.",
    "🌍 Ahli Planologi (Tata Ruang)": "Kamu Urban Planner. Fokus: Zonasi, KDB/KLB, GIS, Peraturan Daerah.",
    "🌊 Ahli Hidrologi (Air)": "Kamu Hydrologist. Fokus: Banjir, Drainase, Irigasi, Bendung.",
    "⚡ Ahli MEP (Mekanikal Elektrikal)": "Kamu Ahli MEP. Fokus: Listrik, Plumbing, AC, Pemadam Kebakaran.",
    "🛣️ Ahli Jalan & Jembatan": "Kamu Highway Engineer. Fokus: Geometrik Jalan, Perkerasan Aspal/Beton.",
    "🐍 Python Lead Developer": "Kamu Lead Programmer. Fokus: Coding Python, Streamlit, Database SQLite.",
    "📐 CAD/BIM Automator": "Kamu Ahli Scripting. Fokus: AutoLISP (AutoCAD) dan Dynamo (Revit)."
}

# --- 3. UI SIDEBAR ---
with st.sidebar:
    st.title("🏗️ ENGINEX")
    st.caption("Integrated Engineering AI")
    st.divider()
    
    # Pilih Proyek (Session)
    st.subheader("📁 Pilih Proyek")
    existing_projects = db.daftar_proyek()
    mode_proyek = st.radio("Mode:", ["Proyek Baru", "Buka Proyek Lama"])
    
    if mode_proyek == "Proyek Baru":
        nama_proyek = st.text_input("Nama Proyek Baru:", "Desain Rumah Tipe 45")
    else:
        if existing_projects:
            nama_proyek = st.selectbox("Daftar Proyek:", existing_projects)
        else:
            st.warning("Belum ada proyek tersimpan.")
            nama_proyek = "Project Default"
            
    st.divider()
    
    # Pilih Tim Ahli
    st.subheader("👥 Panggil Tim Ahli")
    selected_gem = st.selectbox("Siapa yang mau ditanya?", list(gems_persona.keys()))
    
    if st.button("🗑️ Hapus Chat Proyek Ini"):
        db.clear_chat(nama_proyek, selected_gem)
        st.rerun()

    st.divider()
    st.download_button("💾 Backup Semua Data", db.export_data(), "enginex_full_backup.json")

# --- 4. AREA UTAMA (CHAT INTERFACE) ---
st.markdown(f'<div class="main-header">{nama_proyek}</div>', unsafe_allow_html=True)
st.caption(f"Sedang berdiskusi dengan: **{selected_gem}**")

# A. Tampilkan History Chat dari Database
history = db.get_chat_history(nama_proyek, selected_gem)
for chat in history:
    with st.chat_message(chat['role']):
        st.markdown(chat['content'])

# B. Input User
if prompt := st.chat_input("Tulis instruksi Anda di sini..."):
    # 1. Simpan & Tampilkan Pesan User
    db.simpan_chat(nama_proyek, selected_gem, "user", prompt)
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Proses AI
    with st.chat_message("assistant"):
        with st.spinner(f"{selected_gem} sedang berpikir..."):
            try:
                # Gabungkan Persona + Konteks
                full_instruction = gems_persona[selected_gem]
                
                # Khusus Project Manager: Beri tahu dia tentang tim yang tersedia
                if "Project Manager" in selected_gem:
                    full_instruction += f"\n\nTim yang tersedia: {', '.join(gems_persona.keys())}"

                model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=full_instruction)
                
                # Kirim chat history sebelumnya sebagai konteks (agar nyambung)
                chat_session = model.start_chat(history=[
                    {"role": "user" if h['role']=="user" else "model", "parts": [h['content']]} 
                    for h in history
                ])
                
                response = chat_session.send_message(prompt)
                reply = response.text
                
                st.markdown(reply)
                
                # 3. Simpan Jawaban AI
                db.simpan_chat(nama_proyek, selected_gem, "assistant", reply)
                
            except Exception as e:
                st.error(f"Error AI: {e}")

