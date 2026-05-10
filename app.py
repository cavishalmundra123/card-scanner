"""Card Scanner - Streamlit UI with username+password authentication.

Auth: streamlit-authenticator (local YAML credentials, bcrypt hashed).
Per-user data isolation: stored in cloud_db using user_email from credentials.
"""

import os
import yaml
from yaml.loader import SafeLoader
import streamlit as st
import streamlit_authenticator as stauth
import pandas as pd

import cloud_db as db
from card_processor import process_file, SERVICE_CATEGORIES

st.set_page_config(page_title="Card Scanner", page_icon="CARD", layout="wide")

UPLOAD_TMP = os.path.join("data", "_uploads")
os.makedirs(UPLOAD_TMP, exist_ok=True)

FIELDS = [
    ("full_name", "Full Name"),
    ("designation", "Designation"),
    ("company_name", "Company Name"),
    ("service_category", "Service Category"),
    ("email", "Email"),
    ("phone_primary", "Phone (Primary)"),
    ("phone_secondary", "Phone (Secondary)"),
    ("whatsapp", "WhatsApp"),
    ("website", "Website"),
    ("address_line", "Address Line"),
    ("area", "Area / Locality"),
    ("city", "City"),
    ("state", "State"),
    ("country", "Country"),
    ("postal_code", "Postal Code"),
    ("social_linkedin", "LinkedIn"),
    ("notes", "Notes"),
]


@st.cache_resource
def load_authenticator():
    """Load credentials from credentials.yaml and build the authenticator."""
    with open("credentials.yaml", "r", encoding="utf-8") as f:
        config = yaml.load(f, Loader=SafeLoader)

    authenticator = stauth.Authenticate(
        config["credentials"],
        config["cookie"]["name"],
        config["cookie"]["key"],
        config["cookie"]["expiry_days"],
    )
    return authenticator, config


authenticator, config = load_authenticator()

# Render the login form
try:
    authenticator.login(location="main")
except Exception as e:
    st.error(f"Login error: {e}")
    st.stop()

# Check authentication status
auth_status = st.session_state.get("authentication_status")

if auth_status is False:
    st.error("Username or password is incorrect.")
    st.stop()
elif auth_status is None:
    st.warning("Please enter your username and password.")
    st.info(
        "If you don't have credentials, contact the admin "
        "(cavishalmundra123@gmail.com)."
    )
    st.stop()

# Logged in successfully
username = st.session_state["username"]
name = st.session_state["name"]
user_email = config["credentials"]["usernames"][username]["email"]


def render_edit_form(prefix, initial, allow_notes=True):
    edited = {}
    col1, col2 = st.columns(2)
    half = len(FIELDS) // 2
    for i, (key, label) in enumerate(FIELDS):
        if not allow_notes and key == "notes":
            continue
        target_col = col1 if i < half else col2
        with target_col:
            if key == "service_category":
                current = initial.get(key) or "Other"
                if current not in SERVICE_CATEGORIES:
                    current = "Other"
                edited[key] = st.selectbox(label, SERVICE_CATEGORIES,
                    index=SERVICE_CATEGORIES.index(current), key=f"{prefix}_{key}")
            elif key == "notes":
                edited[key] = st.text_area(label, value=initial.get(key) or "",
                    key=f"{prefix}_{key}", height=80)
            else:
                edited[key] = st.text_input(label, value=initial.get(key) or "",
                    key=f"{prefix}_{key}")
    return edited


