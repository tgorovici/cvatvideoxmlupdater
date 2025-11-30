import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd

st.set_page_config(page_title="CVAT Attribute Range Editor", layout="wide")

st.title("CVAT Video XML Attribute Editor")

st.markdown("""
Upload a CVAT **video XML** (`annotations.xml` from a *video* export), then:

1. Select tracks (all or specific)
2. Select attributes
3. For each attribute:
   - Set a new value
   - Choose scope:
     - Entire track
     - Single frame range
     - Multiple frame ranges
4. Apply and download modified XML.
""")

uploaded_file = st.file_uploader("Upload CVAT video XML (annotations.xml)", type=["xml"])

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
st.write(f"Found **{len(tracks)}** `<track>` elements.")

if not tracks:
    st.error("❌ No <track> elements found. This is probably not a CVAT *video* XML export.")
    st.stop()

# -----------------------------
# COLLECT TRACK + ATTRIBUTE INFO
# -----------------------------
attribute_values = {}   # {attr_name: set(values)}
track_infos = []

for track in tracks:
    t_id = track.get("id", "")
    label = track.get("label", "")
    attrs_in_track = set()

    # Track-level attributes
    for attr in track.findall("attribute"):
        name = attr.get("name")
        if not name:
            continue
        attrs_in_track.add(name)
        attribute_values.setdefault(name, set()).add((attr.text or "").strip())

    # Box-level attributes
    for box in track.findall("box"):
        for attr in box.findall("attribute"):
            name = attr.get("name")
            if not name:
                continue
            attrs_in_track.add(name)
            attribute_values.setdefault(name, set()).add((attr.text or "").strip())

    track_infos.append({
        "Track ID": t_id,
        "Label": label,
        "Attributes": ", ".join(sorted(attrs_in_track)) if attrs_in_track else "",
    })

if not attribute_values:
    st.error("No `<attribute>` elements found under tracks/boxes.")
    st.stop()

st.subheader("Tracks Overview")
st.dataframe(pd.DataFrame(track_infos), use_container_width=True)

# -----------------------------
# 1️⃣ TRACK SELECTION
# -----------------------------
st.subheader("1️⃣ Select Tracks")

track_selection_mode = st.radio(
    "Track selection mode",
    ["Apply to ALL tracks", "Select specific tracks"],
    horizontal=True,
)

track_label_to_id = {
    f"{info['Track ID']} – {info['Label']}": info["Track ID"] for info in track_infos
}

if track_selection_mode == "Select specific tracks":
    selected_track_labels = st.multiselect(
        "Select tracks",
        list(track_label_to_id.keys()),
    )
    if not selected_track_labels:
        st.warning("No tracks selected.")
        st.stop()
    selected_track_ids = {track_label_to_id[lbl] for lbl in selected_track_labels}
else:
    selected_track_labels = []
    selected_track_ids = {info["Track ID"] for info in track_infos}

st.write(f"Tracks chosen: **{len(selected_track_ids)}**")

# -----------------------------
# 2️⃣ ATTRIBUTE SELECTION
# -----------------------------
st.subheader("2️⃣ Select Attributes")

all_attr_names = sorted(attribute_values.keys())
selected_attrs = st.multiselect(
    "Attributes to modify (you can choose multiple):",
    all_attr_names,
)
if not selected_attrs:
    st.info("Select at least one attribute.")
    st.stop()

# -----------------------------
# 3️⃣ NEW VALUE PER ATTRIBUTE
# -----------------------------
st.subheader("3️⃣ New values")

def existing_values_for(attr_name):
    values = attribute_values.get(attr_name, set())
    return sorted(v for v in values if v)

for attr_name in selected_attrs:
    st.markdown(f"### Attribute `{attr_name}`")

    existing_vals = existing_values_for(attr_name)

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

# -----------------------------
# 4️⃣ SCOPES & FRAME RANGES
# -----------------------------
st.subheader("4️⃣ Scope & frame ranges")

