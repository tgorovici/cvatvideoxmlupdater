import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd

st.set_page_config(page_title="CVAT Attribute Range Editor", layout="wide")

st.title("CVAT Video XML Attribute Editor – Multiple Frame Ranges")

st.markdown("""
Upload a CVAT **video XML** (`annotations.xml` from *video* export).  
Then:

1. Select tracks  
2. Select attributes  
3. Define **multiple frame ranges** per track per attribute  
4. Apply changes  
""")

uploaded_file = st.file_uploader("Upload CVAT video XML", type=["xml"])

if not uploaded_file:
    st.info("Upload `annotations.xml` to begin.")
    st.stop()

xml_bytes = uploaded_file.getvalue()

# -----------------------------
# PARSE XML
# -----------------------------
try:
    root = ET.fromstring(xml_bytes)
except ET.ParseError as e:
    st.error(f"❌ XML Parse Error: {e}")
    st.stop()

tracks = root.findall(".//track")
if not tracks:
    st.error("❌ No <track> elements found. This is not a CVAT VIDEO XML.")
    st.stop()

# Collect track + attribute overview
attribute_values = {}
track_infos = []

for track in tracks:
    t_id = track.get("id", "")
    label = track.get("label", "")
    attrs = set()

    for attr in track.findall("attribute"):
        attrs.add(attr.get("name"))
        attribute_values.setdefault(attr.get("name"), set()).add(attr.text)

    for box in track.findall("box"):
        for attr in box.findall("attribute"):
            attrs.add(attr.get("name"))
            attribute_values.setdefault(attr.get("name"), set()).add(attr.text)

    track_infos.append({
        "Track ID": t_id,
        "Label": label,
        "Attributes": ", ".join(sorted(attrs))
    })

st.subheader("Tracks Overview")
st.dataframe(pd.DataFrame(track_infos), use_container_width=True)

# -----------------------------
# TRACK SELECTION
# -----------------------------
st.subheader("1️⃣ Select Tracks")

track_selection_mode = st.radio(
    "Track selection:",
    ["Apply to ALL tracks", "Select specific tracks"],
    horizontal=True
)

track_lookup = {
    f"{info['Track ID']} – {info['Label']}": info["Track ID"]
    for info in track_infos
}

if track_selection_mode == "Select specific tracks":
    selected_labels = st.multiselect("Tracks:", list(track_lookup.keys()))
    if not selected_labels:
        st.stop()

    selected_track_ids = {track_lookup[l] for l in selected_labels}
else:
    selected_track_ids = {info["Track ID"] for info in track_infos}

# -----------------------------
# ATTRIBUTE SELECTION
# -----------------------------
st.subheader("2️⃣ Select Attributes")

all_attr_names = sorted(attribute_values.keys())

selected_attrs = st.multiselect("Attributes to modify:", all_attr_names)
if not selected_attrs:
    st.stop()

# -----------------------------
# SELECT NEW VALUE FOR EACH ATTRIBUTE
# -----------------------------
st.subheader("3️⃣ New Values")

for attr in selected_attrs:
    st.markdown(f"### Attribute `{attr}`")

    values = sorted(v for v in attribute_values[attr] if v)

    choice = st.selectbox(
        f"New value for `{attr}`:",
        values + ["⟶ Custom value"],
        key=f"val_choice_{attr}",
    )
    if choice == "⟶ Custom value":
        st.text_input(
            f"Custom value for {attr}",
            key=f"custom_val_{attr}"
        )

    st.markdown("---")

# -----------------------------
# FRAME RANGES (MULTIPLE)
# -----------------------------
st.subheader("4️⃣ Frame Ranges (supports multiple ranges per track per attribute)")

