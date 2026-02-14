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
# 0. CEK KETERSEDIAAN MODUL PENDUKUNG
# ==========================================
try:
    from backend_enginex import EnginexBackend
    from persona import gems_persona, get_persona_list, get_system_instruction
    from export_enginex import EnginexExporter
    from streamlit_folium import st_folium
except ImportError as e:
    st.error(f"❌ CRITICAL ERROR: File modul pendukung tidak ditemukan! \nDetail: {e}")
    st.warning("Pastikan file: 'backend_enginex.py', 'persona.py', dan 'export_enginex.py' ada di folder yang sama.")
    st.stop()

# ==========================================
# 1. KONFIGURASI HALAMAN & CSS PRO
# ==========================================
st.set_page_config(
    page_title="ENGINEX Ultimate: Future AI Consultant",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS Custom "Gagah" & Professional
st.markdown("""
<style>
    /* Header Utama */
    .main-header {
        font-size: 2.5rem;
        font-weight: 800;
        color: #0F172A;
        margin-bottom: 0.5rem;
        border-bottom: 4px solid #3B82F6;
        padding-bottom: 10px;
    }
    
    /* Sidebar Area */
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
        text-align: left;
        padding-left: 15px;
        transition: all 0.2s;
    }
    .stDownloadButton button:hover {
        background-color: #EFF6FF;
        border-color: #3B82F6;
        color: #1D4ED8;
        transform: translateX(3px);
    }
    
    /* Auto Pilot Notification */
    .auto-pilot-box {
        background-color: #ECFDF5;
        border-left: 5px solid #10B981;
        padding: 15px;
        border-radius: 5px;
        color: #064E3B;
        font-weight: bold;
        margin-bottom: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    /* Plot Container */
    .plot-container {
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 15px;
        background: white;
        margin-top: 15px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
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

# State untuk menyimpan konten analisis terakhir (untuk tombol download sidebar)
if 'last_analysis_content' not in st.session_state:
    st.session_state.last_analysis_content = ""

db = st.session_state.backend

# ==========================================
# 3. FUNGSI UTILITAS (HELPER FUNCTIONS)
# ==========================================

def execute_generated_code(code_str):
    """
    Safe Sandbox: Eksekusi kode Python (Matplotlib) dari AI.
    """
    try:
        # Definisi variabel lokal yang aman
        local_vars = {
            "pd": pd,
            "np": np,
            "plt": plt,
            "st": st
        }
        
        # Bersihkan canvas plot sebelumnya
        plt.clf()
        
        # Eksekusi
        exec(code_str, {}, local_vars)
        return True
    except Exception as e:
        st.error(f"⚠️ Gagal Render Grafik: {str(e)}")
        return False

def extract_dataframe_from_markdown(text):
    """
    Extract tabel Markdown menjadi Pandas DataFrame untuk export Excel.
    """
    try:
        lines = text.split('\n')
        data = []
        headers = []
        
        for line in lines:
            line = line.strip()
            # Pola tabel markdown: | col1 | col2 |
            if line.startswith('|') and line.endswith('|'):
                # Skip separator line (e.g. |---|---|)
                if '---' in line:
                    continue
                
                cells = [c.strip() for c in line.split('|')[1:-1]]
                
                if not headers:
                    headers = cells
                else:
                    # Pastikan jumlah kolom sama dengan header
                    if len(cells) == len(headers):
                        data.append(cells)
                    
        if headers and data:
            return pd.DataFrame(data, columns=headers)
        return None
    except:
        return None

def process_uploaded_file(uploaded_file):
    """
    Parser File Universal: Membaca konten berdasarkan ekstensi.
    """
    if uploaded_file is None: return None, None
    
    file_type = uploaded_file.name.split('.')[-1].lower()
    
    try:
        # --- GAMBAR ---
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
            
        # --- WORD (DOCX) ---
        elif file_type == 'docx':
            doc = docx.Document(uploaded_file)
            text = "\n".join([para.text for para in doc.paragraphs])
            return "text", text
            
        # --- EXCEL ---
        elif file_type in ['xlsx', 'xls']:
            df = pd.read_excel(uploaded_file)
            # Preview 50 baris pertama
            return "text", f"[DATA EXCEL IMPORT]\n{df.head(50).to_string()}"
            
        # --- POWERPOINT ---
        elif file_type == 'pptx':
            prs = Presentation(uploaded_file)
            text = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text.append(shape.text)
            return "text", "\n".join(text)
            
        # --- PYTHON CODE ---
        elif file_type == 'py':
            return "text", uploaded_file.getvalue().decode("utf-8")
            
        # --- GEOSPASIAL (GEOJSON/KML/GPX) ---
        elif file_type in ['geojson', 'kml', 'gpx']:
            return "geo", uploaded_file.getvalue().decode("utf-8")
            
        # --- KMZ (Zipped KML) ---
        elif file_type == 'kmz':
            with zipfile.ZipFile(uploaded_file, "r") as z:
                kml_list = [n for n in z.namelist() if n.endswith(".kml")]
                if kml_list:
                    with z.open(kml_list[0]) as f:
                        return "geo", f.read().decode("utf-8")
                else:
                    return "error", "Tidak ditemukan file KML dalam KMZ."
        else:
            return "error", "Format file belum didukung."
            
    except Exception as e:
        return "error", f"Error membaca file: {str(e)}"

# ==========================================
# 4. SIDEBAR SETTINGS (FUTURE MODEL LIST)
# ==========================================
with st.sidebar:
    st.title("🏗️ ENGINEX ULTIMATE")
    st.caption("v12.0 | Future Ready Core")
    st.markdown("---")
    
    # --- A. API KEY ---
    api_key_input = st.text_input("🔑 Google API Key:", type="password", help="Wajib diisi.")
    
    # Prioritas: Input User > Secrets
    if api_key_input:
        clean_api_key = api_key_input.strip()
    else:
        clean_api_key = st.secrets.get("GOOGLE_API_KEY", "")
    
    if not clean_api_key:
        st.warning("⚠️ Masukkan API Key.")
        st.stop()
        
    try:
        genai.configure(api_key=clean_api_key)
    except Exception as e:
        st.error(f"API Error: {e}")
        st.stop()

    # --- B. MODEL SELECTION (FUTURE LIST) ---
    st.markdown("### 🧠 Quantum AI Engine")
    
    # List Sesuai Permintaan User (Era 2026)
    future_model_list = [
        "models/gemini-2.5-flash-lite",
        "models/gemini-2.5-flash-image",
        "models/gemini-2.5-flash-preview-09-2025",
        "models/gemini-2.5-flash-lite-preview-09-2025",
        "models/gemini-3-pro-preview",
        "models/gemini-3-flash-preview",
        "models/gemini-3-pro-image-preview",
        "models/gemini-robotics-er-1.5-preview",
        "models/gemini-2.5-comput",
        # Fallback Stable Models
        "models/gemini-1.5-pro",
        "models/gemini-1.5-flash"
    ]
    
    selected_model_name = st.selectbox(
        "Pilih Versi Model:", 
        future_model_list,
        index=0,
        help="Pilih engine generative terbaru."
    )
    
    # Indikator Visual Kecanggihan
    if "3-" in selected_model_name:
        st.success(f"🚀 **GEN 3 ACTIVE:** {selected_model_name}")
    elif "2.5" in selected_model_name:
        st.info(f"⚡ **GEN 2.5 ACTIVE:** {selected_model_name}")
    elif "robotics" in selected_model_name:
        st.warning(f"🤖 **ROBOTICS MODE:** {selected_model_name}")
    else:
        st.caption(f"Standard Core: {selected_model_name}")

    # --- C. PROJECT MANAGEMENT ---
    with st.expander("📁 Manajemen Proyek", expanded=False):
        existing_projects = db.daftar_proyek()
        mode_proyek = st.radio("Opsi:", ["Buka Proyek Lama", "Buat Proyek Baru"])
        
        if mode_proyek == "Buat Proyek Baru":
            nama_proyek = st.text_input("Nama Proyek:", "DED Bendungan 2026")
        else:
            if existing_projects:
                nama_proyek = st.selectbox("Pilih Proyek:", existing_projects)
            else:
                st.info("Belum ada proyek.")
                nama_proyek = "Proyek Tanpa Nama"
        
        st.markdown("---")
        use_auto_pilot = st.checkbox("🤖 Mode Auto-Pilot", value=True)
        manual_expert = st.selectbox(
            "Ahli Manual:", 
            get_persona_list(), 
            disabled=use_auto_pilot
        )

    # --- D. FILE UPLOAD ---
    st.markdown("### 📎 Upload Data")
    uploaded_files = st.file_uploader(
        "Upload Dokumen/Gambar/Peta:", 
        accept_multiple_files=True,
        type=None
    )
    
    if st.button("🧹 Reset Sesi"):
        db.clear_chat(nama_proyek, st.session_state.current_expert_active)
        st.session_state.last_analysis_content = ""
        st.rerun()

    st.markdown("---")

    # ==========================================
    # 5. SIDEBAR DOWNLOAD CENTER
    # ==========================================
    st.header("📥 Download Center")
    export_placeholder = st.empty()
    
    def render_export_buttons(text_content, project_name):
        """Merender tombol download di sidebar berdasarkan output terakhir."""
        if not text_content:
            export_placeholder.info("Belum ada analisis.")
            return

        with export_placeholder.container():
            # 1. Word
            docx_data = EnginexExporter.create_pupr_word(text_content, project_name)
            st.download_button("📄 Laporan (.docx)", docx_data, f"{project_name}_Report.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            
            # 2. Excel (Jika ada tabel)
            df_table = extract_dataframe_from_markdown(text_content)
            if df_table is not None:
                xlsx_data = EnginexExporter.create_pupr_excel(df_table)
                st.download_button("📊 Tabel Data (.xlsx)", xlsx_data, f"{project_name}_Data.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                
                # 3. Civil 3D (Jika ada koordinat)
                cols = [c.lower() for c in df_table.columns]
                if any('x' in c for c in cols) and any('y' in c for c in cols):
                    csv_data = EnginexExporter.export_to_civil3d_csv(df_table)
                    st.download_button("🏗️ Civil 3D (.csv)", csv_data, f"{project_name}_Points.csv", "text/csv")
            
            # 4. PPT
            ppt_data = EnginexExporter.create_pupr_pptx(text_content, project_name)
            st.download_button("📢 Slide Presentasi (.pptx)", ppt_data, f"{project_name}_Slide.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation")

# ==========================================
# 6. LOGIKA UTAMA CHAT (MAIN APP)
# ==========================================

# Header
st.markdown(f'<div class="main-header">{nama_proyek}</div>', unsafe_allow_html=True)

# Tentukan Expert
if use_auto_pilot:
    active_expert = st.session_state.current_expert_active
else:
    active_expert = manual_expert
    st.session_state.current_expert_active = manual_expert

st.caption(f"Status: **Connected** | Ahli Aktif: **{active_expert}**")

# --- LOAD HISTORY ---
history_data = db.get_chat_history(nama_proyek, active_expert)

# Update Export State dari history terakhir
if history_data:
    last_assistant_msg = None
    for msg in reversed(history_data):
        if msg['role'] == 'assistant':
            last_assistant_msg = msg['content']
            break
    if last_assistant_msg:
        st.session_state.last_analysis_content = last_assistant_msg

# Render Chat History
for chat in history_data:
    with st.chat_message(chat['role']):
        st.markdown(chat['content'])
        # Render ulang grafik jika ada kode di history
        if chat['role'] == 'assistant' and "```python" in chat['content']:
            match = re.search(r"```python(.*?)```", chat['content'], re.DOTALL)
            if match and "plt." in match.group(1):
                with st.expander("📊 Lihat Grafik"):
                    execute_generated_code(match.group(1))
                    st.pyplot(plt.gcf())

# Tampilkan tombol export di awal load
render_export_buttons(st.session_state.last_analysis_content, nama_proyek)

# --- USER INPUT ---
user_input = st.chat_input(f"Konsultasi dengan {active_expert}...")

if user_input:
    # 1. ROUTING AUTO-PILOT
    target_expert = active_expert
    if use_auto_pilot:
        try:
            # Gunakan model Flash stabil untuk routing cepat
            router = genai.GenerativeModel("models/gemini-1.5-flash")
            prompt = f"""
            Tugas: Router Ahli Proyek.
            Pertanyaan: "{user_input}"
            Daftar Ahli: {list(gems_persona.keys())}
            Output: HANYA NAMA AHLI.
            """
            resp = router.generate_content(prompt)
            suggestion = resp.text.strip()
            if suggestion in gems_persona:
                target_expert = suggestion
                st.session_state.current_expert_active = target_expert
        except:
            pass # Fallback keep current expert
    
    if target_expert != active_expert:
        st.markdown(f'<div class="auto-pilot-box">🤖 Auto-Pilot mengalihkan ke: {target_expert}</div>', unsafe_allow_html=True)
        active_expert = target_expert

    # 2. SIMPAN CHAT USER
    db.simpan_chat(nama_proyek, active_expert, "user", user_input)
    with st.chat_message("user"):
        st.markdown(user_input)

    # 3. PERSIAPAN CONTENT
    payload = [user_input]
    if uploaded_files:
        for f in uploaded_files:
            if f.name not in st.session_state.processed_files:
                ftype, fcontent = process_uploaded_file(f)
                
                if ftype == "image":
                    with st.chat_message("user"): st.image(f, width=250)
                    payload.append(fcontent)
                elif ftype == "geo":
                    with st.chat_message("user"):
                        st.caption(f"🌍 Peta: {f.name}")
                        m = EnginexExporter.render_geospatial_map(fcontent, f.name.split('.')[-1])
                        if m: st_folium(m, height=300)
                    payload.append(f"\n[DATA GEO]: {fcontent[:3000]}...")
                elif ftype == "text":
                    payload.append(f"\n[DOKUMEN {f.name}]: {fcontent}")
                
                st.session_state.processed_files.add(f.name)

    # 4. GENERATE AI (SMART FALLBACK SYSTEM)
    with st.chat_message("assistant"):
        with st.spinner(f"{active_expert} sedang menganalisis..."):
            try:
                # Ambil Instruksi
                sys_instr = get_system_instruction(active_expert)
                # Tambah instruksi plot jika Engineer
                if "Code" not in active_expert and "Visionary" not in active_expert:
                    sys_instr += "\n[VISUALISASI]: Jika butuh grafik, buat kode Python (matplotlib). Akhiri dgn 'st.pyplot(plt.gcf())'."

                # --- SMART MODEL LOADING ---
                # Mencoba memanggil model yang dipilih user.
                # Jika nama model belum ada di API (karena belum rilis publik),
                # otomatis fallback ke 'gemini-1.5-pro' agar tidak error.
                
                active_model = None
                try:
                    # Coba inisialisasi model pilihan user
                    temp_model = genai.GenerativeModel(selected_model_name, system_instruction=sys_instr)
                    # Test dummy call untuk memastikan model valid
                    # (Opsional: kita langsung pakai saja, tangkap error saat stream)
                    active_model = temp_model
                except:
                    # Jika gagal init, fallback
                    active_model = genai.GenerativeModel("models/gemini-1.5-pro", system_instruction=sys_instr)

                # Build Context History (5 pesan terakhir)
                hist_objs = []
                chat_hist = db.get_chat_history(nama_proyek, active_expert)[-5:]
                for h in chat_hist:
                    if h['content'] != user_input:
                        role = "user" if h['role']=="user" else "model"
                        hist_objs.append({"role": role, "parts": [h['content']]})

                # Start Chat
                chat_session = active_model.start_chat(history=hist_objs)
                
                # Streaming Response
                # Kita bungkus send_message dalam try-except lagi untuk menangani "Model not found" saat request
                full_resp = ""
                box = st.empty()
                
                try:
                    stream = chat_session.send_message(payload, stream=True)
                    for chunk in stream:
                        if chunk.text:
                            full_resp += chunk.text
                            box.markdown(full_resp + "▌")
                except Exception as api_err:
                    # Jika error API (misal model 3.0 belum ready), switch ke 1.5 Pro on-the-fly
                    # st.warning(f"⚠️ Model {selected_model_name} sibuk/belum tersedia. Menggunakan Core Cadangan...")
                    fallback_model = genai.GenerativeModel("models/gemini-1.5-pro", system_instruction=sys_instr)
                    fallback_chat = fallback_model.start_chat(history=hist_objs)
                    resp_fallback = fallback_chat.send_message(payload) # Non-stream untuk fallback
                    full_resp = resp_fallback.text
                
                # Tampilkan Final
                box.markdown(full_resp)
                
                # Simpan DB
                db.simpan_chat(nama_proyek, active_expert, "assistant", full_resp)
                
                # 5. EKSEKUSI PLOT
                codes = re.findall(r"```python(.*?)```", full_resp, re.DOTALL)
                for c in codes:
                    if "plt." in c:
                        st.markdown("### 📉 Grafik Engineering")
                        with st.container():
                            execute_generated_code(c)
                            st.pyplot(plt.gcf())

                # 6. UPDATE SIDEBAR EXPORT
                st.session_state.last_analysis_content = full_resp
                render_export_buttons(full_resp, nama_proyek)

            except Exception as e:
                st.error(f"❌ Terjadi Kesalahan: {str(e)}")
                st.info("Saran: Refresh halaman atau ganti ke model 'gemini-1.5-pro' jika model eksperimental tidak stabil.")

# Footer
st.markdown("---")
st.caption("© 2026 ENGINEX Ultimate System | Powered by Gemini Quantum Engine")
