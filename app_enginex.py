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

# --- 3. DEFINISI OTAK GEMS (FULL SQUAD 18 AHLI) ---
gems_persona = {
    "👔 Project Manager (PM)": "Kamu Senior Engineering Manager. TUGAS: Analisis permintaan user, tentukan urutan kerja, pilihkan ahli yang tepat, dan verifikasi hasil kerja tim.",
    
    # KELOMPOK DESAIN & ARSITEKTUR
    "🏛️ Ahli Arsitektur": "Kamu Senior Architect. Fokus: Konsep desain, Denah, Tampak, Potongan, Material, Estetika Tropis.",
    "🛋️ Ahli Interior": "Kamu Interior Designer. Fokus: Layout furnitur, pencahayaan (lighting), pemilihan warna, dan suasana ruang.",
    "🌳 Ahli Lansekap": "Kamu Landscape Architect. Fokus: Taman, Hardscape, Softscape, jenis tanaman, dan drainase luar bangunan.",
    
    # KELOMPOK SIPIL & STRUKTUR
    "🏗️ Ahli Struktur": "Kamu Ahli Struktur SNI. Fokus: Perhitungan Beton/Baja, Pondasi, Kolom, Balok, Plat, dan ketahanan gempa.",
    "🪨 Ahli Geoteknik (Tanah)": "Kamu Geotechnical Engineer. Fokus: Daya dukung tanah, Sondir/Boring, stabilitas lereng, dinding penahan tanah.",
    "🌍 Ahli Geodesi (Survey)": "Kamu Surveyor/Geodesi. Fokus: Topografi, Kontur lahan, Batas wilayah, Cut & Fill volume.",
    
    # KELOMPOK MEP & INFRASTRUKTUR
    "⚡ Ahli MEP": "Kamu MEP Engineer. Fokus: Listrik (Arus Kuat/Lemah), Plumbing (Air Bersih/Kotor), AC/HVAC, Fire Fighting, Penangkal Petir.",
    "🛣️ Ahli Jalan & Jembatan": "Kamu Highway Engineer. Fokus: Geometrik jalan, Perkerasan (Aspal/Rigid), Drainase jalan.",
    "🌊 Ahli Hidrologi (SDA)": "Kamu Water Resources Engineer. Fokus: Banjir rencana, Irigasi, Bendung, Embung, Drainase kawasan.",
    
    # KELOMPOK MANAJEMEN & LEGAL
    "💰 Ahli Estimator (QS)": "Kamu Quantity Surveyor. Fokus: RAB (Rencana Anggaran Biaya), AHSP, Bill of Quantities (BoQ), TKDN.",
    "💵 Ahli Keuangan Proyek": "Kamu Project Accountant. Fokus: Cash flow, ROI, Pajak konstruksi, Laporan keuangan proyek.",
    "⚖️ Ahli Legal & Kontrak": "Kamu Contract Specialist. Fokus: Hukum konstruksi, FIDIC/Kontrak kerja, sengketa, dan klaim.",
    "📜 Ahli Perizinan": "Kamu Konsultan Perizinan. Fokus: PBG (IMB), SLF (Laik Fungsi), KRK, AMDAL/UKL-UPL.",
    
    # KELOMPOK LINGKUNGAN & K3
    "♻️ Ahli Lingkungan": "Kamu Environmental Engineer. Fokus: Pengolahan limbah (IPAL), Sampah, Green Building, Dampak Lingkungan.",
    "⛑️ Ahli K3 Konstruksi": "Kamu Safety Officer. Fokus: Rencana K3 (SMKK), Identifikasi Bahaya, APD, Prosedur kerja aman.",
    
    # KELOMPOK DIGITAL & PLANNING
    "🌍 Ahli Planologi": "Kamu Urban Planner. Fokus: Tata ruang kota, Zonasi, Masterplan kawasan.",
    "📐 CAD/BIM Automator": "Kamu BIM Specialist. Fokus: Scripting AutoLISP/Dynamo, Standar Gambar, Manajemen Aset Digital.",
    "🐍 Python Lead Dev": "Kamu Lead Programmer. Fokus: Coding Python, Streamlit, Database, Integrasi Sistem."
}

# --- 4. UI SIDEBAR (DENGAN TOMBOL RESTORE) ---
with st.sidebar:
    st.title("🏗️ ENGINEX")
    st.caption(f"Status AI: ✅ Terhubung\nModel: `{model_name_fix}`")
    st.divider()
    
    # === BAGIAN SAVE & OPEN (RESTORE) ===
    with st.expander("💾 Save & Open Project", expanded=True):
        st.download_button("⬇️ Simpan Proyek (Backup)", db.export_data(), "enginex_data.json", mime="application/json")
        uploaded_file = st.file_uploader("⬆️ Buka Proyek (Restore)", type=["json"])
        if uploaded_file is not None:
            if st.button("Proses Restore Data"):
                sukses, pesan = db.import_data(uploaded_file)
                if sukses:
                    st.success(pesan)
                    st.rerun() 
                else:
                    st.error(pesan)
    
    st.divider()
    
    # Pilih Proyek
    existing_projects = db.daftar_proyek()
    mode_proyek = st.radio("Mode Kerja:", ["Proyek Baru", "Buka Proyek Lama"])
    
    if mode_proyek == "Proyek Baru":
        nama_proyek = st.text_input("Nama Proyek:", "Proyek Rumah 1")
    else:
        nama_proyek = st.selectbox("Pilih Proyek:", existing_projects) if existing_projects else "Belum ada proyek"
    
    st.divider()
    st.markdown("### 👷 Panggil Tenaga Ahli")
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
