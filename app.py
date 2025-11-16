import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd

st.set_page_config(page_title="CVAT Attribute Editor", layout="wide")

st.title("CVAT Video XML Attribute Editor")

st.markdown(
    """
Upload a CVAT **video XML** (`annotations.xml` from a *video* task).  
Then:
1. Choose tracks (or apply to all tracks)  
2. Select **multiple attributes**  
3. For each attribute, set new value + frame scope  
4. Download the modified XML
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
track_infos = []        # list of dicts for display table

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

# -----------------------------
# Track selection (ALL / specific)
# -----------------------------
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

# -----------------------------
# Attribute change rules (multiple)
# -----------------------------
st.subheader("2️⃣ Define attribute changes")

all_attr_names = sorted(attribute_values.keys())

selected_attrs = st.multiselect(
    "Choose attributes to modify (you can select multiple)",
    all_attr_names
)

if not selected_attrs:
    st.info("Select at least one attribute to set up change rules.")
    st.stop()

st.markdown("#### Change rules")

rules = []  # We'll build them from session_state when applying

for attr_name in selected_attrs:
    st.markdown(f"**Attribute: `{attr_name}`**")

    existing_vals = sorted(v for v in attribute_values[attr_name] if v)

    # New value choice
    value_choice = st.selectbox(
        f"New value for `{attr_name}`",
        existing_vals + ["⟶ Custom value"],
        key=f"value_choice_{attr_name}",
    )

    if value_choice == "⟶ Custom value":
        custom_value = st.text_input(
            f"Custom value for `{attr_name}`",
            value="",
            key=f"custom_value_{attr_name}",
        )
    else:
        custom_value = ""

    # Scope
    scope = st.radio(
        f"Where to apply `{attr_name}`?",
        ["Entire track", "First N frames"],
        horizontal=True,
        key=f"scope_{attr_name}",
    )

    if scope == "First N frames":
        num_frames = st.number_input(
            f"N frames for `{attr_name}`",
            min_value=1,
            value=10,
            step=1,
            key=f"num_frames_{attr_name}",
        )
    else:
        num_frames = None

    st.markdown("---")

# -----------------------------
# Apply button
# -----------------------------
if st.button("3️⃣ Apply all changes and generate modified XML", type="primary"):

    # Re-parse fresh root
    root = ET.fromstring(xml_bytes)

    total_changed_tracks = 0
    total_changed_track_attrs = 0
    total_changed_box_attrs = 0

    # Build rules from session state (so they survive rerun)
    rule_objects = []
    for attr_name in selected_attrs:
        value_choice = st.session_state.get(f"value_choice_{attr_name}")
        if value_choice == "⟶ Custom value":
            new_value = (st.session_state.get(f"custom_value_{attr_name}", "") or "").strip()
        else:
            new_value = value_choice

        if not new_value:
            st.error(f"Value for attribute `{attr_name}` cannot be empty.")
            st.stop()

        scope = st.session_state.get(f"scope_{attr_name}", "Entire track")
        num_frames = st.session_state.get(f"num_frames_{attr_name}", None)
        if scope == "First N frames":
            if not num_frames or num_frames <= 0:
                st.error(f"Invalid N for attribute `{attr_name}`.")
                st.stop()
        else:
            num_frames = None

        rule_objects.append({
            "attr_name": attr_name,
            "new_value": new_value,
            "scope": scope,
            "num_frames": num_frames,
        })

    # Apply rules
    for track in root.findall(".//track"):
        t_id = track.get("id", "")
        if t_id not in selected_track_ids:
            continue

        track_changed_in_any_rule = False

        for rule in rule_objects:
            attr_name = rule["attr_name"]
            new_value = rule["new_value"]
            scope = rule["scope"]
            num_frames = rule["num_frames"]

            # Track-level attributes
            for attr in track.findall("attribute"):
                if attr.get("name") == attr_name:
                    attr.text = new_value
                    total_changed_track_attrs += 1
                    track_changed_in_any_rule = True

            # Box-level attributes
            boxes = list(track.findall("box"))
            if not boxes:
                continue

            if scope == "Entire track":
                boxes_to_change = boxes
            else:
                boxes_sorted = sorted(
                    boxes,
                    key=lambda b: int(b.get("frame", "0"))
                )
                boxes_to_change = boxes_sorted[: int(num_frames)]

            for box in boxes_to_change:
                for attr in box.findall("attribute"):
                    if attr.get("name") == attr_name:
                        attr.text = new_value
                        total_changed_box_attrs += 1
                        track_changed_in_any_rule = True

        if track_changed_in_any_rule:
            total_changed_tracks += 1

    out_bytes = ET.tostring(root, encoding="utf-8")

    st.success(
        f"Done! Applied **{len(rule_objects)} change rule(s)**.\n\n"
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
