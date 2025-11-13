import streamlit as st
import xml.etree.ElementTree as ET
import io
import pandas as pd

st.set_page_config(page_title="CVAT Attribute Editor", layout="wide")

st.title("CVAT Video XML Attribute Editor")

st.markdown(
    """
Upload a CVAT **video XML** (`annotations.xml` from the ZIP), choose an attribute,
select tracks, and update attribute values for the whole track or the first N frames.
"""
)

uploaded_file = st.file_uploader("Upload CVAT video XML file (annotations.xml)", type=["xml"])

if not uploaded_file:
    st.info("👆 Upload a CVAT video XML file to get started.")
    st.stop()

# Read XML bytes
xml_bytes = uploaded_file.getvalue()

# Try to parse XML
try:
    root = ET.fromstring(xml_bytes)
except ET.ParseError as e:
    st.error(f"❌ Failed to parse XML: {e}")
    st.stop()

# --- Debug info so you can see what's going on ---
st.subheader("Debug: XML structure")
st.write(f"Root tag: `{root.tag}`")

# Find tracks (anywhere below root)
tracks = root.findall(".//track")
st.write(f"Found `{len(tracks)}` `<track>` elements in the XML.")

if not tracks:
    st.error(
        "No `<track>` elements found.\n\n"
        "This app currently supports **CVAT video XML** (with `<track>` nodes). "
        "Make sure you uploaded `annotations.xml` from a *video* task export, "
        "not an image task or the ZIP file itself."
    )
    st.stop()

# --- Collect track info and attribute summary ---

attribute_values = {}  # attr_name -> set(values)
track_infos = []       # list of {id, label, attributes}

for track in tracks:
    t_id = track.get("id", "")
    label = track.get("label", "")
    attr_names = set()

    # track-level <attribute>
    for attr in track.findall("attribute"):
        name = attr.get("name")
        if not name:
            continue
        attr_names.add(name)
        value = (attr.text or "").strip()
        attribute_values.setdefault(name, set()).add(value)

    # box-level <attribute> (per-frame)
    for box in track.findall("box"):
        for attr in box.findall("attribute"):
            name = attr.get("name")
            if not name:
                continue
            attr_names.add(name)
            value = (attr.text or "").strip()
            attribute_values.setdefault(name, set()).add(value)

    track_infos.append(
        {
            "Track ID": t_id,
            "Label": label,
            "Attributes in track": ", ".join(sorted(attr_names)) if attr_names else "",
        }
    )

if not attribute_values:
    st.error(
        "No `<attribute>` elements found under `<track>` / `<box>`.\n\n"
        "Check that your XML actually has attributes like:\n"
        "`<attribute name=\"Visibility\">61-80%</attribute>`"
    )
    st.stop()

st.subheader("Tracks overview")
st.dataframe(pd.DataFrame(track_infos), use_container_width=True)

st.subheader("Edit attributes")

# --- Attribute selection ---
attr_name = st.selectbox(
    "Attribute to modify",
    sorted(attribute_values.keys()),
)

existing_values = sorted(v for v in attribute_values[attr_name] if v != "")

# --- Track selection ---
track_label_to_id = {
    f"{info['Track ID']} – {info['Label']}": info["Track ID"] for info in track_infos
}

selected_track_labels = st.multiselect(
    "Tracks to modify (leave empty to apply to ALL tracks)",
    list(track_label_to_id.keys()),
)

if selected_track_labels:
    selected_track_ids = {track_label_to_id[lbl] for lbl in selected_track_labels}
else:
    # No selection = all tracks
    selected_track_ids = {info["Track ID"] for info in track_infos}

# --- New value selection ---
options = existing_values + ["⟶ Custom value"]
choice = st.selectbox("New value", options)

if choice == "⟶ Custom value":
    custom_value = st.text_input("Custom value", value="")
    new_value = custom_value.strip()
else:
    new_value = choice

# --- Frame range selection ---
mode = st.radio(
    "Where to apply the change?",
    ["Entire track", "First N frames from start"],
    horizontal=True,
)

num_frames = None
if mode == "First N frames from start":
    num_frames = st.number_input(
        "Number of frames (boxes) from the beginning of each track",
        min_value=1,
        step=1,
        value=10,
    )

st.markdown("---")

if st.button("Apply changes and generate modified XML", type="primary"):
    if not new_value:
        st.error("Please provide a non-empty value for the attribute.")
        st.stop()

    # Re-parse a fresh copy so we don't accumulate edits across reruns
    root = ET.fromstring(xml_bytes)

    changed_tracks = 0
    changed_boxes = 0
    changed_track_attrs = 0

    for track in root.findall(".//track"):
        t_id = track.get("id", "")
        if t_id not in selected_track_ids:
            continue

        changed_tracks += 1

        # 1) Update track-level attributes
        for attr in track.findall("attribute"):
            if attr.get("name") == attr_name:
                attr.text = new_value
                changed_track_attrs += 1

        # 2) Update attributes inside <box> elements (per-frame)
        boxes = list(track.findall("box"))

        if mode == "Entire track":
            boxes_to_change = boxes
        else:
            # Sort boxes by frame number and take first N
            boxes_sorted = sorted(
                boxes,
                key=lambda b: int(b.get("frame", "0")),
            )
            boxes_to_change = boxes_sorted[: int(num_frames)]

        for box in boxes_to_change:
            for attr in box.findall("attribute"):
                if attr.get("name") == attr_name:
                    attr.text = new_value
                    changed_boxes += 1

    output_bytes = ET.tostring(root, encoding="utf-8")

    st.success(
        f"✅ Updated attribute '{attr_name}' to '{new_value}' "
        f"in {changed_tracks} tracks, {changed_track_attrs} track-level attrs, "
        f"and {changed_boxes} box-level attrs."
    )

    st.download_button(
        label="📥 Download modified XML",
        data=output_bytes,
        file_name=f"modified_{uploaded_file.name}",
        mime="application/xml",
    )

st.caption(
    "Notes: This app updates all attributes with the selected name inside each selected track. "
    "For 'First N frames', it updates attributes only in the first N <box> elements per track "
    "(sorted by frame), plus the track-level attributes."
)
