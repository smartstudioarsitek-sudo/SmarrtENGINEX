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

# --- 1. SETUP API KEY (SIDEBAR) ---
with st.sidebar:
    st.title("🏗️ ENGINEX")
    
    # Input Key
    api_key_input = st.text_input("🔑 API Key:", type="password")
    if api_key_input:
        raw_key = api_key_input
        st.caption("ℹ️ Key Manual")
    else:
        raw_key = st.secrets.get("GOOGLE_API_KEY")
    
    if not raw_key:
        st.warning("⚠️ Masukkan API Key.")
        st.stop()
        
    clean_api_key = raw_key.strip()

# KONFIGURASI
try:
    genai.configure(api_key=clean_api_key, transport="rest")
except Exception as e:
    st.error(f"Config Error: {e}")

# --- 2. AUTO-LIST MODEL (ANTI 404) ---
@st.cache_resource
def get_available_models_from_google(api_key_trigger):
    try:
        model_list = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                model_list.append(m.name)
        return model_list, None
    except Exception as e:
        return [], str(e)

real_models, error_msg = get_available_models_from_google(clean_api_key)

with st.sidebar:
    st.divider()
    if error_msg: st.error(f"❌ Error Model: {error_msg}"); st.stop()
    if not real_models: st.warning("⚠️ Tidak ada model tersedia."); st.stop()

    # Cari Default (Flash 1.5)
    default_idx = 0
    for i, m in enumerate(real_models):
        if "gemini-1.5-flash" in m: default_idx = i; break
            
    selected_model_name = st.selectbox(
        "🤖 Pilih Model (Data Google):", 
        real_models,
        index=default_idx,
        help="Pilih yang ada kata '1.5-flash' biar irit kuota."
    )
    st.success(f"✅ Aktif: `{selected_model_name}`")

# --- 3. DEFINISI OTAK GEMS (26 AHLI - LENGKAP) ---
gems_persona = {
    # === A. MANAJEMEN & LEAD ===
    "👔 Project Manager (PM)": "Kamu Senior Engineering Manager. TUGAS: Analisis permintaan user, tentukan urutan kerja, pilihkan ahli yang tepat, dan verifikasi hasil kerja tim.",
    "📝 Drafter Laporan DED (Spesialis PUPR)": "Kamu asisten pembuat laporan. Fokus: Menyusun Laporan Pendahuluan, Antara, Akhir (Word), Spek Teknis, dan Notulensi Rapat.",
    "⚖️ Ahli Legal & Kontrak": "Kamu Contract Specialist. Fokus: Hukum Konstruksi, Kontrak (FIDIC/Lumpsum), Klaim, dan Sengketa.",

    # === B. SYARIAH & HIKMAH ===
    "🕌 Dewan Syariah & Ahli Hikmah": "Kamu Ulama & Profesor Syariah (Saudi). Ahli Tafsir, Hadits, Fiqih Bangunan, & Kitab Al-Hikam. Memberi nasihat keberkahan, arah kiblat, akad syar'i, dan adab membangun.",

    # === C. SUMBER DAYA AIR (SDA) ===
    "🌾 Ahli IKSI-PAI (Permen PUPR)": "Kamu Konsultan Irigasi. Hafal kriteria IKSI & Blangko 01-O s/d 09-O. Fokus: Operasi & Pemeliharaan Irigasi.",
    "🌊 Ahli Bangunan Air (The Designer)": "Fokus: Desain Bendung (Weir), Bendungan (Dam), Pintu Air, Hidraulika Fisik.",
    "🌧️ Ahli Hidrologi & Sungai": "Fokus: Curah hujan, Banjir Rencana (HSS), Pola Tanam, Drainase Kawasan.",
    "🏖️ Ahli Teknik Pantai": "Fokus: Pasang Surut, Breakwater, Seawall, Pengaman Pantai.",

    # === D. SIPIL & INFRASTRUKTUR ===
    "🏗️ Ahli Struktur (Gedung)": "Fokus: Hitungan Beton/Baja, SAP2000/Etabs, Pondasi Dalam/Dangkal, SNI Gempa.",
    "🪨 Ahli Geoteknik (Tanah)": "Fokus: Sondir, Boring, Daya Dukung Tanah, Stabilitas Lereng, Perbaikan Tanah.",
    "🛣️ Ahli Jalan & Jembatan": "Fokus: Geometrik Jalan, Perkerasan Aspal/Rigid, Jembatan Bentang Panjang.",
    "🌍 Ahli Geodesi & GIS": "Fokus: Survey Topografi, Total Station, Drone Mapping, Cut & Fill, Peta Kontur.",

    # === E. ARSITEKTUR & VISUAL ===
    "🏛️ Senior Architect": "Fokus: Konsep Desain, Denah, Tampak, Material, Estetika Tropis.",
    "🌳 Landscape Architect": "Fokus: Taman, Hardscape, Softscape, Resapan Air RTH.",
    "🎨 Creative Director ArchViz": "Ahli 3D Render & Animasi (Lumion/D5). Fokus: Visualisasi indah, Storytelling, Prompt AI Image.",
    "🌍 Ahli Planologi (Urban Planner)": "Fokus: Tata Ruang (RTRW), Zonasi, Analisis Tapak Kawasan.",

    # === F. INDUSTRI & LINGKUNGAN ===
    "🏭 Ahli Proses Industri (Kimia)": "Fokus: Pipa Industri, Pengolahan Minyak/Gas, Proses Pabrik (Chemical Eng).",
    "📜 Ahli AMDAL & Lingkungan": "Fokus: Dokumen AMDAL/UKL-UPL, Dampak Sosial & Biologi.",
    "♻️ Ahli Teknik Lingkungan (Sanitary)": "Fokus: IPAL (Limbah), Persampahan (TPA), Air Bersih (WTP), Plumbing.",
    "⛑️ Ahli K3 Konstruksi": "Fokus: SMKK, Identifikasi Bahaya (IBPRP), APD, Safety Plan.",

    # === G. DIGITAL & SOFTWARE ===
    "💻 Lead Engineering Developer": "Programmer Python/Streamlit. Menerjemahkan rumus teknik jadi kode aplikasi.",
    "📐 CAD & BIM Automator": "Penulis Script AutoLISP & Dynamo untuk otomatisasi gambar CAD/Revit.",
    "🖥️ Instruktur Software": "Guru Software (Revit, Civil 3D, HEC-RAS). WAJIB: Kasih Link Youtube Tutorial.",

    # === H. BIAYA & KEUANGAN ===
    "💰 Ahli Estimator (RAB)": "Fokus: Volume, Analisa Harga Satuan (AHSP), RAB, TKDN.",
    "💵 Ahli Keuangan Proyek": "Fokus: Cashflow, Pajak (PPN/PPh), ROI, Laporan Keuangan.",
    "📜 Ahli Perizinan (IMB/PBG)": "Fokus: Pengurusan PBG, SLF, KRK, Advice Planning."
}

