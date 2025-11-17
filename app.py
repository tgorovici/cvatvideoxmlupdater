import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd

st.set_page_config(page_title="CVAT Attribute Editor", layout="wide")

st.title("CVAT Video XML Attribute Editor")

st.markdown(
    """
Upload a CVAT **video XML** (`annotations.xml` from a *video* task).  

Then:

1. Choose tracks (ALL tracks or specific tracks)  
2. Select **one or more attributes**  
3. For each attribute:
   - Set a new value  
   - Define scope:
     - Entire track, or  
     - Frame range (start–end)  
       - If using **ALL tracks** mode → one range for all tracks  
       - If using **Select specific tracks** mode → a separate range **per track**  
4. Download the modified XML.
"""
)

uploaded_file = st.file_uploader("Upload CVAT video XML file", type=["xml"])

if not uploaded_file:
    st.info("👆 Upload a CVAT video XML file to get started.")
    st.stop()

xml_bytes = uploaded_file.getvalue()

# -----------------------------
# Parse XML
# -----------------------------
try:
    root = ET.fromstring(xml_bytes)
except ET.ParseError as e:
    st.error(f"❌ Failed to parse XML: {e}")
    st.stop()

st.subheader("Debug Info")
st.write(f"Root tag: `{root.tag}`")

tracks = root.findall(".//track")
st.write(f"Found **{len(tracks)}** `<track>` elements.")

if not tracks:
    st.error("No `<track>` found. This is probably not a CVAT *video* XML export.")
    st.stop()

# -----------------------------
# Collect track & attribute info
# -----------------------------
attribute_values = {}   # {attr_name: set(values)}
track_infos = []        # list of dicts for display

for track in tracks:
    t_id = track.get("id", "")
    label = track.get("label", "")
    attr_names = set()

    # Track-level attributes
    for attr in track.findall("attribute"):
        name = attr.get("name")
        if not name:
            continue
        attr_names.add(name)
        attribute_values.setdefault(name, set()).add((attr.text or "").strip())

    # Box-level attributes
    for box in track.findall("box"):
        for attr in box.findall("attribute"):
            name = attr.get("name")
            if not name:
                continue
            attr_names.add(name)
            attribute_values.setdefault(name, set()).add((attr.text or "").strip())

    track_infos.append({
        "Track ID": t_id,
        "Label": label,
        "Attributes in track": ", ".join(sorted(attr_names)) if attr_names else "",
    })

if not attribute_values:
    st.error("No `<attribute>` elements found under tracks/boxes.")
    st.stop()

st.subheader("Tracks Overview")
st.dataframe(pd.DataFrame(track_infos), use_container_width=True)

# ======================================================
# 1️⃣ TRACK SELECTION MODE
# ======================================================
st.subheader("1️⃣ Select tracks")

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
        "Select tracks",
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

# ======================================================
# 2️⃣ ATTRIBUTE CHANGE RULES (MULTIPLE ATTRIBUTES)
# ======================================================
st.subheader("2️⃣ Define attribute changes")

all_attr_names = sorted(attribute_values.keys())

selected_attrs = st.multiselect(
    "Choose attributes to modify (you can select multiple)",
    all_attr_names
)

if not selected_attrs:
    st.info("Select at least one attribute to set up change rules.")
    st.stop()

st.markdown("#### New values per attribute")

# Step A: define NEW VALUE for each attribute (same for all tracks)
for attr_name in selected_attrs:
    st.markdown(f"**Attribute: `{attr_name}`**")

    existing_vals = sorted(v for v in attribute_values[attr_name] if v)

    value_choice = st.selectbox(
        f"New value for `{attr_name}`",
        existing_vals + ["⟶ Custom value"],
        key=f"value_choice_{attr_name}",
    )

    if value_choice == "⟶ Custom value":
        st.text_input(
            f"Custom value for `{attr_name}`",
            value="",
            key=f"custom_value_{attr_name}",
        )

    st.markdown("---")

# Step B: define SCOPE (frame ranges) – depends on track selection mode
st.subheader("3️⃣ Define frame scope per attribute")

if track_selection_mode == "Apply to ALL tracks":
    # One scope per attribute, applied to all selected tracks
    for attr_name in selected_attrs:
        st.markdown(f"**Scope for attribute `{attr_name}` (ALL selected tracks)**")

        scope = st.radio(
            f"Where to apply `{attr_name}`?",
            ["Entire track", "Frame range (start–end, inclusive)"],
            horizontal=True,
            key=f"scope_global_{attr_name}",
        )

        if scope == "Frame range (start–end, inclusive)":
            col_start, col_end = st.columns(2)
            with col_start:
                st.number_input(
                    f"Start frame for `{attr_name}`",
                    min_value=0,
                    value=0,
                    step=1,
                    key=f"start_global_{attr_name}",
                )
            with col_end:
                st.number_input(
                    f"End frame for `{attr_name}` (inclusive)",
                    min_value=0,
                    value=10,
                    step=1,
                    key=f"end_global_{attr_name}",
                )
        st.markdown("---")

