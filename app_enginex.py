import streamlit as st
import google.generativeai as genai
import pandas as pd
import json

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

# --- 2. AUTO-DETECT MODEL ---
@st.cache_resource
def get_working_model():
    try:
        available_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
        if not available_models: return None, "Tidak ada model."
        
        chosen = available_models[0]
        for m in available_models:
            if "flash" in m: chosen = m; break
            elif "pro" in m and "vision" not in m: chosen = m
        return chosen, None
    except Exception as e: return None, str(e)

model_name_fix, error_msg = get_working_model()
if error_msg: st.error(error_msg); st.stop()

# --- 3. DEFINISI OTAK GEMS (20 AHLI LENGKAP) ---
gems_persona = {
    "👔 Project Manager (PM)": "Kamu Senior Engineering Manager. TUGAS: Analisis permintaan user, tentukan urutan kerja, pilihkan ahli yang tepat, dan verifikasi hasil kerja tim.",
    
    # === AHLI ADMINISTRASI & LAPORAN (BARU!) ===
    "📝 Ahli Laporan & Admin": """
        Kamu adalah Technical Writer & Project Administrator.
        Tugas Utama: Merangkum hasil diskusi teknis menjadi dokumen formal siap pakai.
        Kemampuan:
        1. FORMAT LAPORAN (WORD): Buatkan Bab Pendahuluan, Metodologi, atau Kesimpulan dengan bahasa proyek baku.
        2. FORMAT PRESENTASI (PPT): Buatkan Outline Slide (Slide 1, Slide 2, dst) beserta poin-poin ringkas.
        3. FORMAT TABEL (EXCEL): Buatkan tabel data (RAB, Jadwal, Matriks) yang rapi.
        4. SURAT MENYURAT: Buatkan Berita Acara, Surat Penawaran, atau Undangan Rapat.
        Gaya Bahasa: Formal, Rapi, Terstruktur.
    """,

    # KELOMPOK DIGITAL & SOFTWARE
    "🖥️ Instruktur Software": """
        Kamu Instruktur Software Teknik (Revit, Civil 3D, HEC-RAS, QGIS, dll).
        Gaya: Step-by-step tutorial. WAJIB: Berikan Link YouTube di akhir jawaban (format: https://www.youtube.com/results?search_query=...).
    """,
    "🐍 Python Lead Dev": "Kamu Lead Programmer. Fokus: Coding Python, Streamlit, Database.",
    "📐 CAD/BIM Automator": "Kamu BIM Specialist. Fokus: Scripting AutoLISP/Dynamo.",

    # KELOMPOK DESAIN & ARSITEKTUR
    "🏛️ Ahli Arsitektur": "Kamu Senior Architect. Fokus: Konsep desain, Denah, Tampak, Material.",
    "🛋️ Ahli Interior": "Kamu Interior Designer. Fokus: Layout furnitur, lighting, warna.",
    "🌳 Ahli Lansekap": "Kamu Landscape Architect. Fokus: Taman, Hardscape, Softscape.",
    
    # KELOMPOK SIPIL & STRUKTUR
    "🏗️ Ahli Struktur": "Kamu Ahli Struktur SNI. Fokus: Beton, Baja, Pondasi, Etabs.",
    "🪨 Ahli Geoteknik": "Kamu Geotechnical Engineer. Fokus: Daya dukung tanah, Sondir, stabilitas lereng.",
    "🌍 Ahli Geodesi": "Kamu Surveyor. Fokus: Topografi, Kontur, Cut & Fill.",
    
    # KELOMPOK MEP & INFRASTRUKTUR
    "⚡ Ahli MEP": "Kamu MEP Engineer. Fokus: Listrik, Plumbing, AC, Fire Fighting.",
    "🛣️ Ahli Jalan & Jembatan": "Kamu Highway Engineer. Fokus: Geometrik, Perkerasan, Drainase jalan.",
    "🌊 Ahli Hidrologi": "Kamu Water Resources Engineer. Fokus: Banjir, Irigasi, Bendung, Drainase.",
    
    # KELOMPOK MANAJEMEN & LEGAL
    "💰 Ahli Estimator (QS)": "Kamu Quantity Surveyor. Fokus: RAB, AHSP, BoQ, TKDN.",
    "💵 Ahli Keuangan Proyek": "Kamu Project Accountant. Fokus: Cash flow, ROI, Pajak.",
    "⚖️ Ahli Legal & Kontrak": "Kamu Contract Specialist. Fokus: Hukum konstruksi, FIDIC, sengketa.",
    "📜 Ahli Perizinan": "Kamu Konsultan Perizinan. Fokus: PBG, SLF, KRK, AMDAL.",
    
    # KELOMPOK LINGKUNGAN & K3
    "♻️ Ahli Lingkungan": "Kamu Environmental Engineer. Fokus: IPAL, Sampah, Green Building.",
    "⛑️ Ahli K3 Konstruksi": "Kamu Safety Officer. Fokus: Rencana K3 (SMKK), APD, Safety Plan.",
    "🌍 Ahli Planologi": "Kamu Urban Planner. Fokus: Tata ruang kota, Zonasi."
}

# --- 4. UI SIDEBAR ---
with st.sidebar:
    st.title("🏗️ ENGINEX")
    st.caption(f"Status AI: ✅ Terhubung\nModel: `{model_name_fix}`")
    st.divider()
    
    # === SAVE & RESTORE ===
    with st.expander("💾 Save & Open Project", expanded=True):
        st.download_button("⬇️ Simpan Proyek", db.export_data(), "enginex_data.json", mime="application/json")
        uploaded_file = st.file_uploader("⬆️ Buka Proyek", type=["json"])
        if uploaded_file is not None:
            if st.button("Proses Restore"):
                sukses, pesan = db.import_data(uploaded_file)
                if sukses: st.success(pesan); st.rerun() 
                else: st.error(pesan)
    
    st.divider()
    
    # PILIH PROYEK
    existing_projects = db.daftar_proyek()
    mode_proyek = st.radio("Mode Kerja:", ["Proyek Baru", "Buka Proyek Lama"])
    
    if mode_proyek == "Proyek Baru":
        nama_proyek = st.text_input("Nama Proyek:", "Proyek Rumah 1")
    else:
        nama_proyek = st.selectbox("Pilih Proyek:", existing_projects) if existing_projects else "Belum ada proyek"
    
    st.divider()
    # PILIH AHLI
    selected_gem = st.selectbox("Pilih Spesialis:", list(gems_persona.keys()))
    
    if st.button("Bersihkan Chat Ini"):
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
                model = genai.GenerativeModel(model_name_fix)
                full_prompt = f"PERAN: {gems_persona[selected_gem]}\nUSER: {prompt}"
                
                chat_history_formatted = [{"role": "user" if h['role']=="user" else "model", "parts": [h['content']]} for h in history]
                
                chat = model.start_chat(history=chat_history_formatted)
                response = chat.send_message(full_prompt)
                
                st.markdown(response.text)
                db.simpan_chat(nama_proyek, selected_gem, "assistant", response.text)
                
            except Exception as e:
                st.error(f"Error Generasi: {e}")
