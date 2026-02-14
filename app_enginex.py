import streamlit as st
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json
from PIL import Image
import PyPDF2
import io
import docx
import zipfile
from pptx import Presentation
import re
import time

# ==========================================
# 0. IMPORT MODUL PENDUKUNG (WAJIB ADA)
# ==========================================
# Pastikan 3 file ini (backend_enginex.py, persona.py, export_enginex.py)
# berada di folder yang sama dengan app_enginex.py
try:
    from backend_enginex import EnginexBackend
    from persona import gems_persona, get_persona_list, get_system_instruction
    from export_enginex import EnginexExporter
    from streamlit_folium import st_folium
except ImportError as e:
    st.error(f"❌ CRITICAL ERROR: File modul pendukung tidak ditemukan! \nDetail Error: {e}")
    st.warning("Pastikan Anda sudah mengupload file: backend_enginex.py, persona.py, dan export_enginex.py")
    st.stop()

# ==========================================
# 1. KONFIGURASI HALAMAN & CSS
# ==========================================
st.set_page_config(
    page_title="ENGINEX Ultimate: AI Consultant",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS Custom untuk Tampilan Profesional
st.markdown("""
<style>
    /* Main Header Style */
    .main-header {
        font-size: 2.5rem;
        font-weight: 800;
        color: #0F172A; /* Slate 900 */
        margin-bottom: 0.5rem;
        border-bottom: 4px solid #3B82F6; /* Blue 500 */
        padding-bottom: 10px;
    }
    
    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #F8FAFC;
        border-right: 1px solid #E2E8F0;
    }
    
    /* Tombol Download di Sidebar */
    .stDownloadButton button {
        width: 100%;
        background-color: #ffffff;
        color: #0F172A;
        border: 1px solid #CBD5E1;
        font-weight: 600;
        border-radius: 6px;
        margin-bottom: 8px;
        transition: all 0.2s;
        text-align: left;
        padding-left: 15px;
    }
    .stDownloadButton button:hover {
        background-color: #EFF6FF;
        border-color: #3B82F6;
        color: #1D4ED8;
        transform: translateX(2px);
    }
    
    /* Auto Pilot Notification Box */
    .auto-pilot-box {
        background-color: #ECFDF5;
        border-left: 5px solid #10B981;
        padding: 15px;
        border-radius: 5px;
        color: #064E3B;
        font-weight: bold;
        margin-bottom: 15px;
        font-size: 0.9rem;
    }
    
    /* Styling Container Grafik */
    .plot-container {
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 10px;
        background: white;
        margin-top: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. INISIALISASI SESSION STATE
# ==========================================
if 'processed_files' not in st.session_state:
    st.session_state.processed_files = set()

if 'current_expert_active' not in st.session_state:
    st.session_state.current_expert_active = "👑 The GEMS Grandmaster"

if 'backend' not in st.session_state:
    st.session_state.backend = EnginexBackend()

# State khusus untuk menyimpan teks analisis terakhir (agar tombol download tetap muncul saat refresh)
if 'last_analysis_content' not in st.session_state:
    st.session_state.last_analysis_content = ""

db = st.session_state.backend

# ==========================================
# 3. FUNGSI UTILITAS (HELPER FUNCTIONS)
# ==========================================

def execute_generated_code(code_str):
    """
    Safe Sandbox untuk mengeksekusi kode Python (Matplotlib) yang digenerate AI.
    """
    try:
        # Definisikan variabel lokal yang boleh diakses AI
        local_vars = {
            "pd": pd,
            "np": np,
            "plt": plt,
            "st": st
        }
        
        # Bersihkan plot sebelumnya agar tidak menumpuk
        plt.clf()
        
        # Eksekusi string kode
        exec(code_str, {}, local_vars)
        return True
    except Exception as e:
        st.error(f"⚠️ Gagal Render Grafik: {str(e)}")
        return False

def extract_dataframe_from_markdown(text):
    """
    Mencoba mendeteksi tabel markdown dalam teks dan mengubahnya jadi DataFrame Pandas.
    Berguna untuk fitur 'Export Excel'.
    """
    try:
        lines = text.split('\n')
        data = []
        headers = []
        
        for line in lines:
            line = line.strip()
            # Cek format baris tabel markdown: | col1 | col2 |
            if line.startswith('|') and line.endswith('|'):
                # Abaikan baris pemisah header (---|---|---)
                if '---' in line:
                    continue
                
                # Pecah string berdasarkan karakter pipe '|'
                cells = [c.strip() for c in line.split('|')[1:-1]]
                
                if not headers:
                    headers = cells
                else:
                    data.append(cells)
                    
        if headers and data:
            return pd.DataFrame(data, columns=headers)
        return None
    except:
        return None

def process_uploaded_file(uploaded_file):
    """
    Membaca konten file berdasarkan ekstensinya.
    Mendukung: Image, PDF, Docx, Excel, PPT, Python, dan GeoJSON/KML.
    """
    if uploaded_file is None: return None, None
    
    file_type = uploaded_file.name.split('.')[-1].lower()
    
    try:
        # --- IMAGE ---
        if file_type in ['png', 'jpg', 'jpeg']:
            return "image", Image.open(uploaded_file)
            
        # --- PDF ---
        elif file_type == 'pdf':
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            text = ""
            for page in pdf_reader.pages:
                extracted = page.extract_text()
                if extracted: text += extracted + "\n"
            return "text", text
            
        # --- DOCX ---
        elif file_type == 'docx':
            doc = docx.Document(uploaded_file)
            text = "\n".join([para.text for para in doc.paragraphs])
            return "text", text
            
        # --- EXCEL ---
        elif file_type in ['xlsx', 'xls']:
            df = pd.read_excel(uploaded_file)
            # Ambil 50 baris pertama saja untuk konteks (hemat token)
            return "text", f"[PREVIEW DATA EXCEL]\n{df.head(50).to_string()}"
            
        # --- POWERPOINT ---
        elif file_type == 'pptx':
            prs = Presentation(uploaded_file)
            text = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text.append(shape.text)
            return "text", "\n".join(text)
            
        # --- PYTHON SCRIPT ---
        elif file_type == 'py':
            return "text", uploaded_file.getvalue().decode("utf-8")
            
        # --- GEOSPATIAL (GEOJSON/KML/GPX) ---
        elif file_type in ['geojson', 'kml', 'gpx']:
            return "geo", uploaded_file.getvalue().decode("utf-8")
            
        # --- KMZ (Zipped KML) ---
        elif file_type == 'kmz':
            with zipfile.ZipFile(uploaded_file, "r") as z:
                # Cari file .kml di dalam zip
                kml_filename = [n for n in z.namelist() if n.endswith(".kml")][0]
                with z.open(kml_filename) as f:
                    return "geo", f.read().decode("utf-8")
        else:
            return "error", "Format file tidak didukung."
            
    except Exception as e:
        return "error", str(e)

# ==========================================
# 4. SIDEBAR INPUT & SETTINGS
# ==========================================
with st.sidebar:
    st.title("🏗️ ENGINEX ULTIMATE")
    st.caption("v11.5 | Integrated AI Consultant")
    st.markdown("---")
    
    # --- A. API KEY CONFIGURATION ---
    api_key_input = st.text_input("🔑 API Key Google:", type="password", help="Masukkan API Key Gemini Anda di sini.")
    
    # Prioritas: Input Manual > Stored Secrets
    if api_key_input:
        clean_api_key = api_key_input.strip()
    else:
        clean_api_key = st.secrets.get("GOOGLE_API_KEY", "")
    
    # Validasi API Key
    if not clean_api_key:
        st.warning("⚠️ Masukkan API Key untuk memulai.")
        st.stop()
        
    try:
        genai.configure(api_key=clean_api_key)
    except Exception as e:
        st.error(f"API Key Invalid: {e}")
        st.stop()

    # --- B. PROJECT MANAGEMENT ---
    with st.expander("📁 Manajemen Proyek", expanded=False):
        existing_projects = db.daftar_proyek()
        mode_proyek = st.radio("Mode Proyek:", ["Buka Proyek Lama", "Buat Proyek Baru"])
        
        if mode_proyek == "Buat Proyek Baru":
            nama_proyek = st.text_input("Nama Proyek:", "DED Irigasi 2026")
        else:
            if existing_projects:
                nama_proyek = st.selectbox("Pilih Proyek:", existing_projects)
            else:
                st.info("Belum ada riwayat proyek.")
                nama_proyek = "Proyek Baru"
        
        st.markdown("---")
        
        # Pengaturan Ahli & Auto Pilot
        use_auto_pilot = st.checkbox("🤖 Mode Auto-Pilot", value=True, help="AI otomatis memilih ahli yang relevan.")
        manual_expert = st.selectbox(
            "Pilih Ahli (Manual):", 
            get_persona_list(), 
            disabled=use_auto_pilot,
            index=0
        )

    # --- C. MODEL SETTINGS ---
    # List model manual untuk mempermudah
    available_models = ["models/gemini-1.5-pro", "models/gemini-1.5-flash", "models/gemini-1.0-pro"]
    selected_model_name = st.selectbox("🧠 Model AI:", available_models, index=1) # Default Flash

    # --- D. FILE UPLOAD ---
    st.markdown("### 📎 Upload Dokumen")
    uploaded_files = st.file_uploader(
        "Upload PDF/Excel/Gambar/Peta:", 
        type=None, 
        accept_multiple_files=True, 
        label_visibility="collapsed"
    )
    
    # Tombol Reset
    if st.button("🧹 Hapus Chat & Reset"):
        db.clear_chat(nama_proyek, st.session_state.current_expert_active)
        st.session_state.last_analysis_content = "" # Bersihkan cache export
        st.rerun()

    st.markdown("---")
    
    # ==========================================
    # 5. SIDEBAR EXPORT CENTER (FITUR UTAMA)
    # ==========================================
    st.header("📥 Download Center")
    
    # Placeholder: Area kosong yang akan diisi tombol download nanti
    export_placeholder = st.empty()
    
    def render_export_buttons(text_content, project_name):
        """
        Fungsi untuk mengisi Sidebar dengan tombol download 
        berdasarkan hasil analisis terakhir.
        """
        if not text_content:
            export_placeholder.info("Belum ada hasil analisis untuk di-download.")
            return

        with export_placeholder.container():
            # 1. DOWNLOAD LAPORAN WORD
            docx_data = EnginexExporter.create_pupr_word(text_content, project_name)
            st.download_button(
                label="📄 Laporan Resmi (.docx)", 
                data=docx_data, 
                file_name=f"{project_name}_Report.docx", 
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            
            # 2. DOWNLOAD DATA EXCEL (Jika ada tabel)
            df_table = extract_dataframe_from_markdown(text_content)
            if df_table is not None:
                xlsx_data = EnginexExporter.create_pupr_excel(df_table)
                st.download_button(
                    label="📊 Data Tabel (.xlsx)", 
                    data=xlsx_data, 
                    file_name=f"{project_name}_Data.xlsx", 
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
                # 3. DOWNLOAD CIVIL 3D POINTS (Jika ada koordinat X, Y/N, E)
                cols_lower = [c.lower() for c in df_table.columns]
                if any('x' in c for c in cols_lower) and any('y' in c for c in cols_lower):
                    csv_data = EnginexExporter.export_to_civil3d_csv(df_table)
                    st.download_button(
                        label="🏗️ Civil 3D Points (.csv)", 
                        data=csv_data, 
                        file_name=f"{project_name}_Points.csv", 
                        mime="text/csv"
                    )
            
            # 4. DOWNLOAD PRESENTASI PPT
            ppt_data = EnginexExporter.create_pupr_pptx(text_content, project_name)
            st.download_button(
                label="📢 Slide Presentasi (.pptx)", 
                data=ppt_data, 
                file_name=f"{project_name}_Slide.pptx", 
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
            )

# ==========================================
# 6. LOGIKA UTAMA CHAT (MAIN CHAT AREA)
# ==========================================

# Judul Halaman Utama
st.markdown(f'<div class="main-header">{nama_proyek}</div>', unsafe_allow_html=True)

# Tentukan Ahli Aktif (Auto vs Manual)
if use_auto_pilot:
    active_expert = st.session_state.current_expert_active
else:
    active_expert = manual_expert
    st.session_state.current_expert_active = manual_expert

st.caption(f"Status: **Connected** | Ahli Aktif: **{active_expert}**")

# --- LOAD HISTORY DARI DATABASE ---
history_data = db.get_chat_history(nama_proyek, active_expert)

# Cek History untuk update tombol export saat halaman direfresh
if history_data:
    # Cari pesan terakhir dari assistant
    last_assistant_msg = None
    for msg in reversed(history_data):
        if msg['role'] == 'assistant':
            last_assistant_msg = msg['content']
            break
    
    if last_assistant_msg:
        st.session_state.last_analysis_content = last_assistant_msg

# Render Pesan Chat
for chat in history_data:
    with st.chat_message(chat['role']):
        st.markdown(chat['content'])
        
        # Jika ada kode Python plot di history, render ulang gambarnya
        if chat['role'] == 'assistant' and "```python" in chat['content']:
            code_match = re.search(r"```python(.*?)```", chat['content'], re.DOTALL)
            if code_match and "plt." in code_match.group(1):
                with st.expander("📊 Lihat Grafik Tersimpan"):
                    execute_generated_code(code_match.group(1))
                    st.pyplot(plt.gcf())

# --- UPDATE SIDEBAR BUTTONS (INITIAL LOAD) ---
# Panggil fungsi ini agar tombol muncul walau user belum mengetik apa-apa (jika ada history)
render_export_buttons(st.session_state.last_analysis_content, nama_proyek)

# --- USER INPUT AREA ---
user_input = st.chat_input(f"Konsultasi dengan {active_expert}...")

if user_input:
    # 1. AUTO-PILOT ROUTING (AI Menentukan Ahli)
    target_expert = active_expert
    
    if use_auto_pilot:
        try:
            # Menggunakan model ringan (Flash) untuk routing cepat
            router_model = genai.GenerativeModel("models/gemini-1.5-flash")
            routing_prompt = f"""
            Tugas: Pilih SATU nama ahli dari daftar berikut yang paling tepat untuk menjawab pertanyaan user.
            Daftar Ahli: {list(gems_persona.keys())}
            Pertanyaan User: "{user_input}"
            Output: HANYA TULIS NAMA AHLI. Jangan ada kata lain.
            """
            resp = router_model.generate_content(routing_prompt)
            suggested_expert = resp.text.strip()
            
            # Validasi nama ahli
            if suggested_expert in gems_persona:
                target_expert = suggested_expert
                st.session_state.current_expert_active = target_expert
        except Exception:
            # Jika routing gagal, tetap gunakan ahli saat ini
            pass
    
    # Notifikasi jika ahli berubah
    if target_expert != active_expert:
        st.markdown(f'<div class="auto-pilot-box">🤖 Auto-Pilot mengalihkan konsultasi ke: {target_expert}</div>', unsafe_allow_html=True)
        active_expert = target_expert

    # 2. SIMPAN CHAT USER
    db.simpan_chat(nama_proyek, active_expert, "user", user_input)
    with st.chat_message("user"):
        st.markdown(user_input)

    # 3. PERSIAPAN KONTEN (TEXT + FILES)
    content_payload = [user_input]
    
    if uploaded_files:
        for f in uploaded_files:
            # Cek apakah file sudah diproses sebelumnya dalam sesi ini (Cache sederhana)
            if f.name not in st.session_state.processed_files:
                ftype, fcontent = process_uploaded_file(f)
                
                if ftype == "image":
                    with st.chat_message("user"):
                        st.image(f, width=250, caption=f.name)
                    content_payload.append(fcontent) # Image Object
                    
                elif ftype == "geo":
                    with st.chat_message("user"): 
                        st.caption(f"🌍 Memuat Peta: {f.name}")
                        # Render Peta Folium
                        m = EnginexExporter.render_geospatial_map(fcontent, f.name.split('.')[-1])
                        if m: st_folium(m, height=300)
                    content_payload.append(f"\n[DATA GEOSPASIAL DIUPLOAD: {f.name}]\nKutipan Data: {fcontent[:2000]}...\n")
                    
                elif ftype == "text":
                    content_payload.append(f"\n[FILE DOKUMEN: {f.name}]\nIsi:\n{fcontent}\n")
                    
                # Tandai file sudah diproses
                st.session_state.processed_files.add(f.name)

    # 4. GENERATE AI RESPONSE
    with st.chat_message("assistant"):
        with st.spinner(f"{active_expert} sedang menganalisis..."):
            try:
                # Ambil instruksi dasar (System Prompt)
                base_instruction = get_system_instruction(active_expert)
                
                # Tambahkan instruksi visualisasi jika ahlinya adalah tipe Engineer
                if "Code" not in active_expert and "Visionary" not in active_expert:
                    base_instruction += """
                    \n[INSTRUKSI VISUALISASI]:
                    Jika user meminta data yang perlu grafik, BUAT KODE PYTHON (matplotlib).
                    Pastikan kode diakhiri dengan 'st.pyplot(plt.gcf())'.
                    Gunakan style 'ggplot'.
                    """

                # Konfigurasi Model
                model = genai.GenerativeModel(
                    model_name=selected_model_name,
                    system_instruction=base_instruction
                )
                
                # Bangun History Chat (Ambil 5 pesan terakhir untuk konteks)
                history_objs = []
                recent_chats = db.get_chat_history(nama_proyek, active_expert)[-5:]
                for h in recent_chats:
                    if h['content'] != user_input: # Jangan masukkan prompt terakhir double
                        role_str = "user" if h['role'] == "user" else "model"
                        history_objs.append({"role": role_str, "parts": [h['content']]})
                
                # Mulai Sesi Chat
                chat_session = model.start_chat(history=history_objs)
                response_stream = chat_session.send_message(content_payload, stream=True)
                
                # Streaming Output
                full_response_text = ""
                response_placeholder = st.empty()
                
                for chunk in response_stream:
                    if chunk.text:
                        full_response_text += chunk.text
                        response_placeholder.markdown(full_response_text + "▌")
                
                # Tampilkan hasil final
                response_placeholder.markdown(full_response_text)
                
                # Simpan ke Database
                db.simpan_chat(nama_proyek, active_expert, "assistant", full_response_text)
                
                # 5. EKSEKUSI KODE PLOTTING (JIKA ADA)
                code_blocks = re.findall(r"```python(.*?)```", full_response_text, re.DOTALL)
                for code in code_blocks:
                    if "plt." in code or "matplotlib" in code:
                        st.markdown("### 📉 Grafik Analisis")
                        with st.container():
                            execute_generated_code(code)
                            st.pyplot(plt.gcf())

                # 6. UPDATE STATE & SIDEBAR BUTTONS (REAL-TIME)
                st.session_state.last_analysis_content = full_response_text
                render_export_buttons(full_response_text, nama_proyek)
                
            except Exception as e:
                st.error(f"❌ Terjadi Kesalahan: {str(e)}")
                st.info("Saran: Coba refresh halaman atau kurangi jumlah file yang diupload.")

# Footer Copyright
st.markdown("---")
st.caption("© 2026 ENGINEX Ultimate System | Powered by Gemini AI")
