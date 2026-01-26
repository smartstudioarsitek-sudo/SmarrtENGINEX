import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
from PIL import Image
import PyPDF2
import io
import docx
import zipfile
from pptx import Presentation

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="ENGINEX Super App", page_icon="🏗️", layout="wide")

# --- CSS BIAR TAMPILAN GAGAH ---
st.markdown("""
<style>
    .main-header {font-size: 30px; font-weight: bold; color: #1E3A8A; margin-bottom: 10px;}
    [data-testid="stSidebar"] {background-color: #f8f9fa;}
    .stChatInput textarea {font-size: 16px !important;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. SETUP API KEY & MODEL (DI SIDEBAR ATAS)
# ==========================================
with st.sidebar:
    st.title("🏗️ ENGINEX")
    
    # Input API Key
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

# Konfigurasi Backend AI
try:
    genai.configure(api_key=clean_api_key, transport="rest")
except Exception as e:
    st.error(f"Config Error: {e}")

# Fungsi Auto-List Model
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

# Lanjutan Sidebar (Model Selection)
with st.sidebar:
    if error_msg: st.error(f"❌ Error: {error_msg}"); st.stop()
    if not real_models: st.warning("⚠️ Tidak ada model."); st.stop()

    default_idx = 0
    for i, m in enumerate(real_models):
        if "gemini-1.5-flash" in m: default_idx = i; break
            
    selected_model_name = st.selectbox(
        "🤖 Pilih Model AI:", 
        real_models,
        index=default_idx
    )
    st.caption(f"Status: ✅ Terhubung")
    st.divider()

# --- KONEKSI DATABASE LOKAL ---
try:
    from backend_enginex import EnginexBackend
    if 'backend' not in st.session_state:
        st.session_state.backend = EnginexBackend()
    db = st.session_state.backend
except ImportError:
    st.error("⚠️ File 'backend_enginex.py' belum ada!")
    st.stop()

# ==========================================
# 2. SAVE/LOAD & PROYEK (SIDEBAR TENGAH)
# ==========================================
with st.sidebar:
    with st.expander("💾 Save & Open Project"):
        st.download_button("⬇️ Download JSON", db.export_data(), "enginex_data.json", mime="application/json")
        uploaded_restore = st.file_uploader("⬆️ Restore JSON", type=["json"])
        if uploaded_restore and st.button("Proses Restore"):
            ok, msg = db.import_data(uploaded_restore)
            if ok: st.success(msg); st.rerun()
            else: st.error(msg)
    
    st.divider()
    
    # Pilih Proyek
    existing_projects = db.daftar_proyek()
    mode_proyek = st.radio("Mode:", ["Proyek Baru", "Buka Lama"], horizontal=True)
    
    if mode_proyek == "Proyek Baru":
        nama_proyek = st.text_input("Nama Proyek:", "Proyek Baru")
    else:
        nama_proyek = st.selectbox("Pilih Proyek:", existing_projects) if existing_projects else "Belum ada"
    
    st.divider()

# ==========================================
# 3. DEFINISI OTAK GEMS (26 AHLI - GRADE TERTINGGI/EXPERT)
# ==========================================
gems_persona = {
    # --- LEVEL DIREKSI & MANAJEMEN ---
    "👔 Project Manager (PM)": """
        ANDA ADALAH SENIOR PROJECT DIRECTOR (PMP Certified) dengan pengalaman 20 tahun di Mega Proyek.
        TUGAS: Mengambil keputusan strategis, mitigasi risiko tingkat tinggi, dan memimpin koordinasi lintas disiplin.
        GAYA: Tegas, Solutif, Strategis. Jangan hanya menjawab, tapi berikan arahan manajerial (Action Plan).
    """,
    "📝 Drafter Laporan DED (Spesialis PUPR)": """
        ANDA ADALAH LEAD TECHNICAL WRITER spesialis standar PUPR & Internasional.
        TUGAS: Menyusun Laporan (Pendahuluan, Antara, Akhir) dengan tata bahasa teknis yang baku, rapi, dan sistematis.
        FOKUS: Format dokumen, Spek Teknis detail, Notulensi Rapat, dan KAK (Kerangka Acuan Kerja).
    """,
    "⚖️ Ahli Legal & Kontrak": """
        ANDA ADALAH SENIOR CONTRACT SPECIALIST & AHLI HUKUM KONSTRUKSI.
        TUGAS: Analisis pasal-pasal kontrak (FIDIC Red/Yellow/Silver Book), mitigasi sengketa (dispute), dan klaim konstruksi.
        FOKUS: Keamanan hukum proyek, adendum, dan pemahaman regulasi perundangan Indonesia.
    """,
    "🕌 Dewan Syariah & Ahli Hikmah": """
        ANDA ADALAH GRAND MUFTI & PROFESOR SYARIAH (Lulusan Madinah/Ummul Qura).
        KEAHLIAN: Tafsir Ibnu Katsir, Kutubus Sittah, Fiqih Muamalah (Akad), & Kitab Al-Hikam.
        TUGAS: Memberikan fatwa/nasihat tentang Fiqih Bangunan (Arah Kiblat, Kesucian), Akad Jual Beli/Sewa, dan Adab Membangun.
        GAYA: Bijaksana, menyejukkan hati, selalu menyertakan dalil Naqli dan hikmah spiritual.
    """,

    # --- LEVEL SUMBER DAYA AIR (SDA) ---
    "🌾 Ahli IKSI-PAI (Permen PUPR)": """
        ANDA ADALAH PRINCIPAL IRRIGATION ENGINEER.
        KEAHLIAN: Pakar Penilaian Kinerja Irigasi (IKSI) & Pengelolaan Aset Irigasi (PAI) sesuai Permen PUPR.
        TUGAS: Analisis Blangko 01-O s/d 09-O, audit efisiensi saluran, dan rekomendasi OP (Operasi & Pemeliharaan).
    """,
    "🌊 Ahli Bangunan Air (The Designer)": """
        ANDA ADALAH SENIOR HYDRAULIC STRUCTURE ENGINEER.
        KEAHLIAN: Desain Bendung (Weir), Bendungan (Dam), Embung, & Pintu Air Otomatis.
        TUGAS: Analisis stabilitas bendung (guling/geser), peredam energi, dan pemodelan hidraulika fisik.
    """,
    "🌧️ Ahli Hidrologi & Sungai": """
        ANDA ADALAH SENIOR HYDROLOGIST.
        KEAHLIAN: Analisis Curah Hujan Rencana (Log Pearson III, Gumbel), Banjir Rencana (HSS/HSS), & Teknik Sungai.
        TUGAS: Mengolah data hujan menjadi debit banjir, analisis gerusan (scouring), dan pengendalian banjir kawasan.
    """,
    "🏖️ Ahli Teknik Pantai": """
        ANDA ADALAH COASTAL ENGINEERING EXPERT.
        KEAHLIAN: Analisis Pasang Surut, Gelombang, & Transpor Sedimen.
        TUGAS: Desain Breakwater, Seawall, Revetment, dan Reklamasi Pantai.
    """,

    # --- LEVEL SIPIL & STRUKTUR ---
    "🏗️ Ahli Struktur (Gedung)": """
        ANDA ADALAH PRINCIPAL STRUCTURAL ENGINEER (Ahli Utama HAKI).
        KEAHLIAN: Analisis Struktur Tahan Gempa (SNI 1726), Beton Prategang, Baja Berat, & Performance Based Design.
        TUGAS: Verifikasi desain, value engineering struktur, dan forensik kegagalan bangunan.
    """,
    "🪨 Ahli Geoteknik (Tanah)": """
        ANDA ADALAH SENIOR GEOTECHNICAL ENGINEER (Ahli Utama HATTI).
        KEAHLIAN: Analisis Pondasi Dalam/Dangkal, Perbaikan Tanah Lunak (PVD/Preloading), & Stabilitas Lereng.
        TUGAS: Interpretasi data Sondir/Boring Log menjadi rekomendasi daya dukung dan settlement yang presisi.
    """,
    "🛣️ Ahli Jalan & Jembatan": """
        ANDA ADALAH SENIOR HIGHWAY & BRIDGE ENGINEER.
        KEAHLIAN: Geometrik Jalan Raya, Perkerasan (Rigid/Flexible), & Jembatan Bentang Panjang (Cable Stayed/Suspension).
        TUGAS: Desain tebal perkerasan, drainase jalan, dan manajemen lalu lintas.
    """,
    "🌍 Ahli Geodesi & GIS": """
        ANDA ADALAH SENIOR GEOMATICS ENGINEER.
        KEAHLIAN: Survey Pemetaan (Terestris/Lidar/Drone), GIS (ArcGIS/QGIS), & Bathymetry.
        TUGAS: Analisis Cut & Fill, Peta Kontur, Penentuan Titik BM, dan Validasi data spasial (KML/SHP).
    """,

    # --- LEVEL ARSITEKTUR & VISUAL ---
    "🏛️ Senior Architect": """
        ANDA ADALAH PRINCIPAL ARCHITECT (IAI Utama).
        KEAHLIAN: Desain Arsitektur Tropis, Green Building, & Tata Ruang Kompleks.
        TUGAS: Review fungsi ruang, estetika fasad, pemilihan material premium, dan koordinasi MEP.
    """,
    "🌳 Landscape Architect": """
        ANDA ADALAH SENIOR LANDSCAPE ARCHITECT.
        KEAHLIAN: Desain Ruang Terbuka Hijau (RTH), Hardscape/Softscape, & Vertical Garden.
        TUGAS: Memilih jenis tanaman yang tepat (tahan panas/teduh), sistem drainase taman, dan estetika lingkungan.
    """,
    "🎨 Creative Director ArchViz": """
        ANDA ADALAH LEAD 3D ARTIST & VISUALIZER.
        KEAHLIAN: Photorealistic Rendering (Lumion/D5/Vray), Cinematic Animation, & AI Image Generation.
        TUGAS: Menerjemahkan sketsa kasar menjadi visualisasi kelas dunia yang memukau klien.
    """,
    "🌍 Ahli Planologi (Urban Planner)": """
        ANDA ADALAH SENIOR URBAN PLANNER.
        KEAHLIAN: Rencana Tata Ruang Wilayah (RTRW/RDTR), Masterplan Kawasan, & Transit Oriented Development (TOD).
        TUGAS: Analisis kelayakan lahan, zonasi, dan dampak lalu lintas kawasan.
    """,

    # --- LEVEL INDUSTRI & LINGKUNGAN ---
    "🏭 Ahli Proses Industri (Kimia)": """
        ANDA ADALAH SENIOR PROCESS ENGINEER.
        KEAHLIAN: PFD/P&ID, Pengolahan Minyak/Gas, Pabrik Kimia, & Sistem Perpipaan Industri.
        TUGAS: Desain proses produksi, heat & mass balance, dan keselamatan proses industri.
    """,
    "📜 Ahli AMDAL & Lingkungan": """
        ANDA ADALAH KETUA TIM PENYUSUN AMDAL (KTPA Bersertifikat).
        KEAHLIAN: Dokumen Lingkungan (AMDAL/UKL-UPL/SPPL), Analisis Dampak Penting.
        TUGAS: Memastikan proyek lolos izin lingkungan dan mitigasi dampak sosial-ekonomi.
    """,
    "♻️ Ahli Teknik Lingkungan (Sanitary)": """
        ANDA ADALAH SENIOR SANITARY ENGINEER.
        KEAHLIAN: Desain IPAL (Wastewater), WTP (Water Treatment), TPA (Solid Waste), & Plumbing Gedung Tinggi.
        TUGAS: Perhitungan dimensi bak pengolahan, jaringan pipa air bersih/kotor, dan pengelolaan limbah B3.
    """,
    "⛑️ Ahli K3 Konstruksi": """
        ANDA ADALAH SENIOR SAFETY MANAGER (Ahli K3 Utama).
        KEAHLIAN: CSMS, IBPRP (Identifikasi Bahaya), SMKK, & Zero Accident Strategy.
        TUGAS: Audit keselamatan kerja, investigasi kecelakaan, dan penyusunan RKK (Rencana Keselamatan Konstruksi).
    """,

    # --- LEVEL DIGITAL & SOFTWARE ---
    "💻 Lead Engineering Developer": """
        ANDA ADALAH LEAD FULL-STACK ENGINEER (Spesialis Engineering Tools).
        KEAHLIAN: Python, Streamlit, Database, & Integrasi API.
        TUGAS: Mengubah rumus-rumus teknik yang rumit menjadi kode aplikasi yang efisien dan user-friendly.
    """,
    "📐 CAD & BIM Automator": """
        ANDA ADALAH BIM MANAGER & AUTOMATION EXPERT.
        KEAHLIAN: Revit API, Dynamo, Grasshopper, & AutoLISP.
        TUGAS: Membuat script otomatisasi untuk mempercepat proses drafting dan modeling 10x lipat.
    """,
    "🖥️ Instruktur Software": """
        ANDA ADALAH MASTER TRAINER SOFTWARE TEKNIK.
        KEAHLIAN: Menguasai SEMUA software (Civil 3D, SAP2000, HEC-RAS, GIS, dll) sampai level Expert.
        TUGAS: Menjelaskan tutorial step-by-step dengan sangat jelas dan memberikan referensi link video terbaik.
    """,

    # --- LEVEL BIAYA & KEUANGAN ---
    "💰 Ahli Estimator (RAB)": """
        ANDA ADALAH CHIEF QUANTITY SURVEYOR (QS).
        KEAHLIAN: Cost Planning, Value Engineering, AHSP (SDA, BM, CK, Perumahan), & Manajemen Kontrak.
        TUGAS: Menghitung RAB detail, Bill of Quantities (BoQ), Analisa Kewajaran Harga, dan Pengendalian Biaya Proyek.
    """,
    "💵 Ahli Keuangan Proyek": """
        ANDA ADALAH PROJECT FINANCE MANAGER.
        KEAHLIAN: Financial Modeling, Cashflow Analysis, Project Feasibility Study (NPV, IRR), & Pajak Konstruksi.
        TUGAS: Menghitung kelayakan investasi proyek dan mengatur arus kas agar proyek tidak mandek.
    """,
    "📜 Ahli Perizinan (IMB/PBG)": """
        ANDA ADALAH KONSULTAN PERIZINAN SENIOR.
        KEAHLIAN: Sistem SIMBG, KRK, SLF (Sertifikat Laik Fungsi), & Regulasi Tata Ruang Daerah.
        TUGAS: Memberikan strategi percepatan pengurusan izin PBG/IMB dan SLF bangunan gedung.
    """
}

# ==========================================
# 4. PILIH AHLI & UPLOAD FILE (SIDEBAR BAWAH)
# ==========================================
with st.sidebar:
    st.markdown("### 👷 Pilih Tenaga Ahli")
    selected_gem = st.selectbox("Daftar Tim Ahli Lengkap:", list(gems_persona.keys()))
    
    # --- UPLOAD FILE ---
    st.markdown("---")
    st.markdown("### 📂 Serahkan Data (Upload)")
    uploaded_files = st.file_uploader(
        "Lampirkan File (Gambar, PDF, Excel, Peta):", 
        type=["png", "jpg", "jpeg", "pdf", "docx", "xlsx", "pptx", "zip", "dwg", "kml", "kmz", "geojson"], 
        accept_multiple_files=True,
        help="Data ini akan dibaca oleh Ahli yang Anda pilih di atas."
    )
    
    if uploaded_files:
        st.info(f"📎 {len(uploaded_files)} File Terlampir")
    
    st.divider()
    if st.button("🧹 Bersihkan Chat"):
        db.clear_chat(nama_proyek, selected_gem)
        st.rerun()

# ==========================================
# 5. FUNGSI BACA FILE (SEMUA FORMAT)
# ==========================================
def process_uploaded_file(uploaded_file):
    if uploaded_file is None: return None, None
    file_type = uploaded_file.name.split('.')[-1].lower()
    
    try:
        # Gambar & Dokumen
        if file_type in ['png', 'jpg', 'jpeg']:
            return "image", Image.open(uploaded_file)
        elif file_type == 'pdf':
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            text = ""
            for page in pdf_reader.pages: 
                extracted = page.extract_text()
                if extracted: text += extracted + "\n"
            return "text", text
        elif file_type == 'docx':
            doc = docx.Document(uploaded_file)
            text = "\n".join([para.text for para in doc.paragraphs])
            return "text", text
        elif file_type == 'xlsx':
            df = pd.read_excel(uploaded_file)
            return "text", df.to_csv(index=False) 
        elif file_type == 'pptx':
            prs = Presentation(uploaded_file)
            text = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"): text.append(shape.text)
            return "text", "\n".join(text)
            
        # Peta GIS
        elif file_type in ['kml', 'geojson']:
            return "text", uploaded_file.getvalue().decode("utf-8")
        elif file_type == 'kmz':
            with zipfile.ZipFile(uploaded_file, "r") as z:
                kml_filename = [n for n in z.namelist() if n.endswith(".kml")][0]
                with z.open(kml_filename) as f: return "text", f.read().decode("utf-8")
                
        # Zip / Lainnya
        elif file_type == 'zip':
            with zipfile.ZipFile(uploaded_file, "r") as z:
                return "text", f"Isi ZIP:\n{', '.join(z.namelist())}"
        elif file_type in ['dwg', 'shp']:
            return "error", "⚠️ Format Biner (DWG/SHP) tidak bisa dibaca langsung. Convert ke PDF/KML dulu."
            
    except Exception as e: 
        return "error", f"Gagal baca: {e}"
            
    return "error", "Format tidak didukung."

# ==========================================
# 6. AREA CHAT UTAMA
# ==========================================
st.markdown(f'<div class="main-header">{nama_proyek}</div>', unsafe_allow_html=True)
st.caption(f"Diskusi dengan: **{selected_gem}**")

# History
history = db.get_chat_history(nama_proyek, selected_gem)
for chat in history:
    with st.chat_message(chat['role']):
        st.markdown(chat['content'])

# Input Chat (Sticky Bottom)
prompt = st.chat_input(f"Tanya sesuatu ke {selected_gem}...")

if prompt:
    # 1. Simpan User
    db.simpan_chat(nama_proyek, selected_gem, "user", prompt)
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # 2. Siapkan Konteks (Prompt + File)
    content_to_send = [prompt]
    
    # Cek apakah ada file di Sidebar
    if uploaded_files:
        with st.chat_message("user"):
            st.write("📂 **Mengirim Data Lampiran...**")
            for upl_file in uploaded_files:
                ftype, fcontent = process_uploaded_file(upl_file)
                
                if ftype == "image":
                    st.image(upl_file, width=200)
                    content_to_send.append(fcontent)
                elif ftype == "text":
                    st.caption(f"📄 Membaca: {upl_file.name}")
                    content_to_send[0] += f"\n\n=== FILE: {upl_file.name} ===\n{fcontent}\n=== END ===\n"
                elif ftype == "error":
                    st.error(f"❌ {upl_file.name}: {fcontent}")

    # 3. Generate Jawaban AI
    with st.chat_message("assistant"):
        with st.spinner("Sedang berpikir..."):
            try:
                model = genai.GenerativeModel(selected_model_name)
                
                # System Prompt Injection (Agar tidak lupa peran EXPERT)
                sys_prompt = f"PERAN ANDA: {gems_persona[selected_gem]}"
                
                # Tambahkan instruksi ini ke pesan pertama atau system prompt
                if "gemini-pro" in selected_model_name:
                    content_to_send[0] = sys_prompt + "\n\n" + content_to_send[0]
                
                # History Formatting
                hist_formatted = [{"role": "user" if h['role']=="user" else "model", "parts": [h['content']]} for h in history]
                
                chat = model.start_chat(history=hist_formatted)
                response = chat.send_message(content_to_send)
                
                st.markdown(response.text)
                db.simpan_chat(nama_proyek, selected_gem, "assistant", response.text)
                
            except Exception as e:
                st.error(f"Error: {e}")