with st.sidebar:
    st.title("Card Scanner")
    st.caption(f"Logged in as: **{name}**")
    st.caption(f"({user_email})")
    authenticator.logout(location="sidebar", button_name="Log out")
    st.markdown("---")
    st.metric("My Contacts", db.get_count(user_email))
    st.markdown("---")
    st.subheader("Excel Backup")
    try:
        excel_bytes = db.build_excel_bytes(user_email)
        st.download_button("Download My Contacts (Excel)", excel_bytes,
            file_name=f"contacts_{user_email.replace('@', '_at_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True)
    except Exception as e:
        st.error(f"Excel build failed: {e}")
    st.markdown("---")
    st.caption("Tip: For best results, scan 3-4 cards per A4 page at 300 DPI.")


tab1, tab2, tab3 = st.tabs(["Upload & Scan", "Search", "All Contacts"])


with tab1:
    st.header("Upload PDF or Image")
    st.caption("Supported: PDF, PNG, JPG. Cards are auto-detected.")
    uploaded = st.file_uploader("Choose a file",
        type=["pdf", "png", "jpg", "jpeg", "webp", "bmp"], key="uploader")

    if uploaded is not None:
        tmp_path = os.path.join(UPLOAD_TMP, uploaded.name)
        with open(tmp_path, "wb") as f:
            f.write(uploaded.getbuffer())

        if st.button("Process File", type="primary"):
            with st.spinner("Detecting cards and extracting via Gemini..."):
                try:
                    results = process_file(tmp_path, user_email)
                    st.session_state["scan_results"] = results
                    st.success(f"Found {len(results)} card(s).")
                except Exception as e:
                    st.error(f"Processing failed: {e}")
                    st.session_state.pop("scan_results", None)

        results = st.session_state.get("scan_results", [])
        if results:
            st.markdown("---")
            unsaved = [r for r in results if not r.get("_saved")]
            st.subheader(f"Review Cards ({len(unsaved)} pending of {len(results)})")

            if len(unsaved) > 1:
                if st.button(f"Save All {len(unsaved)} Cards", type="primary", key="save_all"):
                    saved_count = 0
                    for idx, item in enumerate(results):
                        if item.get("_saved"):
                            continue
                        prefix = f"scan_{idx}"
                        record = {}
                        for key, _ in FIELDS:
                            session_key = f"{prefix}_{key}"
                            record[key] = st.session_state.get(session_key) or item["data"].get(key)
                        record["card_image_path"] = item["image_path"]
                        db.insert_contact(user_email, record)
                        item["_saved"] = True
                        saved_count += 1
                    st.success(f"Saved {saved_count} contacts.")
                    st.rerun()

            for idx, item in enumerate(results):
                if item.get("_saved"):
                    continue
                with st.expander(
                    f"Card {idx + 1} - {item['data'].get('full_name') or '(no name)'} @ {item['data'].get('company_name') or '(no company)'}",
                    expanded=True):
                    img_col, form_col = st.columns([1, 2])
                    with img_col:
                        signed_url = db.get_card_image_url(item["image_path"])
                        if signed_url:
                            st.image(signed_url, use_container_width=True)
                        st.caption(f"Page {item.get('page', 1)}")
                        if "_extraction_error" in item["data"]:
                            st.error(f"Extraction error: {item['data']['_extraction_error']}")
                    with form_col:
                        edited = render_edit_form(prefix=f"scan_{idx}",
                            initial=item["data"], allow_notes=True)
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("Save to Database", key=f"save_{idx}", type="primary"):
                                edited["card_image_path"] = item["image_path"]
                                new_id = db.insert_contact(user_email, edited)
                                item["_saved"] = True
                                st.success(f"Saved as contact #{new_id}")
                                st.rerun()
                        with c2:
                            if st.button("Discard", key=f"discard_{idx}"):
                                item["_saved"] = True
                                st.info("Discarded.")
                                st.rerun()

            st.markdown("---")
            if st.button("Clear all results"):
                st.session_state.pop("scan_results", None)
                st.rerun()


with tab2:
    st.header("Search My Contacts")
    existing_categories = db.get_distinct_values(user_email, "service_category")
    category_options = ["All"] + sorted(set(SERVICE_CATEGORIES) | set(existing_categories))
    country_options = ["All"] + db.get_distinct_values(user_email, "country")

    f1, f2, f3, f4 = st.columns(4)
    with f1:
        sel_category = st.selectbox("Service Category", category_options)
    with f2:
        sel_country = st.selectbox("Country", country_options)
    with f3:
        sel_city = st.text_input("City (contains)")
    with f4:
        sel_area = st.text_input("Area (contains)")

    sel_keyword = st.text_input("Keyword (name, company, email, phone, notes)")

    results = db.search_contacts(user_email, category=sel_category,
        country=sel_country, city=sel_city, area=sel_area, keyword=sel_keyword)

    st.markdown(f"**{len(results)} result(s)**")
    if results:
        df = pd.DataFrame(results)
        display_cols = ["id", "full_name", "designation", "company_name",
            "service_category", "phone_primary", "email", "city", "country"]
        display_cols = [c for c in display_cols if c in df.columns]
        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Download as CSV", csv, "contacts_search.csv", "text/csv")


with tab3:
    st.header("All My Contacts")
    contacts = db.get_all_contacts(user_email)
    if not contacts:
        st.info("No contacts yet. Upload a file in the 'Upload & Scan' tab.")
    else:
        df_all = pd.DataFrame(contacts)
        s1, s2, s3 = st.columns(3)
        with s1:
            st.metric("Total", len(df_all))
        with s2:
            uc = df_all["company_name"].dropna().nunique() if "company_name" in df_all else 0
            st.metric("Unique Companies", uc)
        with s3:
            uco = df_all["country"].dropna().nunique() if "country" in df_all else 0
            st.metric("Countries", uco)

        display_cols = ["id", "full_name", "designation", "company_name",
            "service_category", "phone_primary", "email", "city", "country", "created_at"]
        display_cols = [c for c in display_cols if c in df_all.columns]
        st.dataframe(df_all[display_cols], use_container_width=True, hide_index=True)

        csv_all = df_all.to_csv(index=False).encode("utf-8")
        st.download_button("Export All as CSV", csv_all, "contacts_all.csv", "text/csv")

        st.markdown("---")
        st.subheader("Edit / Delete Contact")
        ids = [c["id"] for c in contacts]
        labels = [f"#{c['id']} - {c.get('full_name') or '(no name)'} @ {c.get('company_name') or '(no company)'}" for c in contacts]
        sel_idx = st.selectbox("Select a contact", range(len(ids)),
            format_func=lambda i: labels[i])
        sel_contact = contacts[sel_idx]

        img_col, form_col = st.columns([1, 2])
        with img_col:
            img_path = sel_contact.get("card_image_path")
            if img_path:
                signed_url = db.get_card_image_url(img_path)
                if signed_url:
                    st.image(signed_url, use_container_width=True)
                else:
                    st.caption("Image link expired.")
            else:
                st.caption("No card image available.")
        with form_col:
            edited = render_edit_form(prefix=f"edit_{sel_contact['id']}",
                initial=sel_contact, allow_notes=True)
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Update Contact", type="primary", key=f"upd_{sel_contact['id']}"):
                    db.update_contact(user_email, sel_contact["id"], edited)
                    st.success("Updated.")
                    st.rerun()
            with c2:
                if st.button("Delete Contact", key=f"del_{sel_contact['id']}"):
                    db.delete_contact(user_email, sel_contact["id"])
                    st.success(f"Deleted contact #{sel_contact['id']}.")
                    st.rerun()
