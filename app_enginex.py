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

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="ENGINEX Ultimate", page_icon="🏗️", layout="wide")

# --- CSS BIAR TAMPILAN GAGAH ---
st.markdown("""
<style>
    .main-header {font-size: 30px; font-weight: bold; color: #1E3A8A; margin-bottom: 10px;}
    [data-testid="stSidebar"] {background-color: #f8f9fa;}
    .stChatInput textarea {font-size: 16px !important;}
    
    /* Efek Avatar */
    .stChatMessage .avatar {background-color: #1E3A8A; color: white;}
    
    /* Tombol Download Custom */
    .stDownloadButton button {
        width: 100%;
        border-radius: 8px;
        font-weight: bold;
    }
    
    /* Highlight untuk Mode Auto-Pilot */
    .auto-pilot-msg {
        background-color: #e0f7fa;
        border-left: 5px solid #00acc1;
        padding: 10px;
        margin-bottom: 10px;
        border-radius: 5px;
        color: #006064;
        font-weight: bold;
    }
    
    /* Highlight Grafik */
    .plot-container {
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 10px;
        margin-top: 10px;
        background-color: white;
    }
</style>
""", unsafe_allow_html=True)

# --- INIT SESSION STATE ---
if 'processed_files' not in st.session_state:
    st.session_state.processed_files = set()
if 'current_expert_active' not in st.session_state:
    st.session_state.current_expert_active = "👑 The GEMS Grandmaster"

# ==========================================
# 0. FUNGSI BANTUAN EXPORT & PLOTTING
# ==========================================

def create_docx_from_text(text_content):
    """Mengubah teks chat menjadi file Word (.docx)"""
    try:
        doc = docx.Document()
        doc.add_heading('Laporan Output ENGINEX', 0)
        
        lines = text_content.split('\n')
        for line in lines:
            clean_line = line.strip()
            if clean_line.startswith('## '):
                doc.add_heading(clean_line.replace('## ', ''), level=2)
            elif clean_line.startswith('### '):
                doc.add_heading(clean_line.replace('### ', ''), level=3)
            elif clean_line.startswith('- ') or clean_line.startswith('* '):
                try:
                    doc.add_paragraph(clean_line, style='List Bullet')
                except:
                    doc.add_paragraph(clean_line)
            elif clean_line:
                doc.add_paragraph(clean_line)
                
        bio = io.BytesIO()
        doc.save(bio)
        bio.seek(0)
        return bio
    except Exception as e:
        return None

def extract_table_to_excel(text_content):
    """Mendeteksi tabel Markdown dalam chat dan mengubahnya ke Excel (.xlsx)"""
    try:
        lines = text_content.split('\n')
        table_data = []
        
        for line in lines:
            stripped = line.strip()
            if "|" in stripped:
                if set(stripped.replace('|', '').replace('-', '').replace(' ', '')) == set():
                    continue
                row_cells = [c.strip() for c in stripped.split('|')]
                if stripped.startswith('|'): row_cells = row_cells[1:]
                if stripped.endswith('|'): row_cells = row_cells[:-1]
                if row_cells:
                    table_data.append(row_cells)
        
        if len(table_data) < 2: return None
            
        headers = table_data[0]
        data_rows = table_data[1:]
        df = pd.DataFrame(data_rows, columns=headers)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Data_ENGINEX')
            worksheet = writer.sheets['Data_ENGINEX']
            for i, col in enumerate(df.columns):
                worksheet.set_column(i, i, 20)
        output.seek(0)
        return output
    except Exception as e:
        return None

def execute_generated_code(code_str):
    """
    [ENGINEERING PLOTTER]
    Mengeksekusi string kode Python yang dihasilkan AI untuk membuat grafik.
    """
    try:
        # Create a dictionary for local variables
        local_vars = {
            "pd": pd,
            "np": np,
            "plt": plt,
            "st": st
        }
        
        # Eksekusi kode dalam lingkungan aman
        exec(code_str, {}, local_vars)
        return True
    except Exception as e:
        st.error(f"⚠️ Gagal Render Grafik: {e}")
        return False

