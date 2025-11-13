import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd

st.set_page_config(page_title="CVAT Attribute Editor", layout="wide")

st.title("CVAT Video XML Attribute Editor")

st.markdown(
    """
Upload a CVAT **video XML** (`annotations.xml` from a *video* task).  
Select an attribute → choose tracks (or all tracks) → update values for entire track or first N frames.
"""
)

uploaded_file = st.file_uploader("Upload CVAT video XML file", type=["xml"])

if not uploaded_file:
    st.info("👆 Upload a CVAT video XML file to get started.")
    st.stop()

# Read bytes
xml_bytes = uploaded_file.getvalue()

# Parse XML
try:
    root = ET.fromstring(xml_bytes)
except ET.ParseError as e:
    st.error(f"❌ Failed to parse XML: {e}")
    st.stop()

# Debug info
st.subheader("Debug Info")
st.write(f"Root tag: `{root.tag}`")

tracks = root.findall(".//track")
st.write(f"Found **{len(tracks)}** `<track>` elements.")

if not tracks:
    st.error("No `<track>` found. This is not a CVAT video XML.")
    st.stop()

# Collect attribute info
attribute_values = {}
track_infos = []

for track in tracks:
    t_id = track.get("id", "")
    label = track.get("label", "")
    attr_names = set()

    # Track-level attributes
    for attr in track.findall("attribute"):
        name = attr.get("name")
        if name:
            attr_names.add(name)
            attribute_values.setdefault(name, set()).add((attr.text or "").strip())

    # Box-level attributes
    for box in track.findall("box"):
        for attr in box.findall("attribute"):
            name = attr.get("name")
            if name:
                attr_names.add(name)
                attribute_values.setdefault(name, set()).add((attr.text or "").strip())

    track_infos.append({
        "Track ID": t_id,
        "Label": label,
        "Attributes": ", ".join(sorted(attr_names)) if attr_names else "",
    })

if not attribute_values:
    st.error("No `<attribute>` elements found in this file.")
    st.stop()

st.subheader("Tracks Overview")
st.dataframe(pd.DataFrame(track_infos), use_container_width=True)

# -----------------------------
# Attribute selection
# -----------------------------
st.subheader("Edit Attributes")

attr_name = st.selectbox(
    "Choose attribute to modify",
    sorted(attribute_values.keys())
)

existing_values = sorted(v for v in attribute_values[attr_name] if v)

# -----------------------------
# Track selection mode (ALL / specific)
# -----------------------------
track_selection_mode = st.radio(
    "Track selection mode",
    ["Apply to ALL tracks", "Select specific tracks"],
    horizontal=True
)

track_label_to_id = {
    f"{info['Track ID']} – {info['Label']}": info["Track ID"]
    for info in track_infos
}

if track_selection_mode == "Select specific tracks":
    selected_track_labels = st.multiselect(
        "Select the tracks",
        list(track_label_to_id.keys())
    )
    selected_track_ids = {track_label_to_id[l] for l in selected_track_labels}

    if not selected_track_ids:
        st.warning("No tracks selected. Select tracks or choose 'Apply to ALL tracks'.")
        st.stop()
else:
    # ALL tracks
    selected_track_ids = {info["Track ID"] for info in track_infos}

st.write(f"Tracks chosen: **{len(selected_track_ids)}**")

# -----------------------------
# New value input
# -----------------------------
value_choice = st.selectbox(
    "New value",
    existing_values + ["⟶ Custom value"]
)

if value_choice == "⟶ Custom value":
    new_value = st.text_input("Custom value", value="")
else:
    new_value = value_choice

# -----------------------------
# Frame range mode
# -----------------------------
mode = st.radio(
    "Where to apply the change?",
    ["Entire track", "First N frames"],
    horizontal=True
)

num_frames = None
if mode == "First N frames":
    num_frames = st.number_input(
        "Number of frames",
        min_value=1,
        value=10,
        step=1
    )

# -----------------------------
# Process XML
# -----------------------------
st.markdown("---")

if st.button("Apply changes and generate modified XML", type="primary"):

    if not new_value:
        st.error("Value cannot be empty.")
        st.stop()

    root = ET.fromstring(xml_bytes)

    changed_tracks = 0
    changed_track_attrs = 0
    changed_boxes = 0

    for track in root.findall(".//track"):
        if track.get("id") not in selected_track_ids:
            continue

        changed_tracks += 1

        # Track-level attributes
        for attr in track.findall("attribute"):
            if attr.get("name") == attr_name:
                attr.text = new_value
                changed_track_attrs += 1

        # Box-level attributes
        boxes = list(track.findall("box"))

        if mode == "Entire track":
            target_boxes = boxes
        else:
            target_boxes = sorted(
                boxes,
                key=lambda b: int(b.get("frame", "0"))
            )[:num_frames]

        for box in target_boxes:
            for attr in box.findall("attribute"):
                if attr.get("name") == attr_name:
                    attr.text = new_value
                    changed_boxes += 1

    out_bytes = ET.tostring(root, encoding="utf-8")

    st.success(
        f"Updated **{attr_name} → {new_value}** in:\n"
        f"• {changed_tracks} tracks\n"
        f"• {changed_track_attrs} track-level attributes\n"
        f"• {changed_boxes} box-level attributes"
    )

    st.download_button(
        "📥 Download modified XML",
        data=out_bytes,
        file_name=f"modified_{uploaded_file.name}",
        mime="application/xml"
    )
