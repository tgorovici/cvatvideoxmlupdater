import streamlit as st
import xml.etree.ElementTree as ET
import io
import pandas as pd

st.set_page_config(page_title="CVAT Attribute Editor", layout="wide")

st.title("CVAT Video XML Attribute Editor")

st.markdown(
    "Upload a CVAT **video XML**, choose an attribute, select tracks, "
    "and update attribute values for the whole track or the first N frames."
)

uploaded_file = st.file_uploader("Upload CVAT video XML file", type=["xml"])

if not uploaded_file:
    st.info("👆 Upload a CVAT video XML file to get started.")
    st.stop()

# Read XML bytes once
xml_bytes = uploaded_file.getvalue()

# Try to parse XML
try:
    root = ET.fromstring(xml_bytes)
except ET.ParseError as e:
    st.err
