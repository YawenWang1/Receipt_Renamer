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

if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = []

# Theme-specific styles
if st.session_state.theme == "dark":
    st.markdown("""
        <style>
        .stApp {
            background-color: #0e1117;
            color: #fafafa;
        }

        .css-1d391kg {
            background-color: #1f2937;
            border-radius: 12px;
        }

        /* Uploader label */
        .stFileUploader label,
        .stFileUploader [data-testid="stWidgetLabel"],
        .stFileUploader [data-testid="stWidgetLabel"] p {
            color: #f8fafc !important;
            opacity: 1 !important;
            font-weight: 500 !important;
        }

        /* Dropzone text */
        .stFileUploader div[data-testid="stFileUploadDropzone"] p,
        .stFileUploader div[data-testid="stFileUploadDropzone"] div {
            color: #e5e7eb !important;
            font-weight: 500 !important;
            font-size: 15px !important;
            opacity: 1 !important;
        }

        /* Uploaded filenames */
        .stFileUploader [data-testid="stFileUploaderFileName"] {
            color: #f3f4f6 !important;
            font-weight: 500 !important;
            font-size: 15px !important;
            opacity: 1 !important;
        }

        /* File size / secondary text */
        .stFileUploader [data-testid="stFileUploaderFile"] small,
        .stFileUploader [data-testid="stFileUploaderFile"] span {
            color: #cbd5e1 !important;
            font-weight: 400 !important;
            opacity: 1 !important;
        }

        /* Data editor / dataframe */
        .stDataFrame, .stTable, .stDataEditor {
            background-color: #111827 !important;
            color: #f9fafb !important;
        }

        .stDataFrame thead th, .stDataEditor thead th {
            background-color: #1f2937 !important;
            color: #f9fafb !important;
        }

        .stDataFrame td, .stDataEditor td {
            color: #f9fafb !important;
        }

        /* Info box */
        .stAlert {
            background-color: #1e3a5f !important;
            color: #bfdbfe !important;
            border-radius: 8px;
        }

        /* Uploader container */
        .stFileUploader {
            background-color: #111827 !important;
            border: 1px solid #374151 !important;
            border-radius: 12px;
        }

        /* Metrics */
        div[data-testid="metric-container"] {
            background-color: #111827 !important;
            border: 1px solid #374151 !important;
            border-radius: 12px !important;
            padding: 12px 16px !important;
            color: #f9fafb !important;
            box-shadow: none !important;
        }

        div[data-testid="metric-container"] > label[data-testid="stMetricLabel"] > div,
        div[data-testid="metric-container"] > label[data-testid="stMetricLabel"] > div p {
            color: #cbd5e1 !important;
            font-weight: 600 !important;
        }

        div[data-testid="metric-container"] [data-testid="stMetricValue"] {
            color: #f9fafb !important;
        }

        div[data-testid="metric-container"] [data-testid="stMetricDelta"] {
            color: #cbd5e1 !important;
        }

        /* Selectbox */
        div[data-baseweb="select"] > div {
            background-color: #111827 !important;
            color: #f9fafb !important;
            border: 1px solid #374151 !important;
            border-radius: 8px !important;
        }

        div[data-baseweb="select"] * {
            color: #f9fafb !important;
        }

        div[role="listbox"] {
            background-color: #111827 !important;
            color: #f9fafb !important;
            border: 1px solid #374151 !important;
        }

        div[role="option"] {
            background-color: #111827 !important;
            color: #f9fafb !important;
        }

        div[role="option"]:hover {
            background-color: #1f2937 !important;
        }

        /* General text */
        .stMarkdown, .stText, .stSelectbox, .stMultiSelect, .stSlider, .stMetric,
        div[data-testid="stMarkdownContainer"] p, label, small {
            color: #f9fafb !important;
        }
        </style>
    """, unsafe_allow_html=True)