if track_selection_mode == "Apply to ALL tracks":
    # Global ranges per attribute
    for attr in selected_attrs:
        st.markdown(f"## Attribute `{attr}` (GLOBAL ranges)")

        key = f"ranges_global_{attr}"

        if key not in st.session_state:
            st.session_state[key] = []

        delete_list = []

        # Show existing ranges
        for idx, r in enumerate(st.session_state[key]):
            c1, c2, c3 = st.columns([1, 1, 0.3])
            with c1:
                st.session_state[key][idx]["start"] = st.number_input(
                    f"Start {idx+1}",
                    min_value=0,
                    value=r["start"],
                    key=f"g_start_{attr}_{idx}"
                )
            with c2:
                st.session_state[key][idx]["end"] = st.number_input(
                    f"End {idx+1}",
                    min_value=0,
                    value=r["end"],
                    key=f"g_end_{attr}_{idx}"
                )
            with c3:
                if st.button(f"🗑️", key=f"g_del_{attr}_{idx}"):
                    delete_list.append(idx)

        for idx in reversed(delete_list):
            del st.session_state[key][idx]

        if st.button(f"➕ Add range for `{attr}`", key=f"g_add_{attr}"):
            st.session_state[key].append({"start": 0, "end": 0})

        st.markdown("---")

else:
    # Per-track, per-attribute ranges
    for lbl in selected_labels:
        t_id = track_lookup[lbl]
        with st.expander(f"Track {lbl} – Frame Ranges"):
            for attr in selected_attrs:
                st.markdown(f"### Attribute `{attr}`")

                key = f"ranges_{t_id}_{attr}"
                if key not in st.session_state:
                    st.session_state[key] = []

                delete_list = []

                for idx, r in enumerate(st.session_state[key]):
                    c1, c2, c3 = st.columns([1, 1, 0.3])
                    with c1:
                        st.session_state[key][idx]["start"] = st.number_input(
                            f"Start {idx+1}",
                            min_value=0,
                            value=r["start"],
                            key=f"start_{t_id}_{attr}_{idx}"
                        )
                    with c2:
                        st.session_state[key][idx]["end"] = st.number_input(
                            f"End {idx+1}",
                            min_value=0,
                            value=r["end"],
                            key=f"end_{t_id}_{attr}_{idx}"
                        )
                    with c3:
                        if st.button(f"🗑️", key=f"del_{t_id}_{attr}_{idx}"):
                            delete_list.append(idx)

                for idx in reversed(delete_list):
                    del st.session_state[key][idx]

                if st.button(f"➕ Add range ({attr}, track {t_id})", key=f"add_{t_id}_{attr}"):
                    st.session_state[key].append({"start": 0, "end": 0})

                st.markdown("---")

# -----------------------------
# APPLY MODIFICATIONS
# -----------------------------
if st.button("5️⃣ Apply Changes and Export XML", type="primary"):

    new_root = ET.fromstring(xml_bytes)

    changed_boxes = 0
    changed_track_attrs = 0

    def get_new_value(attr):
        choice = st.session_state[f"val_choice_{attr}"]
        if choice == "⟶ Custom value":
            return st.session_state[f"custom_val_{attr}"]
        return choice

    for track in new_root.findall(".//track"):

        t_id = track.get("id")
        if t_id not in selected_track_ids:
            continue

        # Update track-level attributes
        for attr in selected_attrs:
            new_val = get_new_value(attr)
            for a in track.findall("attribute"):
                if a.get("name") == attr:
                    a.text = new_val
                    changed_track_attrs += 1

        for attr in selected_attrs:

            new_val = get_new_value(attr)

            # Determine ranges
            if track_selection_mode == "Apply to ALL tracks":
                ranges = st.session_state[f"ranges_global_{attr}"]
            else:
                ranges = st.session_state[f"ranges_{t_id}_{attr}"]

            for box in track.findall("box"):
                frame = int(box.get("frame"))

                # Check if IN ANY RANGE
                apply_here = any(r["start"] <= frame <= r["end"] for r in ranges)

                if apply_here:
                    for a in box.findall("attribute"):
                        if a.get("name") == attr:
                            a.text = new_val
                            changed_boxes += 1

    out = ET.tostring(new_root, encoding="utf-8")

    st.success(
        f"Updated XML:\n"
        f"• Track-level attributes changed: {changed_track_attrs}\n"
        f"• Box-level attributes changed: {changed_boxes}"
    )

    st.download_button(
        "📥 Download Modified XML",
        data=out,
        file_name=f"modified_{uploaded_file.name}",
        mime="application/xml"
    )