else:
    # Per-track scope: for each selected track AND each attribute
    for track_label in selected_track_labels:
        t_id = track_label_to_id[track_label]
        with st.expander(f"Track {track_label} – frame ranges"):
            for attr_name in selected_attrs:
                st.markdown(f"*Attribute `{attr_name}`*")

                scope = st.radio(
                    f"Scope for `{attr_name}` on track {t_id}",
                    ["Entire track", "Frame range (start–end, inclusive)"],
                    horizontal=True,
                    key=f"scope_{t_id}_{attr_name}",
                )

                if scope == "Frame range (start–end, inclusive)":
                    col_start, col_end = st.columns(2)
                    with col_start:
                        st.number_input(
                            f"Start frame ({attr_name}, track {t_id})",
                            min_value=0,
                            value=0,
                            step=1,
                            key=f"start_{t_id}_{attr_name}",
                        )
                    with col_end:
                        st.number_input(
                            f"End frame ({attr_name}, track {t_id})",
                            min_value=0,
                            value=10,
                            step=1,
                            key=f"end_{t_id}_{attr_name}",
                        )
                st.markdown("---")

# ======================================================
# 4️⃣ APPLY BUTTON
# ======================================================
if st.button("4️⃣ Apply all changes and generate modified XML", type="primary"):

    # Fresh root for modification
    root = ET.fromstring(xml_bytes)

    total_changed_tracks = 0
    total_changed_track_attrs = 0
    total_changed_box_attrs = 0

    # Helper: get new value for an attribute
    def get_new_value(attr_name: str) -> str:
        val_choice = st.session_state.get(f"value_choice_{attr_name}")
        if val_choice == "⟶ Custom value":
            return (st.session_state.get(f"custom_value_{attr_name}", "") or "").strip()
        return val_choice

    # Validate values and frame ranges
    for attr_name in selected_attrs:
        new_val = get_new_value(attr_name)
        if not new_val:
            st.error(f"Value for attribute `{attr_name}` cannot be empty.")
            st.stop()

        if track_selection_mode == "Apply to ALL tracks":
            scope = st.session_state.get(f"scope_global_{attr_name}", "Entire track")
            if scope == "Frame range (start–end, inclusive)":
                start = st.session_state.get(f"start_global_{attr_name}", 0)
                end = st.session_state.get(f"end_global_{attr_name}", 0)
                if end < start:
                    st.error(
                        f"For `{attr_name}` (ALL tracks), end frame ({end}) "
                        f"must be >= start frame ({start})."
                    )
                    st.stop()
        else:
            for track_label in selected_track_labels:
                t_id = track_label_to_id[track_label]
                scope = st.session_state.get(f"scope_{t_id}_{attr_name}", "Entire track")
                if scope == "Frame range (start–end, inclusive)":
                    start = st.session_state.get(f"start_{t_id}_{attr_name}", 0)
                    end = st.session_state.get(f"end_{t_id}_{attr_name}", 0)
                    if end < start:
                        st.error(
                            f"For `{attr_name}` on track {t_id}, end frame ({end}) "
                            f"must be >= start frame ({start})."
                        )
                        st.stop()

    # =========================
    # MAIN APPLY LOOP
    # =========================
    for track in root.findall(".//track"):
        t_id = track.get("id", "")
        if t_id not in selected_track_ids:
            continue

        track_changed = False

        for attr_name in selected_attrs:
            new_value = get_new_value(attr_name)

            # Determine scope & frame range for this track + attr
            if track_selection_mode == "Apply to ALL tracks":
                scope = st.session_state.get(f"scope_global_{attr_name}", "Entire track")
                if scope == "Frame range (start–end, inclusive)":
                    start_frame = st.session_state.get(f"start_global_{attr_name}", 0)
                    end_frame = st.session_state.get(f"end_global_{attr_name}", 0)
                else:
                    start_frame = None
                    end_frame = None
            else:
                scope = st.session_state.get(
                    f"scope_{t_id}_{attr_name}", "Entire track"
                )
                if scope == "Frame range (start–end, inclusive)":
                    start_frame = st.session_state.get(f"start_{t_id}_{attr_name}", 0)
                    end_frame = st.session_state.get(f"end_{t_id}_{attr_name}", 0)
                else:
                    start_frame = None
                    end_frame = None

            # 1) Track-level attributes - always apply when track is selected
            for attr in track.findall("attribute"):
                if attr.get("name") == attr_name:
                    attr.text = new_value
                    total_changed_track_attrs += 1
                    track_changed = True

            # 2) Box-level attributes - respect frame scope
            boxes = list(track.findall("box"))
            if not boxes:
                continue

            if scope == "Entire track":
                boxes_to_change = boxes
            else:
                boxes_to_change = []
                for box in boxes:
                    try:
                        frame_idx = int(box.get("frame", "0"))
                    except ValueError:
                        frame_idx = 0
                    if start_frame <= frame_idx <= end_frame:
                        boxes_to_change.append(box)

            for box in boxes_to_change:
                for attr in box.findall("attribute"):
                    if attr.get("name") == attr_name:
                        attr.text = new_value
                        total_changed_box_attrs += 1
                        track_changed = True

        if track_changed:
            total_changed_tracks += 1

    out_bytes = ET.tostring(root, encoding="utf-8")

    st.success(
        f"Done! Applied changes for {len(selected_attrs)} attribute(s).\n\n"
        f"- Tracks affected: **{total_changed_tracks}**\n"
        f"- Track-level attributes changed: **{total_changed_track_attrs}**\n"
        f"- Box-level attributes changed: **{total_changed_box_attrs}**"
    )

    st.download_button(
        "📥 Download modified XML",
        data=out_bytes,
        file_name=f"modified_{uploaded_file.name}",
        mime="application/xml"
    )