# Helper to manage multiple ranges (list of dicts: {"start": int, "end": int})
def ranges_ui(key_prefix: str, label_prefix: str):
    key = f"ranges_{key_prefix}"
    if key not in st.session_state:
        st.session_state[key] = []

    delete_indices = []
    for idx, r in enumerate(st.session_state[key]):
        c1, c2, c3 = st.columns([1, 1, 0.3])
        with c1:
            st.session_state[key][idx]["start"] = st.number_input(
                f"{label_prefix} Start {idx+1}",
                min_value=0,
                value=r["start"],
                step=1,
                key=f"{key_prefix}_start_{idx}",
            )
        with c2:
            st.session_state[key][idx]["end"] = st.number_input(
                f"{label_prefix} End {idx+1}",
                min_value=0,
                value=r["end"],
                step=1,
                key=f"{key_prefix}_end_{idx}",
            )
        with c3:
            if st.button("🗑️", key=f"{key_prefix}_del_{idx}"):
                delete_indices.append(idx)

    for idx in reversed(delete_indices):
        del st.session_state[key][idx]

    if st.button(f"➕ Add range ({label_prefix})", key=f"{key_prefix}_add"):
        st.session_state[key].append({"start": 0, "end": 0})

    return key  # we will retrieve ranges later from session_state[key]


# ---- GLOBAL SCOPES (ALL TRACKS MODE) ----
if track_selection_mode == "Apply to ALL tracks":
    for attr_name in selected_attrs:
        st.markdown(f"### Scope for attribute `{attr_name}` (ALL selected tracks)")

        scope_key = f"scope_global_{attr_name}"
        scope = st.radio(
            f"Scope for `{attr_name}`",
            ["Entire track", "Single frame range", "Multiple frame ranges"],
            horizontal=True,
            key=scope_key,
        )

        if scope == "Single frame range":
            c1, c2 = st.columns(2)
            with c1:
                st.number_input(
                    f"Start frame for `{attr_name}`",
                    min_value=0,
                    value=0,
                    step=1,
                    key=f"single_start_global_{attr_name}",
                )
            with c2:
                st.number_input(
                    f"End frame for `{attr_name}` (inclusive)",
                    min_value=0,
                    value=10,
                    step=1,
                    key=f"single_end_global_{attr_name}",
                )
        elif scope == "Multiple frame ranges":
            ranges_ui(
                key_prefix=f"global_{attr_name}",
                label_prefix=f"{attr_name}",
            )
        st.markdown("---")

# ---- PER-TRACK SCOPES (SPECIFIC TRACKS MODE) ----
else:
    for track_label in selected_track_labels:
        t_id = track_label_to_id[track_label]
        with st.expander(f"Track {track_label} – scopes & ranges"):
            for attr_name in selected_attrs:
                st.markdown(f"**Attribute `{attr_name}`**")

                scope_key = f"scope_{t_id}_{attr_name}"
                scope = st.radio(
                    f"Scope for `{attr_name}` on track {t_id}",
                    ["Entire track", "Single frame range", "Multiple frame ranges"],
                    horizontal=True,
                    key=scope_key,
                )

                if scope == "Single frame range":
                    c1, c2 = st.columns(2)
                    with c1:
                        st.number_input(
                            f"Start frame ({attr_name}, track {t_id})",
                            min_value=0,
                            value=0,
                            step=1,
                            key=f"single_start_{t_id}_{attr_name}",
                        )
                    with c2:
                        st.number_input(
                            f"End frame ({attr_name}, track {t_id})",
                            min_value=0,
                            value=10,
                            step=1,
                            key=f"single_end_{t_id}_{attr_name}",
                        )
                elif scope == "Multiple frame ranges":
                    ranges_ui(
                        key_prefix=f"{t_id}_{attr_name}",
                        label_prefix=f"{attr_name} (track {t_id})",
                    )
                st.markdown("---")