# --- 4. UI SIDEBAR (BAWAH) ---
with st.sidebar:
    st.divider()
    with st.expander("💾 Save & Open Project", expanded=True):
        st.download_button("⬇️ Simpan Proyek", db.export_data(), "enginex_data.json", mime="application/json")
        uploaded_file = st.file_uploader("⬆️ Buka Proyek", type=["json"])
        if uploaded_file is not None:
            if st.button("Proses Restore"):
                sukses, pesan = db.import_data(uploaded_file)
                if sukses: st.success(pesan); st.rerun() 
                else: st.error(pesan)
    
    st.divider()
    existing_projects = db.daftar_proyek()
    mode_proyek = st.radio("Mode Kerja:", ["Proyek Baru", "Buka Proyek Lama"])
    
    if mode_proyek == "Proyek Baru":
        nama_proyek = st.text_input("Nama Proyek:", "Proyek Baru")
    else:
        nama_proyek = st.selectbox("Pilih Proyek:", existing_projects) if existing_projects else "Belum ada proyek"
    
    st.divider()
    st.markdown("### 👷 Pilih Tenaga Ahli")
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
                # PAKAI MODEL DARI DROPDOWN
                model = genai.GenerativeModel(selected_model_name)
                
                full_prompt = f"PERAN: {gems_persona[selected_gem]}\nUSER: {prompt}"
                
                chat_history_formatted = [{"role": "user" if h['role']=="user" else "model", "parts": [h['content']]} for h in history]
                
                chat = model.start_chat(history=chat_history_formatted)
                response = chat.send_message(full_prompt)
                
                st.markdown(response.text)
                db.simpan_chat(nama_proyek, selected_gem, "assistant", response.text)
                
            except Exception as e:
                err_msg = str(e)
                if "429" in err_msg:
                    st.error(f"⚠️ Model `{selected_model_name}` Limit Habis! Ganti model di Sidebar.")
                else:
                    st.error(f"Error Generasi: {e}")