else:
    st.markdown("""
        <style>
        .stApp {
            background-color: #f4f4f5;
            color: #1f2937;
        }

        .css-1d391kg {
            background-color: #ffffff;
            border-radius: 12px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.10);
        }

        /* Uploader label */
        .stFileUploader label,
        .stFileUploader [data-testid="stWidgetLabel"],
        .stFileUploader [data-testid="stWidgetLabel"] p {
            color: #334155 !important;
            opacity: 1 !important;
            font-weight: 500 !important;
        }

        /* Dropzone text */
        .stFileUploader div[data-testid="stFileUploadDropzone"] p,
        .stFileUploader div[data-testid="stFileUploadDropzone"] div {
            color: #475569 !important;
            font-weight: 500 !important;
            font-size: 15px !important;
            opacity: 1 !important;
        }

        /* Uploaded filenames */
        .stFileUploader [data-testid="stFileUploaderFileName"] {
            color: #475569 !important;
            font-weight: 500 !important;
            font-size: 15px !important;
            opacity: 1 !important;
        }

        /* File size / secondary text */
        .stFileUploader [data-testid="stFileUploaderFile"] small,
        .stFileUploader [data-testid="stFileUploaderFile"] span {
            color: #64748b !important;
            font-weight: 400 !important;
            opacity: 1 !important;
        }

        /* Data editor / dataframe */
        .stDataFrame, .stTable, .stDataEditor {
            background-color: #ffffff !important;
            color: #1f2937 !important;
        }

        .stDataFrame thead th, .stDataEditor thead th {
            background-color: #f1f5f9 !important;
            color: #1f2937 !important;
        }

        .stDataFrame td, .stDataEditor td {
            color: #1f2937 !important;
        }

        /* Info box */
        .stAlert {
            background-color: #e0f2fe !important;
            color: #1e40af !important;
            border-radius: 8px;
        }

        /* Uploader container */
        .stFileUploader {
            background-color: #ffffff !important;
            border: 1px solid #d1d5db !important;
            border-radius: 12px;
        }

        /* Metrics */
        div[data-testid="metric-container"] {
            background-color: #ffffff !important;
            border: 1px solid #e2e8f0 !important;
            border-radius: 12px !important;
            padding: 12px 16px !important;
            color: #0f172a !important;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06) !important;
        }

        div[data-testid="metric-container"] > label[data-testid="stMetricLabel"] > div,
        div[data-testid="metric-container"] > label[data-testid="stMetricLabel"] > div p {
            color: #64748b !important;
            font-weight: 600 !important;
        }

        div[data-testid="metric-container"] [data-testid="stMetricValue"] {
            color: #0f172a !important;
        }

        div[data-testid="metric-container"] [data-testid="stMetricDelta"] {
            color: #475569 !important;
        }

        /* Selectbox */
        div[data-baseweb="select"] > div {
            background-color: #ffffff !important;
            color: #1f2937 !important;
            border: 1px solid #cbd5e1 !important;
            border-radius: 8px !important;
        }

        div[data-baseweb="select"] * {
            color: #1f2937 !important;
        }

        div[role="listbox"] {
            background-color: #ffffff !important;
            color: #1f2937 !important;
            border: 1px solid #cbd5e1 !important;
        }

        div[role="option"] {
            background-color: #ffffff !important;
            color: #1f2937 !important;
        }

        div[role="option"]:hover {
            background-color: #f8fafc !important;
        }

        /* General text */
        .stMarkdown, .stText, .stSelectbox, .stMultiSelect, .stSlider, .stMetric,
        div[data-testid="stMarkdownContainer"] p, label, small {
            color: #1f2937 !important;
        }
        </style>
    """, unsafe_allow_html=True)
# Shared button styling for Process / ZIP buttons
st.markdown("""
    <style>
    /* === Process / ZIP buttons (unchanged) === */
    div[class*="st-key-processbtn"] button,
    div[class*="st-key-zipbtn"] button {
        background-color: #ff5a5f !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        padding: 0.6rem 1rem !important;
        box-shadow: 0 2px 6px rgba(0,0,0,0.15) !important;
    }

    div[class*="st-key-processbtn"] button:hover,
    div[class*="st-key-zipbtn"] button:hover {
        background-color: #ff4a4f !important;
        color: #ffffff !important;
    }

    div[class*="st-key-processbtn"] button:focus,
    div[class*="st-key-processbtn"] button:active,
    div[class*="st-key-zipbtn"] button:focus,
    div[class*="st-key-zipbtn"] button:active {
        background-color: #ff4a4f !important;
        color: #ffffff !important;
        outline: none !important;
        border: none !important;
        box-shadow: 0 0 0 0.2rem rgba(255,90,95,0.25) !important;
    }

    /* === BROWSE FILES BUTTON — SUPER AGGRESSIVE SELECTOR (works in BOTH themes) === */
    /* This targets every possible way Streamlit renders the "Browse files" button */
    div[data-testid="stFileUploader"] section[data-testid="stFileUploadDropzone"] button,
    div[data-testid="stFileUploadDropzone"] button,
    .stFileUploader button,
    div[data-testid="stFileUploader"] button[data-testid="baseButton-secondary"] {
        background-color: #111827 !important;
        color: #f9fafb !important;
        border: 1px solid #374151 !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        opacity: 1 !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.2) !important;
        min-height: 38px !important;   /* matches Streamlit default height */
    }

    /* Hover */
    div[data-testid="stFileUploader"] section[data-testid="stFileUploadDropzone"] button:hover,
    div[data-testid="stFileUploadDropzone"] button:hover,
    .stFileUploader button:hover,
    div[data-testid="stFileUploader"] button[data-testid="baseButton-secondary"]:hover {
        background-color: #1f2937 !important;
        color: #ffffff !important;
        border: 1px solid #4b5563 !important;
    }

    /* Focus / Active */
    div[data-testid="stFileUploader"] section[data-testid="stFileUploadDropzone"] button:focus,
    div[data-testid="stFileUploader"] section[data-testid="stFileUploadDropzone"] button:active,
    div[data-testid="stFileUploadDropzone"] button:focus,
    div[data-testid="stFileUploadDropzone"] button:active,
    .stFileUploader button:focus,
    .stFileUploader button:active,
    div[data-testid="stFileUploader"] button[data-testid="baseButton-secondary"]:focus,
    div[data-testid="stFileUploader"] button[data-testid="baseButton-secondary"]:active {
        background-color: #1f2937 !important;
        color: #ffffff !important;
        border: 1px solid #4b5563 !important;
        outline: none !important;
        box-shadow: 0 0 0 0.2rem rgba(75,85,99,0.25) !important;
    }
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
    accept_multiple_files=True,
    key="receipt_uploader"
)

if uploaded_files:
    st.session_state.uploaded_files = uploaded_files

# if st.session_state.uploaded_files:
#     process_clicked = st.button(
#         f"🚀 Process {len(st.session_state.uploaded_files)} Files",
#         key="processbtn"
#     )

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
        width='stretch',
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
        width='stretch'
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