# -----------------------------
# 5️⃣ APPLY CHANGES
# -----------------------------
if st.button("5️⃣ Apply changes and download XML", type="primary"):

    # Helper: get new value for attribute
    def get_new_value(attr_name: str) -> str:
        choice = st.session_state.get(f"value_choice_{attr_name}")
        if choice == "⟶ Custom value":
            return (st.session_state.get(f"custom_value_{attr_name}", "") or "").strip()
        return choice or ""

    # Validate values and ranges
    for attr_name in selected_attrs:
        new_val = get_new_value(attr_name)
        if not new_val:
            st.error(f"Value for attribute `{attr_name}` cannot be empty.")
            st.stop()

        if track_selection_mode == "Apply to ALL tracks":
            scope = st.session_state.get(f"scope_global_{attr_name}", "Entire track")
            if scope == "Single frame range":
                start = st.session_state.get(f"single_start_global_{attr_name}", 0)
                end = st.session_state.get(f"single_end_global_{attr_name}", 0)
                if end < start:
                    st.error(
                        f"For `{attr_name}` (ALL tracks), end frame ({end}) "
                        f"must be >= start frame ({start})."
                    )
                    st.stop()
            elif scope == "Multiple frame ranges":
                ranges_key = f"ranges_global_{attr_name}"
                ranges = st.session_state.get(ranges_key, [])
                for r in ranges:
                    if r["end"] < r["start"]:
                        st.error(
                            f"For `{attr_name}` (ALL tracks), a range has end < start "
                            f"({r['start']} – {r['end']})."
                        )
                        st.stop()
        else:
            # per track
            for track_label in selected_track_labels:
                t_id = track_label_to_id[track_label]
                scope = st.session_state.get(
                    f"scope_{t_id}_{attr_name}",
                    "Entire track"
                )
                if scope == "Single frame range":
                    start = st.session_state.get(f"single_start_{t_id}_{attr_name}", 0)
                    end = st.session_state.get(f"single_end_{t_id}_{attr_name}", 0)
                    if end < start:
                        st.error(
                            f"For `{attr_name}` on track {t_id}, end frame ({end}) "
                            f"must be >= start frame ({start})."
                        )
                        st.stop()
                elif scope == "Multiple frame ranges":
                    ranges_key = f"ranges_{t_id}_{attr_name}"
                    ranges = st.session_state.get(ranges_key, [])
                    for r in ranges:
                        if r["end"] < r["start"]:
                            st.error(
                                f"For `{attr_name}` on track {t_id}, a range has end < start "
                                f"({r['start']} – {r['end']})."
                            )
                            st.stop()

    # Re-parse fresh for modifications
    new_root = ET.fromstring(xml_bytes)

    total_changed_tracks = 0
    total_changed_track_attrs = 0
    total_changed_box_attrs = 0

    for track in new_root.findall(".//track"):
        t_id = track.get("id", "")
        if t_id not in selected_track_ids:
            continue

        track_changed = False

        for attr_name in selected_attrs:
            new_val = get_new_value(attr_name)

            # Determine scope & ranges for this track+attr
            if track_selection_mode == "Apply to ALL tracks":
                scope = st.session_state.get(
                    f"scope_global_{attr_name}",
                    "Entire track"
                )
                if scope == "Entire track":
                    ranges = None  # means "all frames"
                elif scope == "Single frame range":
                    start = st.session_state.get(
                        f"single_start_global_{attr_name}", 0
                    )
                    end = st.session_state.get(
                        f"single_end_global_{attr_name}", 0
                    )
                    ranges = [{"start": start, "end": end}]
                else:  # Multiple frame ranges
                    ranges = st.session_state.get(
                        f"ranges_global_{attr_name}", []
                    )
            else:
                scope = st.session_state.get(
                    f"scope_{t_id}_{attr_name}",
                    "Entire track"
                )
                if scope == "Entire track":
                    ranges = None
                elif scope == "Single frame range":
                    start = st.session_state.get(
                        f"single_start_{t_id}_{attr_name}", 0
                    )
                    end = st.session_state.get(
                        f"single_end_{t_id}_{attr_name}", 0
                    )
                    ranges = [{"start": start, "end": end}]
                else:
                    ranges = st.session_state.get(
                        f"ranges_{t_id}_{attr_name}", []
                    )

            # 1) Track-level attributes: always updated for selected tracks
            for attr in track.findall("attribute"):
                if attr.get("name") == attr_name:
                    attr.text = new_val
                    total_changed_track_attrs += 1
                    track_changed = True

            # 2) Box-level attributes: obey scope/ranges
            boxes = list(track.findall("box"))
            if not boxes:
                continue

            if ranges is None:  # Entire track
                boxes_to_change = boxes
            else:
                boxes_to_change = []
                for box in boxes:
                    try:
                        frame_idx = int(box.get("frame", "0"))
                    except ValueError:
                        frame_idx = 0
                    if any(
                        r["start"] <= frame_idx <= r["end"]
                        for r in ranges
                    ):
                        boxes_to_change.append(box)

            for box in boxes_to_change:
                for attr in box.findall("attribute"):
                    if attr.get("name") == attr_name:
                        attr.text = new_val
                        total_changed_box_attrs += 1
                        track_changed = True

        if track_changed:
            total_changed_tracks += 1

    out_bytes = ET.tostring(new_root, encoding="utf-8")

    st.success(
        f"Done! Modified XML:\n"
        f"- Tracks affected: **{total_changed_tracks}**\n"
        f"- Track-level attributes changed: **{total_changed_track_attrs}**\n"
        f"- Box-level attributes changed: **{total_changed_box_attrs}**"
    )

    st.download_button(
        "📥 Download modified XML",
        data=out_bytes,
        file_name=f"modified_{uploaded_file.name}",
        mime="application/xml",
    )
