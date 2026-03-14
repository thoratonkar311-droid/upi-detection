import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image

from detector import (
    check_dimensions,
    detect_crop,
    preprocess,
    extract_text_with_confidence,
    extract_details,
    validate_upi,
    detect_editing,
    detect_noise,
    detect_duplicate,
    detect_upi_app,
    fraud_score,
    classify_transaction,
    save_to_csv
)

st.set_page_config(page_title="UPI Fraud Detector", layout="wide")

st.title("🔍 UPI Screenshot Fraud Detector")

st.write("Upload one or more UPI transaction screenshots to analyze.")

files = st.file_uploader(
    "Upload UPI Screenshots",
    type=["png", "jpg", "jpeg"],
    accept_multiple_files=True
)

results = []

if files:

    progress = st.progress(0)

    for i, file in enumerate(files):

        image = Image.open(file)

        st.image(image, caption=file.name, width=250)

        img_array = np.array(image)

        try:

            # Run detection functions
            dimension = check_dimensions(img_array)

            crop = detect_crop(img_array)

            processed = preprocess(img_array)

            text = extract_text_with_confidence(processed)

            name, upi, amount, txn = extract_details(text)

            upi_valid = validate_upi(upi)

            editing = detect_editing(image)

            noise = detect_noise(img_array)

            duplicate = detect_duplicate(img_array)

            app = detect_upi_app(img_array)

            # Fraud score calculation
            score = fraud_score(
                upi_valid,
                txn,
                amount,
                editing,
                dimension,
                noise,
                crop,
                duplicate
            )

            status = classify_transaction(score)

        except Exception as e:

            name = "Unknown"
            app = "Unknown"
            score = 0
            status = "ERROR"

        result = {
            "File Name": file.name,
            "Name": name,
            "UPI App": app,
            "Fraud Score": score,
            "Status": status
        }

        results.append(result)

        save_to_csv({
            "File Name": file.name,
            "Name": name,
            "UPI App": app,
            "Fraud Score": score,
            "Status": status,
            "UPI Valid": upi_valid,
            "Editing Detected": editing,
            "Duplicate Screenshot": duplicate
        })

        progress.progress((i + 1) / len(files))

    df = pd.DataFrame(results)

    st.subheader("📊 Detection Results")
    st.dataframe(df)

    st.subheader("📈 Fraud Score Chart")
    st.bar_chart(df.set_index("File Name")["Fraud Score"])

    st.subheader("✅ Real Transactions")
    st.write(df[df["Status"] == "REAL"]["File Name"])

    st.subheader("⚠ Suspicious Transactions")
    st.write(df[df["Status"] == "SUSPICIOUS"]["File Name"])

    st.subheader("❌ Fake Transactions")
    st.write(df[df["Status"] == "FAKE"]["File Name"])

    st.success("Results saved to fraud_report.csv")