# ==========================================
# 1. SETUP API KEY & MODEL (SIDEBAR)
# ==========================================
with st.sidebar:
    st.title("🏗️ ENGINEX ULTIMATE")
    st.caption("v10.0 | Agentic + Plotting Engine")
    
    api_key_input = st.text_input("🔑 API Key:", type="password")
    if api_key_input:
        raw_key = api_key_input
        st.caption("ℹ️ Key Manual Digunakan")
    else:
        raw_key = st.secrets.get("GOOGLE_API_KEY")
    
    if not raw_key:
        st.warning("⚠️ Masukkan API Key Google AI Studio.")
        st.stop()
        
    clean_api_key = raw_key.strip()

try:
    genai.configure(api_key=clean_api_key, transport="rest")
except Exception as e:
    st.error(f"Config Error: {e}")

@st.cache_resource
def get_available_models_from_google(api_key_trigger):
    try:
        model_list = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                model_list.append(m.name)
        model_list.sort(key=lambda x: 'pro' not in x) 
        return model_list, None
    except Exception as e:
        return [], str(e)

real_models, error_msg = get_available_models_from_google(clean_api_key)

with st.sidebar:
    if error_msg: st.error(f"❌ Error: {error_msg}"); st.stop()
    if not real_models: st.warning("⚠️ Tidak ada model."); st.stop()

    default_idx = 0
    for i, m in enumerate(real_models):
        if "flash" in m:  
            default_idx = i
            break
            
    selected_model_name = st.selectbox("🧠 Pilih Otak AI:", real_models, index=default_idx)
    
    if "pro" in selected_model_name or "ultra" in selected_model_name:
        st.success(f"⚡ Mode: HIGH REASONING")
    else:
        st.info(f"🚀 Mode: HIGH SPEED")
    
    # [FIX] Menambahkan Toggle Auto Pilot di sini agar variabel 'use_auto_pilot' terdefinisi
    use_auto_pilot = st.checkbox("🤖 Mode Auto-Pilot", value=False)
    
    st.divider()

# --- KONEKSI DATABASE ---
# --- IMPORT BACKEND & PERSONA ---
try:
    from backend_enginex import EnginexBackend
    # IMPORT BARU DISINI:
    from persona import gems_persona, get_persona_list, get_system_instruction
    
    if 'backend' not in st.session_state:
        st.session_state.backend = EnginexBackend()
    db = st.session_state.backend
except ImportError as e:
    st.error(f"⚠️ Error Import File: {e}")
    st.stop()

# ==========================================
# 2. SAVE/LOAD & PROYEK
# ==========================================
with st.sidebar:
    with st.expander("💾 Manajemen Data"):
        st.download_button("⬇️ Backup JSON", db.export_data(), "backup.json", mime="application/json")
        uploaded_restore = st.file_uploader("⬆️ Restore", type=["json"])
        if uploaded_restore and st.button("Restore"):
            ok, msg = db.import_data(uploaded_restore)
            if ok: st.success(msg); st.rerun()
            else: st.error(msg)
    
    st.divider()
    existing_projects = db.daftar_proyek()
    mode_proyek = st.radio("Folder Proyek:", ["Proyek Baru", "Buka Lama"], horizontal=True)
    
    if mode_proyek == "Proyek Baru":
        nama_proyek = st.text_input("Nama Proyek:", "DED Irigasi 2026")
    else:
        nama_proyek = st.selectbox("Pilih Proyek:", existing_projects) if existing_projects else "Belum ada"
    st.divider()

# ==========================================
# 3. DEFINISI PERSONA (UPDATED WITH PLOTTING INSTRUCTIONS)
# ==========================================

PLOT_INSTRUCTION = """
[ATURAN PENTING UNTUK VISUALISASI DATA]:
Jika user meminta grafik/diagram/plot:
1. JANGAN HANYA MEMBERIKAN DESKRIPSI.
2. ANDA WAJIB MENULISKAN KODE PYTHON DI DALAM BLOK KODE (```python).
3. Gunakan library `matplotlib.pyplot` (sebagai plt) dan `numpy` (sebagai np).
4. WAJIB: Di akhir kode plotting, gunakan perintah `st.pyplot(plt.gcf())` agar grafik muncul di layar aplikasi
