import streamlit as st
import pandas as pd
import cv2
import zipfile
import io
import os
import time
import warnings

warnings.filterwarnings("ignore", category=UserWarning)

st.set_page_config(page_title="Receipt Renamer", page_icon="🧾", layout="wide")

# ====================== THEME ======================
if 'theme' not in st.session_state:
    st.session_state.theme = "dark"

def toggle_theme():
    st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"

if st.session_state.theme == "dark":
    st.markdown("""
        <style>
        .stApp { background-color: #0e1117; color: #fafafa; }
        .css-1d391kg { background-color: #1f2937; border-radius: 12px; }
        </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
        <style>
        .stApp { background-color: #f8f9fa; color: #1f2937; }
        .css-1d391kg { background-color: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-radius: 12px; }
        </style>
    """, unsafe_allow_html=True)

# ====================== HEADER ======================
col1, col2 = st.columns([5, 1])
with col1:
    st.title("🧾 Receipt Renamer")
with col2:
    if st.button("☀️" if st.session_state.theme == "dark" else "🌙", help="Toggle theme"):
        toggle_theme()
        st.rerun()

st.markdown("**Simple • Private • Local** — AI-powered receipt scanner and renamer")
st.info("🧪 **Demo Mode** — Real AI processing requires Ollama running locally on your computer.")

# ====================== UPLOADER ======================
uploaded_files = st.file_uploader(
    "Upload Receipts (JPG, PNG, PDF)",
    type=['jpg', 'jpeg', 'png', 'pdf'],
    accept_multiple_files=True
)

# ====================== DEMO PROCESSING ======================
if uploaded_files:
    if st.button(f"🚀 Process {len(uploaded_files)} Files", type="primary"):
        with st.spinner("Processing in demo mode..."):
            # Simulate realistic processing time based on number of files
            estimated_time = len(uploaded_files) * 2.8   # ~2.8 seconds per file
            progress_bar = st.progress(0)
            status_text = st.empty()

            for i in range(len(uploaded_files)):
                status_text.text(f"Processing file {i+1}/{len(uploaded_files)}...")
                time.sleep(0.9)  # simulate delay
                progress_bar.progress((i + 1) / len(uploaded_files))

            # Create realistic mock results
            mock_results = []
            for i, file in enumerate(uploaded_files):
                mock_results.append({
                    "Original File": file.name,
                    "Date": "2025-04-01",
                    "Vendor": "Demo Store",
                    "Category": "Eten" if any(x in file.name.lower() for x in ["ah", "jumbo", "aldi"]) else "Other",
                    "Currency": "€",
                    "Amount": round(5.5 + i * 2.3, 2),
                    "Order Number": f"DEMO{10000 + i}",
                    "Raw Text": "Demo OCR output - Real version requires Ollama"
                })

            st.session_state.df_results = pd.DataFrame(mock_results)
            st.session_state.data_processed = True
            st.session_state.total_time = round(estimated_time, 1)
            st.session_state.ocr_time = round(estimated_time * 0.4, 1)
            st.session_state.llm_time = round(estimated_time * 0.6, 1)

            st.success(f"✅ Demo processing completed in {st.session_state.total_time} seconds!")
            st.rerun()

# ====================== REVIEW & EDIT ======================
if st.session_state.get('data_processed') and not st.session_state.get('df_results', pd.DataFrame()).empty:
    st.divider()
    st.subheader("Review & Edit")

    df = st.session_state.df_results.copy()

    def format_filename(row):
        try:
            d = row['Date'][2:].replace('-', '_')
            v = str(row['Vendor']).replace(' ', '_')
            a = f"{float(row['Amount']):.2f}"
            return f"{d}_{v}_{a}.jpg"
        except:
            return "error.jpg"

    df["New Filename"] = df.apply(format_filename, axis=1)

    edited_df = st.data_editor(
        df,
        column_config={
            "Original File": st.column_config.TextColumn("Original File", disabled=True),
            "Amount": st.column_config.NumberColumn(format="%.2f"),
            "New Filename": st.column_config.TextColumn(disabled=False),
            "Order Number": st.column_config.TextColumn(disabled=False),
            "Currency": st.column_config.TextColumn(disabled=False),
        },
        use_container_width=True,
        hide_index=True
    )

    # Timers (demo)
    if 'total_time' in st.session_state:
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("⏱️ Total Processing Time", f"{st.session_state.total_time} seconds")
        c2.metric("👁️ OCR Time", f"{st.session_state.ocr_time} seconds")
        c3.metric("🧠 LLM Time", f"{st.session_state.llm_time} seconds")

    # Preview
    st.subheader("Receipt Preview")
    selected_file = st.selectbox(
        "Select a receipt to preview",
        options=edited_df["Original File"].tolist(),
        key="preview_select"
    )

    st.image(
        "https://via.placeholder.com/800x500/1f2937/ffffff?text=Receipt+Preview",
        caption="Demo Preview — Real image would appear here when running locally with Ollama",
        use_column_width=True
    )

    # Summary & Download
    st.divider()
    col1, col2 = st.columns(2)
    col1.metric("Total Receipts", len(edited_df))
    col2.metric("Grand Total", f"€ {edited_df['Amount'].sum():.2f}")

    if st.button("📦 Generate ZIP", type="primary"):
        final_df = edited_df.copy()
        final_df["New Filename"] = final_df["New Filename"].apply(lambda x: f"{os.path.splitext(str(x))[0]}.jpg")

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("summary.csv", final_df.to_csv(sep=";", decimal=",", index=False).encode('utf-8'))
            zf.writestr("demo_receipt.jpg", b"dummy image content")

        st.download_button(
            "⬇️ Download Demo ZIP",
            zip_buffer.getvalue(),
            "demo_renamed_receipts.zip",
            "application/zip"
        )