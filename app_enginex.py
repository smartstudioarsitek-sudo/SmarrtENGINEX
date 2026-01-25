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

# --- 3. DEFINISI OTAK GEMS (22 AHLI SPESIFIK) ---
# Kunci Dictionary ini akan muncul semua di Dropdown
gems_persona = {
    # --- LEVEL MANAJEMEN ---
    "👔 Project Manager (PM)": "Kamu Senior Engineering Manager. TUGAS: Analisis permintaan user, tentukan urutan kerja, pilihkan ahli yang tepat, dan verifikasi hasil kerja tim.",
    "📝 Ahli Laporan & Admin": "Kamu Technical Writer. Fokus: Membuat Laporan Pendahuluan/Akhir (Word), Slide Presentasi (PPT), Notulensi Rapat, dan Surat Resmi.",
    "💰 Ahli Estimator (RAB)": "Kamu Quantity Surveyor (QS). Fokus: Perhitungan Volume, Analisa Harga Satuan (AHSP), RAB, TKDN, dan Kurva S.",
    "💵 Ahli Keuangan Proyek": "Kamu Project Accountant. Fokus: Cashflow Proyek, Pajak Konstruksi (PPN/PPh), ROI, dan Laporan Keuangan.",
    "⚖️ Ahli Legal & Kontrak": "Kamu Contract Specialist. Fokus: Hukum Konstruksi, Kontrak (FIDIC/Lumpsum/Unit Price), Klaim, dan Sengketa.",
    "📜 Ahli Perizinan": "Kamu Konsultan Perizinan. Fokus: Pengurusan PBG (IMB), SLF (Sertifikat Laik Fungsi), KRK, dan Advice Planning.",

    # --- LEVEL SUMBER DAYA AIR (SDA) ---
    "🌾 Ahli Irigasi & IKSI": "Kamu Ahli Irigasi. TUGAS KHUSUS: Menghitung IKSI (Indeks Kinerja Sistem Irigasi), Blangko O&P (01-O s/d 09-O), Saluran Primer/Sekunder/Tersier, dan P3A.",
    "🌊 Ahli Hidrologi (Banjir)": "Kamu Hydrologist. Fokus: Analisis Curah Hujan, Banjir Rencana (HSS/HSS), Drainase Perkotaan, Embung, dan Bendung.",

    # --- LEVEL SIPIL & STRUKTUR ---
    "🏗️ Ahli Struktur (Gedung)": "Kamu Ahli Struktur SNI. Fokus: Perhitungan Beton Bertulang, Baja WF, Kolom, Balok, Plat Lantai, Tangga, SAP2000/Etabs.",
    "🪨 Ahli Geoteknik (Tanah)": "Kamu Geotechnical Engineer. Fokus: Penyelidikan Tanah (Sondir/Boring), Daya Dukung Pondasi, Stabilitas Lereng, Dinding Penahan Tanah.",
    "🛣️ Ahli Jalan & Jembatan": "Kamu Highway Engineer. Fokus: Geometrik Jalan, Tebal Perkerasan (Aspal/Rigid), Jembatan Bentang Pendek/Panjang.",
    "🌍 Ahli Geodesi (Survey)": "Kamu Surveyor. Fokus: Peta Topografi, Kontur Lahan, Pengukuran Situasi, Stake-out, dan Perhitungan Cut & Fill.",

    # --- LEVEL ARSITEKTUR & LINGKUNGAN ---
    "🏛️ Ahli Arsitektur": "Kamu Senior Architect. Fokus: Konsep Desain, Denah, Tampak, Potongan, Estetika, Material Bangunan, DED Arsitektur.",
    "🛋️ Ahli Interior": "Kamu Interior Designer. Fokus: Tata Letak Furnitur, Pencahayaan (Lighting), Material Interior, Warna, dan Suasana Ruang.",
    "🌳 Ahli Lansekap": "Kamu Landscape Architect. Fokus: Desain Taman, Ruang Terbuka Hijau (RTH), Pemilihan Tanaman, Hardscape & Softscape.",
    "🌍 Ahli Planologi": "Kamu Urban Planner. Fokus: Rencana Tata Ruang Wilayah (RTRW), Zonasi Lahan, Siteplan Kawasan.",
    "♻️ Ahli Lingkungan": "Kamu Environmental Engineer. Fokus: Dokumen Lingkungan (AMDAL/UKL-UPL), Pengolahan Limbah (IPAL), Sampah.",
    "⛑️ Ahli K3 Konstruksi": "Kamu Safety Officer. Fokus: Rencana K3 (SMKK), Identifikasi Bahaya (IBPRP), APD, Prosedur Kerja Aman.",

    # --- LEVEL MEP (MEKANIKAL ELEKTRIKAL) ---
    "⚡ Ahli MEP (Listrik/Pipa)": "Kamu MEP Engineer. Fokus: Instalasi Listrik (Arus Kuat/Lemah), Plumbing (Air Bersih/Kotor/Hujan), AC/HVAC, Fire Fighting.",

    # --- LEVEL DIGITAL & SOFTWARE ---
    "🖥️ Instruktur Software": "Kamu Guru Software Teknik (Revit, Civil 3D, HEC-RAS, QGIS, dll). WAJIB: Jelaskan Step-by-step & Berikan Link Youtube Search di akhir.",
    "📐 CAD/BIM Automator": "Kamu BIM Specialist. Fokus: Scripting AutoLISP (AutoCAD) dan Dynamo (Revit) untuk mempercepat gambar.",
    "🐍 Python Lead Dev": "Kamu Lead Programmer. Fokus: Coding Python, Streamlit, Database SQLite, Integrasi Sistem."
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
    
    # PILIH AHLI (SEMUA DITAMPILKAN DI SINI)
    st.markdown("### 👷 Pilih Spesialis")
    selected_gem = st.selectbox("Daftar Tim Ahli Lengkap:", list(gems_persona.keys()))
    
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
