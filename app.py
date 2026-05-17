"""Card Scanner - Streamlit UI with Supabase-based authentication."""

import os
import streamlit as st
import pandas as pd
from streamlit_option_menu import option_menu

import cloud_db as db
from card_processor import process_file, SERVICE_CATEGORIES
from ui_components import (
    load_css, render_app_header, render_section_header,
    render_user_card, render_stat_card, render_sidebar_label,
    render_tip, ICON_UPLOAD, ICON_SEARCH, ICON_CONTACTS,
    ICON_KEY, ICON_DOWNLOAD,
)

st.set_page_config(
    page_title="Card Scanner",
    page_icon="💼",  # browser tab favicon only — not visible inside app
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject custom CSS (call once, near the top)
load_css("static/style.css")

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


# ── Login Page ────────────────────────────────────────────────────────────────

def show_login():
    render_app_header()
    st.markdown("### Sign in")
    username = st.text_input("Username").strip().lower()
    password = st.text_input("Password", type="password")

    if st.button("Login", type="primary"):
        if not username or not password:
            st.error("Please enter both username and password.")
            return
        user = db.get_user(username)
        if not user:
            st.error("Invalid username or password.")
            return
        if not db.verify_password(password, user["password_hash"]):
            st.error("Invalid username or password.")
            return
        # Success
        st.session_state["authenticated"] = True
        st.session_state["username"] = user["username"]
        st.session_state["user_email"] = user["email"]
        st.session_state["must_change_password"] = user.get("must_change_password", False)
        st.rerun()

    st.caption("Contact admin if you need access: cavishalmundra123@gmail.com")


# ── Change Password Page ──────────────────────────────────────────────────────

def show_change_password():
    render_app_header()
    st.markdown("### Change your password")
    st.info("You must set a new password before continuing.")
    username = st.session_state["username"]

    new_pass = st.text_input("New Password", type="password")
    confirm_pass = st.text_input("Confirm New Password", type="password")

    if st.button("Set New Password", type="primary"):
        if len(new_pass) < 8:
            st.error("Password must be at least 8 characters.")
            return
        if new_pass != confirm_pass:
            st.error("Passwords do not match.")
            return
        success = db.update_password(username, new_pass)
        if success:
            st.session_state["must_change_password"] = False
            st.success("Password updated! Loading your dashboard...")
            st.rerun()
        else:
            st.error("Update failed. Please try again.")


# ── Auth Gate ─────────────────────────────────────────────────────────────────

if not st.session_state.get("authenticated"):
    show_login()
    st.stop()

if st.session_state.get("must_change_password"):
    show_change_password()
    st.stop()

# Authenticated — load main app
username = st.session_state["username"]
user_email = st.session_state["user_email"]


# ── Helper ────────────────────────────────────────────────────────────────────

@st.dialog("Card Details")
def _show_card_dialog(contact):
    """Popup dialog: card image on top, contact details below."""
    name = contact.get("full_name") or "(no name)"
    company = contact.get("company_name") or "-"

    img_path = contact.get("card_image_path")
    if img_path:
        signed_url = db.get_card_image_url(img_path)
        if signed_url:
            st.image(signed_url, use_container_width=True)
        else:
            st.caption("Image link expired.")
    else:
        st.caption("No card image available.")

    st.markdown(f"### {name}")
    if contact.get("designation"):
        st.markdown(f"*{contact['designation']}*")
    st.markdown(f"**{company}**")
    st.markdown("---")

    # Show all non-empty fields as a clean list
    detail_fields = [
        ("Service Category", "service_category"),
        ("Email", "email"),
        ("Phone (Primary)", "phone_primary"),
        ("Phone (Secondary)", "phone_secondary"),
        ("WhatsApp", "whatsapp"),
        ("Website", "website"),
        ("Address", "address_line"),
        ("Area", "area"),
        ("City", "city"),
        ("State", "state"),
        ("Country", "country"),
        ("Postal Code", "postal_code"),
        ("LinkedIn", "social_linkedin"),
        ("Notes", "notes"),
    ]
    for label, key in detail_fields:
        val = contact.get(key)
        if val:
            st.markdown(f"**{label}:** {val}")


def render_contact_rows(contacts, key_prefix):
    """Render contacts as custom rows, each with a 'View Card' button.
    Clicking a button opens a popup dialog with the card image and details.

    Note: S.No. shown to the user is computed per-user, oldest = 1.
    The real database 'id' is still used internally for unique button keys.
    """
    # Compute stable S.No. per user (oldest = 1). We sort by id ascending
    # (since IDs are auto-incremented in insertion order), then map id -> sno.
    sno_map = {
        c["id"]: i + 1
        for i, c in enumerate(sorted(contacts, key=lambda x: x["id"]))
    }

    # Column width ratios: S.No, Name, Company, Category, Phone, Email, City, Country, Card
    col_widths = [0.8, 2, 2.3, 1.6, 1.8, 2.3, 1.2, 1.2, 1.5]

    # Header row
    h = st.columns(col_widths)
    h[0].markdown("**S.No**")
    h[1].markdown("**Name**")
    h[2].markdown("**Company**")
    h[3].markdown("**Category**")
    h[4].markdown("**Phone**")
    h[5].markdown("**Email**")
    h[6].markdown("**City**")
    h[7].markdown("**Country**")
    h[8].markdown("**Card**")
    st.markdown(
        "<hr style='margin:4px 0; border:none; border-top:1px solid #e2e8f0;'>",
        unsafe_allow_html=True,
    )

    for contact in contacts:
        cid = contact["id"]
        sno = sno_map[cid]
        name = contact.get("full_name") or "(no name)"
        company = contact.get("company_name") or "-"
        category = contact.get("service_category") or "-"
        phone = contact.get("phone_primary") or "-"
        email = contact.get("email") or "-"
        city = contact.get("city") or "-"
        country = contact.get("country") or "-"

        row = st.columns(col_widths)
        row[0].write(str(sno))
        row[1].write(name)
        row[2].write(company)
        row[3].write(category)
        row[4].write(phone)
        row[5].write(email)
        row[6].write(city)
        row[7].write(country)
        if row[8].button("View Card", key=f"{key_prefix}_view_{cid}"):
            _show_card_dialog(contact)

        st.markdown(
            "<hr style='margin:4px 0; border:none; border-top:1px solid #f1f5f9;'>",
            unsafe_allow_html=True,
        )


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


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    # User identity card
    render_user_card(username, user_email)

    # Hero stat card
    contact_count = db.get_count(user_email)
    render_stat_card("My Contacts", contact_count)

    # Log out
    if st.button("Log out", use_container_width=True, type="secondary"):
        st.session_state.clear()
        st.rerun()

    # Tools section
    render_sidebar_label("Tools", ICON_DOWNLOAD)
    try:
        excel_bytes = db.build_excel_bytes(user_email)
        st.download_button(
            "Download Excel Backup",
            excel_bytes,
            file_name=f"contacts_{user_email.replace('@', '_at_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    except Exception as e:
        st.error(f"Excel build failed: {e}")

    # Account section
    render_sidebar_label("Account", ICON_KEY)
    with st.expander("Change password"):
        cp_current = st.text_input("Current password", type="password", key="cp_current")
        cp_new = st.text_input("New password", type="password", key="cp_new")
        cp_confirm = st.text_input("Confirm new password", type="password", key="cp_confirm")
        if st.button("Update password", key="cp_btn", type="primary", use_container_width=True):
            user = db.get_user(username)
            if not db.verify_password(cp_current, user["password_hash"]):
                st.error("Current password is incorrect.")
            elif len(cp_new) < 8:
                st.error("New password must be at least 8 characters.")
            elif cp_new != cp_confirm:
                st.error("New passwords do not match.")
            else:
                db.update_password(username, cp_new)
                st.success("Password updated!")

    # Tip card
    render_tip("For best scans, fit 3-4 cards per A4 page at 300 DPI.")


# ── Main Header + Top Nav ─────────────────────────────────────────────────────

render_app_header()

selected_tab = option_menu(
    menu_title=None,
    options=["Upload & Scan", "Search", "All Contacts"],
    icons=["cloud-upload", "search", "people"],
    orientation="horizontal",
    default_index=0,
    styles={
        "container": {
            "padding": "0!important",
            "background-color": "transparent",
            "margin-bottom": "1.5rem",
            "border-bottom": "1px solid #e2e8f0",
        },
        "icon": {"color": "#64748b", "font-size": "16px"},
        "nav-link": {
            "font-size": "0.95rem",
            "text-align": "center",
            "margin": "0 4px",
            "padding": "12px 20px",
            "color": "#64748b",
            "background-color": "transparent",
            "border-radius": "6px 6px 0 0",
            "border-bottom": "2px solid transparent",
        },
        "nav-link-selected": {
            "background-color": "transparent",
            "color": "#1f4e79",
            "font-weight": "600",
            "border-bottom": "2px solid #1f4e79",
            "border-radius": "0",
        },
    },
)


# ── Tab 1: Upload & Scan ──────────────────────────────────────────────────────

if selected_tab == "Upload & Scan":
    render_section_header(
        "Scan Card",
        "Take a photo or upload a file. Cards are auto-detected.",
        ICON_UPLOAD,
    )

    scan_tab1, scan_tab2 = st.tabs(["Upload File", "Camera"])

    uploaded = None
    tmp_path = None

    with scan_tab1:
        upload_file = st.file_uploader("Choose a file",
            type=["pdf", "png", "jpg", "jpeg", "webp", "bmp"], key="uploader")
        if upload_file is not None:
            tmp_path = os.path.join(UPLOAD_TMP, upload_file.name)
            with open(tmp_path, "wb") as f:
                f.write(upload_file.getbuffer())
            uploaded = upload_file

    with scan_tab2:
        camera_img = st.camera_input("Point camera at business card", key="camera")
        if camera_img is not None:
            from datetime import datetime
            filename = f"camera_capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            tmp_path = os.path.join(UPLOAD_TMP, filename)
            with open(tmp_path, "wb") as f:
                f.write(camera_img.getbuffer())
            uploaded = camera_img

    if uploaded is not None:
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
                    skipped_dups = 0
                    for idx, item in enumerate(results):
                        if item.get("_saved"):
                            continue
                        prefix = f"scan_{idx}"
                        record = {}
                        for key, _ in FIELDS:
                            session_key = f"{prefix}_{key}"
                            record[key] = st.session_state.get(session_key) or item["data"].get(key)
                        # Skip cards with duplicates — user must resolve those individually
                        dup_check = db.find_duplicate(
                            user_email,
                            phone_primary=record.get("phone_primary", "") or "",
                            phone_secondary=record.get("phone_secondary", "") or "",
                            whatsapp=record.get("whatsapp", "") or "",
                            email=record.get("email", "") or "",
                        )
                        if dup_check:
                            skipped_dups += 1
                            continue
                        record["card_image_path"] = item["image_path"]
                        db.insert_contact(user_email, record)
                        item["_saved"] = True
                        saved_count += 1
                    if skipped_dups:
                        st.success(f"Saved {saved_count} contacts. Skipped {skipped_dups} possible duplicate(s) - please review below.")
                    else:
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

                        # ---- Duplicate detection ----
                        dup_inputs = (
                            (edited.get("phone_primary") or "").strip(),
                            (edited.get("phone_secondary") or "").strip(),
                            (edited.get("whatsapp") or "").strip(),
                            (edited.get("email") or "").strip().lower(),
                        )
                        dup_cache_key = f"dup_{idx}_{hash(dup_inputs)}"
                        if dup_cache_key not in st.session_state:
                            st.session_state[dup_cache_key] = db.find_duplicate(
                                user_email,
                                phone_primary=dup_inputs[0],
                                phone_secondary=dup_inputs[1],
                                whatsapp=dup_inputs[2],
                                email=dup_inputs[3],
                            )
                        duplicate = st.session_state[dup_cache_key]

                        # ---- Warning + choice if duplicate ----
                        dup_choice = "new"  # default
                        if duplicate:
                            dup_name = duplicate.get("full_name") or "(no name)"
                            dup_company = duplicate.get("company_name") or "(no company)"
                            dup_phone = duplicate.get("phone_primary") or duplicate.get("phone_secondary") or duplicate.get("whatsapp") or ""
                            dup_email = duplicate.get("email") or ""
                            st.warning(
                                f"⚠️ **Possible duplicate found**\n\n"
                                f"**{dup_name}** @ {dup_company}\n\n"
                                f"Phone: `{dup_phone}` | Email: `{dup_email}`"
                            )
                            dup_choice = st.radio(
                                "What would you like to do?",
                                options=["update", "new"],
                                format_func=lambda x: "Update existing contact" if x == "update" else "Save as new contact (intentional duplicate)",
                                key=f"dup_choice_{idx}",
                                horizontal=False,
                            )

                        # ---- Save / Discard buttons ----
                        save_label = "Update Existing" if (duplicate and dup_choice == "update") else "Save to Database"
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button(save_label, key=f"save_{idx}", type="primary"):
                                if duplicate and dup_choice == "update":
                                    edited["card_image_path"] = item["image_path"]
                                    ok = db.update_contact_partial(user_email, duplicate["id"], edited)
                                    if ok:
                                        item["_saved"] = True
                                        st.success("Updated existing contact.")
                                        st.rerun()
                                    else:
                                        st.error("Update failed. Check console.")
                                else:
                                    edited["card_image_path"] = item["image_path"]
                                    new_id = db.insert_contact(user_email, edited)
                                    item["_saved"] = True
                                    st.success("Contact saved.")
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


# ── Tab 2: Search ─────────────────────────────────────────────────────────────

elif selected_tab == "Search":
    render_section_header(
        "Search My Contacts",
        "Find contacts by name, company, phone, or any field.",
        ICON_SEARCH,
    )
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
        render_contact_rows(results, key_prefix="search")
        df = pd.DataFrame(results)
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Download as CSV", csv, "contacts_search.csv", "text/csv")


# ── Tab 3: All Contacts ───────────────────────────────────────────────────────

elif selected_tab == "All Contacts":
    render_section_header(
        "All My Contacts",
        f"You have {contact_count} contact(s) saved.",
        ICON_CONTACTS,
    )
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

        render_contact_rows(contacts, key_prefix="all")

        csv_all = df_all.to_csv(index=False).encode("utf-8")
        st.download_button("Export All as CSV", csv_all, "contacts_all.csv", "text/csv")

        st.markdown("---")
        st.subheader("Edit / Delete Contact")
        ids = [c["id"] for c in contacts]
        # Compute S.No. per user (oldest = 1) -- same logic as render_contact_rows
        sno_map = {
            c["id"]: i + 1
            for i, c in enumerate(sorted(contacts, key=lambda x: x["id"]))
        }
        labels = [
            f"S.No {sno_map[c['id']]} - {c.get('full_name') or '(no name)'} @ {c.get('company_name') or '(no company)'}"
            for c in contacts
        ]
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
                    st.success("Contact deleted.")
                    st.rerun()
