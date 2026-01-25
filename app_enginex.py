import streamlit as st
import pandas as pd
import io
import plotly.graph_objects as go
import json
import google.generativeai as genai

# --- 0. KONFIGURASI HALAMAN (Wajib Paling Atas) ---
st.set_page_config(
    page_title="ENGINEX | Integrated Engineering Hub",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 1. KONEKSI BACKEND (DATABASE & LOGIC) ---
# Pastikan file 'backend_iksi.py' ada di folder yang sama
try:
    from backend_iksi import IrigasiBackend
except ImportError:
    st.error("⚠️ File 'backend_iksi.py' tidak ditemukan. Pastikan file backend sudah direname dan diupload.")
    st.stop()

# Inisialisasi Backend Class
if 'app' not in st.session_state:
    st.session_state.app = IrigasiBackend()
app = st.session_state.app

# --- 2. STYLE CSS (Tampilan Profesional) ---
st.markdown("""
    <style>
    /* Header & Titles */
    .main-header {
        font-size: 28px; font-weight: 800; color: #1E3A8A;
        border-bottom: 3px solid #F59E0B; padding-bottom: 10px; margin-bottom: 20px;
    }
    .sub-header {font-size: 18px; font-weight: 600; color: #374151; margin-top: 15px;}
    
    /* Metrics/Cards */
    div[data-testid="stMetric"] {
        background-color: #F3F4F6; border: 1px solid #E5E7EB;
        padding: 15px; border-radius: 8px; border-left: 5px solid #1E3A8A;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {background-color: #F8FAFC; border-right: 1px solid #E2E8F0;}
    
    /* Chat Bubble Style */
    .chat-user {background-color: #E0F2FE; padding: 10px; border-radius: 10px; margin-bottom: 5px;}
    .chat-ai {background-color: #F0FDF4; padding: 10px; border-radius: 10px; border: 1px solid #BBF7D0; margin-bottom: 5px;}
    </style>
""", unsafe_allow_html=True)

# --- 3. HELPER FUNCTIONS ---
def update_master_aset_sql(id_aset, nama, jenis, luas, nab):
    try:
        app.cursor.execute("UPDATE master_aset SET nama_aset=?, jenis_aset=?, luas_layanan_desain=?, nilai_aset_baru=? WHERE id=?", (nama, jenis, luas, nab, id_aset))
        app.conn.commit()
        return True
    except: return False

def delete_master_aset_sql(id_aset):
    try:
        app.cursor.execute("DELETE FROM master_aset WHERE id=?", (id_aset,))
        app.cursor.execute("DELETE FROM inspeksi_aset WHERE aset_id=?", (id_aset,))
        app.conn.commit()
        return True
    except: return False

# --- 4. SIDEBAR MENU ---
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/0/06/Logo_Pekerjaan_Umum_Indonesia.png/600px-Logo_Pekerjaan_Umum_Indonesia.png", width=70)
    st.markdown("## **ENGINEX**")
    st.caption("Integrated Engineering Hub")
    st.divider()
    
    menu = st.radio("Modul Aplikasi", [
        "🏠 Dashboard Eksekutif",
        "🤖 Super-Team AI (Konsultasi)",
        "1️⃣ Inventaris Aset (1-O)",
        "2️⃣ Inspeksi & Kinerja (2-O)",
        "3️⃣ Data Penunjang",
        "📘 Dokumen Teknis (SKPL)",
        "🖨️ Laporan & Prioritas"
    ])
    
    st.divider()
    with st.expander("💾 Database Tools"):
        st.download_button("⬇️ Backup Data (JSON)", app.export_ke_json(), "enginex_backup.json")
        up_json = st.file_uploader("⬆️ Restore Data", type=['json'])
        if up_json and st.button("Restore Sekarang"):
            st.warning(app.import_dari_json(up_json))
            st.rerun()

# ==============================================================================
# MODUL 1: DASHBOARD EKSEKUTIF
# ==============================================================================
if "Dashboard" in menu:
    st.markdown('<div class="main-header">🏠 Dashboard Kinerja (SIKI)</div>', unsafe_allow_html=True)
    
    res = app.hitung_skor_iksi_audit()
    iksi = res['Total IKSI']
    det = res['Rincian']
    
    c1, c2 = st.columns([1.5, 2.5])
    with c1:
        # Gauge Chart
        fig = go.Figure(go.Indicator(
            mode = "gauge+number+delta", value = iksi,
            title = {'text': "<b>SKOR IKSI</b>"},
            delta = {'reference': 100},
            gauge = {
                'axis': {'range': [None, 100]}, 'bar': {'color': "#1E3A8A"},
                'steps': [{'range': [0, 55], 'color': '#EF4444'}, {'range': [55, 80], 'color': '#F59E0B'}, {'range': [80, 100], 'color': '#10B981'}]
            }
        ))
        fig.update_layout(height=300, margin=dict(l=20,r=20,t=40,b=20))
        st.plotly_chart(fig, use_container_width=True)
        
    with c2:
        st.subheader("Rincian Komponen")
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Fisik (45%)", det['Prasarana Fisik (45%)'])
        col_b.metric("Produktivitas (15%)", det['Produktivitas Tanam (15%)'])
        col_c.metric("Sarana (10%)", det['Sarana Penunjang (10%)'])
        
        col_d, col_e, col_f = st.columns(3)
        col_d.metric("Organisasi (15%)", det['Organisasi Personalia (15%)'])
        col_e.metric("P3A (10%)", det['P3A (10%)'])
        col_f.metric("Dokumentasi (5%)", det['Dokumentasi (5%)'])

# ==============================================================================
# MODUL 2: SUPER-TEAM AI (MULTI-AGENT SYSTEM)
# ==============================================================================
elif "Super-Team AI" in menu:
    st.markdown('<div class="main-header">🤖 ENGINEX Super-Team</div>', unsafe_allow_html=True)
    st.info("Konsultasikan proyek Anda dengan Tim Ahli Digital. Gunakan 'Project Manager' untuk panduan awal.")

    # A. SETUP API KEY
    try:
        # Coba ambil dari Secrets Streamlit Cloud
        api_key = st.secrets["GOOGLE_API_KEY"]
        genai.configure(api_key=api_key)
        api_ready = True
    except:
        # Fallback input manual
        api_key = st.text_input("⚠️ Masukkan Google Gemini API Key:", type="password")
        if api_key:
            genai.configure(api_key=api_key)
            api_ready = True
        else:
            api_ready = False
            st.warning("API Key diperlukan agar AI bisa menjawab.")

    # B. DEFINISI OTAK GEMS (PROMPT ENGINEERING)
    gems_instructions = {
        "👔 Project Manager & Verifikator": """
            Kamu adalah Senior Engineering Project Manager & QA Specialist.
            Tugasmu:
            1. ORCHESTRATOR: Saat user memberi proyek (misal: "Desain Rumah Tipe 100"), kamu TIDAK mendesain sendiri. Tapi kamu menyarankan alur kerja dan Gem mana yang harus dipakai.
               Contoh: "Untuk Rumah Tipe 100, langkahnya: 1. Tanya Arsitek (Denah), 2. Tanya Struktur (Pondasi), 3. Tanya Estimator (Biaya)."
            2. VERIFIKATOR: Jika user memberikan kode/hasil dari Gem lain, kamu cek apakah ada error, kode terpotong, atau logika yang salah.
            
            Daftar Tim Kamu:
            - Ahli Arsitek & Interior
            - Ahli Struktur (Sipil)
            - Ahli Estimator (RAB)
            - Ahli Hidrologi (Air)
            - Python Civil Lead (Coding)
            - CAD Automator (Drafting)
        """,
        "🏛️ Ahli Arsitek & Interior": "Kamu Senior Arsitek Tropis. Fokus: Konsep, Denah, Zoning, Material, Estetika. Paham GSB/KDB.",
        "🏗️ Ahli Struktur (Sipil)": "Kamu Ahli Struktur SNI (Beton/Baja). Fokus: Dimensi Kolom/Balok, Tulangan, Pondasi, Keamanan Gempa.",
        "💰 Ahli Estimator (RAB)": "Kamu Quantity Surveyor (QS). Fokus: Volume, AHSP PUPR, Budgeting, TKDN.",
        "🌊 Ahli Hidrologi & Irigasi": "Kamu Ahli SDA. Fokus: Banjir Rencana, Dimensi Saluran, Bendung, Neraca Air.",
        "🐍 Python Civil Lead": "Kamu Lead Developer App Sipil. Fokus: Coding Streamlit, Database SQLite, GIS Folium. Berikan kode lengkap.",
        "📐 CAD & BIM Automator": "Kamu Ahli Scripting (AutoLISP/Dynamo). Fokus: Membuat script otomatisasi gambar. Jangan ajarkan cara manual."
    }

    if api_ready:
        col_list, col_chat = st.columns([1, 2.5])
        
        with col_list:
            st.markdown("### Pilih Ahli:")
            selected_gem = st.radio("Tim Tersedia", list(gems_instructions.keys()))
            
            st.info(f"**Fokus Keahlian:**\n{gems_instructions[selected_gem][:150]}...")
            if st.button("🗑️ Reset Percakapan"):
                st.session_state.chat_history = []
                st.rerun()

        with col_chat:
            st.markdown(f"### 💬 Diskusi dengan {selected_gem}")
            
            # Init History
            if "chat_history" not in st.session_state:
                st.session_state.chat_history = []
            
            # Tampilkan History
            for chat in st.session_state.chat_history:
                with st.chat_message(chat["role"]):
                    st.markdown(chat["content"])
            
            # Input User
            if user_msg := st.chat_input(f"Tulis instruksi untuk {selected_gem}..."):
                # 1. Tampilkan User Msg
                st.session_state.chat_history.append({"role": "user", "content": user_msg})
                with st.chat_message("user"):
                    st.markdown(user_msg)
                
                # 2. Pikirkan Jawaban
                with st.chat_message("assistant"):
                    try:
                        with st.spinner(f"{selected_gem} sedang bekerja..."):
                            model = genai.GenerativeModel('gemini-1.5-pro', system_instruction=gems_instructions[selected_gem])
                            response = model.generate_content(user_msg)
                            reply = response.text
                            st.markdown(reply)
                            # Simpan Jawaban
                            st.session_state.chat_history.append({"role": "assistant", "content": reply})
                    except Exception as e:
                        st.error(f"Gagal terhubung ke AI: {e}")

# ==============================================================================
# MODUL 3: INVENTARISASI ASET (1-O)
# ==============================================================================
elif "Inventaris Aset" in menu:
    st.markdown('<div class="main-header">1️⃣ Inventarisasi Aset (Blangko 01-O)</div>', unsafe_allow_html=True)
    
    t1, t2, t3 = st.tabs(["📝 Input Data", "🗃️ Database", "✏️ Edit/Hapus"])
    
    with t1:
        with st.form("f_aset"):
            c1, c2 = st.columns(2)
            nm = c1.text_input("Nama Aset")
            jn = c1.selectbox("Jenis", ["Bendung Utama", "Intake", "Saluran Primer", "Saluran Sekunder", "Tersier", "Bangunan Bagi", "Lainnya"])
            stn = c2.selectbox("Satuan", ["Unit", "Km", "Buah"])
            thn = c2.number_input("Tahun Bangun", 2000)
            st.divider()
            ls = st.number_input("Luas Layanan (Ha) - WAJIB", 0.0)
            nab = st.number_input("Nilai Aset (Rp)", 0.0, step=1000000.0)
            det = st.text_area("Dimensi Teknis (JSON)", '{}')
            
            if st.form_submit_button("Simpan"):
                if nm and ls>0: st.success(app.tambah_master_aset(nm, jn, stn, thn, 0, ls, nab, det))
                else: st.error("Nama dan Luas wajib diisi.")

    with t2:
        st.dataframe(app.get_master_aset(), use_container_width=True)

    with t3:
        df = app.get_master_aset()
        if not df.empty:
            pilih = st.selectbox("Pilih Aset Edit", df['nama_aset'].unique())
            row = df[df['nama_aset']==pilih].iloc[0]
            with st.form("f_edit"):
                n_nm = st.text_input("Nama", row['nama_aset'])
                n_ls = st.number_input("Luas", float(row['luas_layanan_desain']))
                if st.form_submit_button("Update"):
                    if update_master_aset_sql(row['id'], n_nm, row['jenis_aset'], n_ls, row['nilai_aset_baru']):
                        st.success("Updated!"); st.rerun()
                if st.form_submit_button("Hapus Permanen", type="primary"):
                    if delete_master_aset_sql(row['id']): st.success("Deleted!"); st.rerun()

# ==============================================================================
# MODUL 4: INSPEKSI (2-O)
# ==============================================================================
elif "Inspeksi" in menu:
    st.markdown('<div class="main-header">2️⃣ Inspeksi Berkala (Blangko 02-O)</div>', unsafe_allow_html=True)
    m = app.get_master_aset()
    if m.empty: st.warning("Isi Master Aset dulu."); st.stop()
    
    aset = st.selectbox("Pilih Aset", m['nama_aset'].unique())
    aid = int(m[m['nama_aset']==aset].iloc[0]['id'])
    
    with st.form("f_ins"):
        c1, c2 = st.columns(2)
        ks = c1.slider("Kondisi Sipil (%)", 0, 100, 90)
        kme = c2.slider("Kondisi Pintu/ME (%)", 0, 100, 90)
        
        fs_opt = c1.radio("Fungsi Sipil", ["Baik", "Kurang", "Rusak"]); fs_val = 100 if fs_opt=="Baik" else (70 if fs_opt=="Kurang" else 40)
        fme_opt = c2.radio("Fungsi ME", ["Baik", "Kurang", "Rusak"]); fme_val = 100 if fme_opt=="Baik" else (70 if fme_opt=="Kurang" else 0)
        
        ls_imp = st.number_input("Luas Dampak (Ha)", 0.0)
        biaya = st.number_input("Biaya Rehab (Rp)", 0.0)
        rek = st.text_area("Rekomendasi")
        
        if st.form_submit_button("Simpan Laporan"):
            st.success(app.tambah_inspeksi(aid, "Surveyor", ks, kme, fs_val, fme_val, ls_imp, rek, biaya))

# ==============================================================================
# MODUL 5: DATA PENUNJANG
# ==============================================================================
elif "Data Penunjang" in menu:
    st.markdown('<div class="main-header">3️⃣ Data Penunjang IKSI</div>', unsafe_allow_html=True)
    t1, t2, t3 = st.tabs(["Tanam", "P3A", "Dokumen"])
    with t1:
        with st.form("ft"):
            mt=st.selectbox("Musim", ["MT1","MT2"]); lr=st.number_input("Renc Ha"); lrl=st.number_input("Real Ha")
            qa=st.number_input("Q Andalan"); qb=st.number_input("Q Butuh")
            if st.form_submit_button("Simpan"): st.success(app.tambah_data_tanam_lengkap(mt,lr,lrl,qa,qb,0,0))
        st.dataframe(app.get_table_data('data_tanam'))
    with t2:
        with st.form("fp"):
            nm=st.text_input("Nama P3A"); stt=st.selectbox("BH", ["Sudah","Belum"]); akt=st.selectbox("Aktif", ["Aktif","Kurang"])
            if st.form_submit_button("Simpan"): st.success(app.tambah_data_p3a(nm,"-",stt,akt,0))
        st.dataframe(app.get_table_data('data_p3a'))
    with t3:
        dok = ["Peta DI", "Skema Jaringan", "Buku Data"]; stat={}
        for d in dok: stat[d] = st.checkbox(d)
        if st.button("Update Dok"): st.success(app.update_dokumentasi(stat))

# ==============================================================================
# MODUL 6: DOKUMEN TEKNIS
# ==============================================================================
elif "Dokumen Teknis" in menu:
    st.markdown('<div class="main-header">📘 Spesifikasi Teknis (SKPL)</div>', unsafe_allow_html=True)
    with st.expander("Lihat KAK / Logika Perhitungan", expanded=True):
        st.markdown("""
        ### ENGINEX - CORE LOGIC
        **1. Fisik (45%):** Weighted Average berdasarkan Luas Layanan & Bobot Jenis (Bendung x1.5).
        **2. Produktivitas (15%):** Faktor K (Neraca Air) & Rasio Luas Tanam.
        **3. Prioritas:** `Score = ((100-Kondisi)*0.4 + (100-Fungsi)*0.6) * Log(LuasDampak)`
        """)

# ==============================================================================
# MODUL 7: LAPORAN
# ==============================================================================
elif "Laporan" in menu:
    st.markdown('<div class="main-header">🖨️ Cetak Laporan</div>', unsafe_allow_html=True)
    
    st.subheader("Matriks Prioritas Penanganan")
    prio = app.get_prioritas_matematis()
    if not prio.empty:
        st.dataframe(prio[['nama_aset','Kelas_Prioritas','estimasi_biaya']], use_container_width=True)
    
    st.divider()
    if st.button("📥 Download Excel Laporan Resmi"):
        b = io.BytesIO()
        with pd.ExcelWriter(b, engine='xlsxwriter') as w:
            app.get_master_aset().to_excel(w, sheet_name="Aset", index=False)
            if not prio.empty: prio.to_excel(w, sheet_name="Prioritas", index=False)
            # Add more sheets as needed
        st.download_button("Klik Download", b, "Laporan_ENGINEX.xlsx")