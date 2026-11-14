"""Run with: python -m streamlit run app.py"""
import json
import io
import logging
import math
import time
import uuid
import streamlit as st
from PIL import ImageOps
from virtual_closet import database as db
from virtual_closet.attributes import (
    CATEGORIES,
    SUBCATEGORIES,
    COLORS,
    BASE_PATTERNS,
    DECORATIONS,
    FITS,
    SLEEVE_LENGTHS,
    NECKLINES,
    CLOTHING_LENGTHS,
    UNKNOWN_ATTRIBUTE,
)
from virtual_closet.brands import BRANDS
from virtual_closet.images import read_image, image_hash, remove_background, display_image
from virtual_closet.metadata import automatic_name, clean_brand, reviewed_attributes
from virtual_closet.recommendation import OCCASIONS, recommend, signature

st.set_page_config(page_title="VirtualCloset", page_icon="👕", layout="wide")
st.markdown("""<style>
.block-container {max-width:1180px;padding-top:2rem;}
div[data-testid="stImage"] img {border-radius:12px;}
.item-name {overflow-wrap:anywhere;white-space:normal;}
</style>""", unsafe_allow_html=True)

@st.cache_resource(show_spinner="Preparing clothing recognition…")
def get_model():
    from virtual_closet.model import FashionModel
    return FashionModel()

def preview_bytes(raw, background, size=420, square=False):
    """Cache bounded, display-sized previews in this user's session."""
    cache = st.session_state.setdefault("_photo_previews", {})
    key = (image_hash(raw), background, size, square)
    if key in cache:
        return cache[key]
    photo = display_image(raw, background)
    if square:
        photo = ImageOps.pad(photo, (size, size), color=background)
    else:
        photo.thumbnail((size, size))
    buffer = io.BytesIO()
    photo.save(buffer, format="JPEG", quality=88)
    result = buffer.getvalue()
    if len(cache) >= 128:
        del cache[next(iter(cache))]
    cache[key] = result
    return result

def reset_session(user=None):
    st.session_state.clear()
    if user:
        st.session_state["user"] = user

def clear_selection():
    for key in list(st.session_state):
        if key.startswith("select_"):
            del st.session_state[key]
    st.session_state.pop("remove_confirmation", None)

def choose_category(value):
    st.session_state["closet_category"] = value
    clear_selection()
    # Attribute filters are category-dependent, so reset them when switching categories.
    for key in list(st.session_state):
        if key.startswith("closet_filter_"):
            st.session_state.pop(key, None)

def mark_manual(prefix):
    st.session_state[prefix + "manual"] = True

def cancel_rename(item_id, name):
    st.session_state[f"rename_input_{item_id}"] = name

def review_values(entry):
    p = entry["prefix"]

    category = st.session_state.get(
        p + "category",
        entry["result"]["attributes"]["Category"]
    )

    attrs = dict(entry["result"]["attributes"])
    attrs["Category"] = category

    # Read all editable attributes
    fields = {
        "Color": COLORS,
        "Subcategory": SUBCATEGORIES.get(category, []),
        "Base pattern": list(BASE_PATTERNS.keys()),
        "Decoration": list(DECORATIONS.keys()),
        "Fit": list(FITS.keys()),
        "Sleeve Length": list(SLEEVE_LENGTHS.keys()),
        "Neckline": list(NECKLINES.keys()),
        "Clothing Length": list(CLOTHING_LENGTHS.keys()),
    }

    for name, options in fields.items():
        if name in st.session_state:
            pass

        key = p + name

        if key in st.session_state:
            attrs[name] = st.session_state[key]

    attrs = reviewed_attributes(attrs, category)

    brand = st.session_state.get(p + "brand")

    if brand == "Other":
        brand = st.session_state.get(p + "custom_brand", "")

    return attrs, clean_brand(brand)


def attribute_selectbox(label, options, key, current=None):
    """Render an attribute selector with a safe default."""

    options = list(options)

    if not options:
        options = [UNKNOWN_ATTRIBUTE]

    if current not in options:
        current = options[0]

    if key not in st.session_state:
        st.session_state[key] = current

    elif st.session_state[key] not in options:
        st.session_state[key] = current

    return st.selectbox(
        label,
        options,
        key=key
    )

def sync_name(entry):
    p = entry["prefix"]
    if not st.session_state.get(p + "manual", False):
        attrs, brand = review_values(entry)
        st.session_state[p + "name"] = automatic_name(attrs, brand)

def save_review(uid):
    added = skipped = 0
    failures, remaining = [], []
    for entry in st.session_state.get("review", []):
        try:
            attrs, brand = review_values(entry)
            result = dict(entry["result"], attributes=attrs)
            ok = db.save_item(uid, entry["filename"], entry["digest"], entry["original"],
                              result, name=st.session_state.get(entry["prefix"] + "name"),
                              brand=brand, cutout_data=entry["cutout"], reviewed=True)
            added += ok
            skipped += not ok
        except Exception as exc:
            logging.exception("Saving reviewed item failed")
            failures.append(f'{entry["filename"]}: {exc}')
            remaining.append(entry)
    st.session_state["review"] = remaining
    st.session_state["failures"] = failures
    st.session_state["notice"] = f"Added {added} item(s). Skipped {skipped} duplicate(s)."
    st.session_state.pop("outfits", None)
    if not remaining:
        st.session_state["upload_version"] = st.session_state.get("upload_version", 0) + 1

def analyze_files(uid, files):
    batch, failures, seen = [], [], set()
    skipped = 0
    progress = st.progress(0)
    for index, file in enumerate(files):
        try:
            raw = file.getvalue()
            digest = image_hash(raw)
            if digest in seen or db.exists(uid, digest):
                skipped += 1
                continue
            seen.add(digest)
            # Required order: segmentation first, then recognition on a white composite.
            cutout = remove_background(raw)
            result = get_model().analyze(read_image(cutout))
            batch.append({"prefix": "review_" + uuid.uuid4().hex + "_",
                          "filename": file.name, "digest": digest, "original": raw,
                          "cutout": cutout, "result": result})
        except Exception as exc:
            logging.exception("Analyzing upload failed")
            failures.append(f"{file.name}: {exc}")
        finally:
            progress.progress((index + 1) / len(files))
    progress.empty()
    st.session_state["review"] = batch
    st.session_state["failures"] = failures
    if skipped:
        st.session_state["notice"] = f"Skipped {skipped} duplicate image(s)."
    st.rerun()

try:
    if not st.session_state.get("_database_ready"):
        db.initialize()
        st.session_state["_database_ready"] = True
except Exception as exc:
    st.error(f'Could not open your closet database: {exc}')
    st.stop()

if 'user' not in st.session_state:
    st.caption('YOUR WARDROBE, SIMPLIFIED')
    st.title('A little less “what do I wear?”')
    st.write('Keep your clothes in one place. Find an outfit for your day.')
    login_tab, signup_tab = st.tabs(['Log in','Create account'])
    with login_tab:
        with st.form('login'):
            username = st.text_input('Username')
            password = st.text_input('Password',type='password')
            submitted = st.form_submit_button('Log in',type='primary')
        if submitted:
            remaining = st.session_state.get('locked_until',0)-time.time()
            if remaining > 0:
                st.error(f'Too many attempts. Try again in {int(remaining)+1} seconds.')
            else:
                user = db.login(username,password)
                if user:
                    reset_session(user)
                    st.rerun()
                else:
                    attempts = st.session_state.get('login_attempts',0)+1
                    st.session_state['login_attempts'] = attempts
                    if attempts >= 5:
                        st.session_state['locked_until'] = time.time()+30
                        st.session_state['login_attempts'] = 0
                    st.error('Incorrect username or password.')
    with signup_tab:
        st.caption('Use 3–32 letters, numbers or underscores for your username; 10–128 characters for your password.')
        with st.form('signup'):
            username = st.text_input('Choose a username')
            password = st.text_input('Choose a password',type='password')
            confirmation = st.text_input('Repeat password',type='password')
            submitted = st.form_submit_button('Create my closet',type='primary')
        if submitted:
            if password != confirmation:
                st.error('Passwords do not match.')
            else:
                try:
                    user = db.register(username,password)
                    reset_session(user)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
                except Exception:
                    logging.exception('Registration failed')
                    st.error('Account creation failed. Check the terminal for details.')
    st.caption('Local demonstration · Accounts are stored on this computer. Refreshing the page may require signing in again.')
    st.stop()


user = st.session_state["user"]
uid = user["id"]
with st.sidebar:
    st.title("VirtualCloset")
    st.write(f'Signed in as {user["username"]}')
    stored_color = db.get_background(uid)
    background = st.color_picker("Photo background", stored_color, key="theme_color")
    if background != stored_color:
        db.set_background(uid, background)
    if st.button("Log out"):
        reset_session()
        st.rerun()

st.title("VirtualCloset")
items = db.list_items(uid)
st.caption(f"{len(items)} pieces in your closet")
with st.container(key="notifications"):
    if "notice" in st.session_state:
        st.success(st.session_state.pop("notice"))
    for failure in st.session_state.get("failures", []):
        st.error(failure)
# Stable key and render position preserve the selected browser tab.
# Switching tabs is client-side: no database reads or image rendering reruns.
today, closet, upload = st.tabs(
    ["Today's outfit", "My closet", "Add clothes"],
    key="main_tabs",
    on_change="ignore",
)

with upload:
    st.subheader("Add clothes")
    files = st.file_uploader("Choose photos", type=["jpg", "jpeg", "png", "webp"],
                             accept_multiple_files=True,
                             key=f'upload_{st.session_state.get("upload_version", 0)}')
    st.caption("One garment per photo. Up to 20 MB and 24 megapixels per image.")
    review = st.session_state.get("review", [])
    if st.button("Analyze photos", disabled=not files or bool(review), type="primary"):
        analyze_files(uid, files)
    if review:
        st.caption("Review the cutouts and details. Nothing is added until you choose Add to closet.")
        st.button("Add to closet", key="add_top", type="primary", on_click=save_review, args=(uid,))
        for entry in review:
            p = entry["prefix"]
            attrs, brand = review_values(entry)
            if p + "name" not in st.session_state:
                st.session_state[p + "name"] = automatic_name(attrs, brand)
            left, right = st.columns([1, 2])
            with left:
                st.image(preview_bytes(entry["cutout"], background), width="stretch")
            with right:
                st.text_input("Name", key=p + "name", on_change=mark_manual, args=(p,))
                st.selectbox("Brand", ["Other"] + BRANDS, index=None,
                             placeholder="Select brand (optional)", key=p + "brand",
                             on_change=sync_name, args=(entry,))
                if st.session_state.get(p + "brand") == "Other":
                    st.text_input("Enter brand", key=p + "custom_brand",
                                  on_change=sync_name, args=(entry,))
                # Category
                predicted = entry["result"]["attributes"]["Category"]

                attribute_selectbox(
                    "Category",
                    sorted(CATEGORIES.keys(), key=str.casefold),
                    p + "category",
                    predicted
                )

                selected_category = st.session_state[p + "category"]

                # Subcategory
                attribute_selectbox(
                    "Subcategory",
                    SUBCATEGORIES.get(selected_category, ["Other / unspecified"]),
                    p + "Subcategory",
                    entry["result"]["attributes"].get("Subcategory")
                )

                # Existing visual attributes
                attribute_selectbox(
                    "Color",
                    COLORS,
                    p + "Color",
                    entry["result"]["attributes"].get("Color")
                )

                attribute_selectbox(
                    "Pattern",
                    BASE_PATTERNS.keys(),
                    p + "Base pattern",
                    entry["result"]["attributes"].get("Base pattern")
                )

                attribute_selectbox(
                    "Decoration",
                    DECORATIONS.keys(),
                    p + "Decoration",
                    entry["result"]["attributes"].get("Decoration")
                )

                st.divider()
                st.markdown("**Additional Attributes**")

                # Fit
                attribute_selectbox(
                    "Fit",
                    FITS.keys(),
                    p + "Fit",
                    entry["result"]["attributes"].get("Fit")
                )

                # Sleeve Length
                attribute_selectbox(
                    "Sleeve Length",
                    SLEEVE_LENGTHS.keys(),
                    p + "Sleeve Length",
                    entry["result"]["attributes"].get("Sleeve Length")
                )

                # Neckline
                attribute_selectbox(
                    "Neckline",
                    NECKLINES.keys(),
                    p + "Neckline",
                    entry["result"]["attributes"].get("Neckline")
                )

                # Clothing Length
                attribute_selectbox(
                    "Clothing Length",
                    CLOTHING_LENGTHS.keys(),
                    p + "Clothing Length",
                    entry["result"]["attributes"].get("Clothing Length")
                )
            st.divider()
        st.button("Add to closet", key="add_bottom", type="primary", on_click=save_review, args=(uid,))
        if st.button("Discard this review"):
            st.session_state["review"] = []
            st.rerun()

with closet:
    st.subheader("My closet")
    attrs_by_id = {i["id"]: json.loads(i["attributes_json"]) for i in items}
    categories = {a.get("Category") or "Uncategorized" for a in attrs_by_id.values()}

    # Main category labels
    options = [None] + sorted(categories - {"Uncategorized"}, key=str.casefold)
    if "Uncategorized" in categories:
        options.append("Uncategorized")

    current = st.session_state.get("closet_category")
    if current not in options:
        current = None
        choose_category(None)

    split = math.ceil(len(options) / 2) if len(options) > 6 else len(options)
    for row in (options[:split], options[split:]):
        if row:
            cols = st.columns(len(row))
            for col, category in zip(cols, row):
                col.button(
                    "All" if category is None else category,
                    key="category_" + ("__all__" if category is None else category),
                    type="primary" if category == current else "secondary",
                    on_click=choose_category,
                    args=(category,),
                    width="stretch",
                )

    # First apply the selected main category.
    category_items = [
        item for item in items
        if current is None
        or (attrs_by_id[item["id"]].get("Category") or "Uncategorized") == current
    ]

    st.markdown("#### Filter by attributes")
    st.caption(
        "Choose one or more values in any field. Values within one field use OR logic; "
        "different fields are combined with AND logic."
    )

    filter_fields = [
        ("Subcategory", "Subcategory"),
        ("Color", "Color"),
        ("Base pattern", "Pattern"),
        ("Decoration", "Decoration"),
        ("Fit", "Fit"),
        ("Sleeve Length", "Sleeve Length"),
        ("Neckline", "Neckline"),
        ("Clothing Length", "Clothing Length"),
    ]

    selected_filters = {}
    filter_columns = st.columns(4)
    for index, (field, label) in enumerate(filter_fields):
        values = sorted(
            {
                str(attrs_by_id[item["id"]].get(field)).strip()
                for item in category_items
                if attrs_by_id[item["id"]].get(field) not in (None, "")
            },
            key=str.casefold,
        )
        key = "closet_filter_" + field.lower().replace(" ", "_")
        existing_selection = st.session_state.get(key, [])
        st.session_state[key] = [
            value for value in existing_selection if value in values
        ]
        with filter_columns[index % 4]:
            selected_filters[field] = st.multiselect(
                label,
                options=values,
                key=key,
                placeholder="All",
            )

    # Different attributes are combined with AND; multiple values in one
    # attribute are combined with OR.
    visible = []
    for item in category_items:
        attrs = attrs_by_id[item["id"]]
        if all(
            not selected_values or attrs.get(field) in selected_values
            for field, selected_values in selected_filters.items()
        ):
            visible.append(item)

    if st.button("Clear attribute filters"):
        for key in list(st.session_state):
            if key.startswith("closet_filter_"):
                st.session_state.pop(key, None)
        st.rerun()

    st.caption(f"Showing {len(visible)} of {len(category_items)} item(s)")

    a, b = st.columns(2)
    if a.button("Select all in this category", disabled=not visible):
        for item in visible:
            st.session_state[f'select_{item["id"]}'] = True
        st.session_state.pop("remove_confirmation", None)
    if b.button("Clear selection"):
        clear_selection()

    selected = [
        i["id"] for i in visible
        if st.session_state.get(f'select_{i["id"]}', False)
    ]
    if st.button(f"Remove selected ({len(selected)})", disabled=not selected):
        st.session_state["remove_confirmation"] = tuple(selected)

    confirm = st.session_state.get("remove_confirmation")
    if confirm is not None:
        if tuple(selected) != confirm:
            st.session_state.pop("remove_confirmation", None)
        else:
            st.warning(f"Remove {len(confirm)} selected item(s) permanently?")
            yes, no = st.columns(2)
            if yes.button("Confirm removal", type="primary"):
                count = db.delete_items(uid, confirm)
                clear_selection()
                st.session_state.pop("outfits", None)
                st.session_state["notice"] = f"Removed {count} item(s)."
                st.rerun()
            if no.button("Cancel removal"):
                st.session_state.pop("remove_confirmation", None)
                st.rerun()

    missing = [i for i in items if not i.get("cutout_data")]
    if missing:
        st.info(f"{len(missing)} existing photo(s) still have their original backgrounds.")
        if st.button("Remove backgrounds from existing clothes"):
            failures = []
            with st.spinner("Removing backgrounds…"):
                for item in missing:
                    try:
                        db.set_cutout(uid, item["id"], remove_background(item["image_data"]))
                    except Exception as exc:
                        failures.append(f'{item["display_name"]}: {exc}')
            st.session_state["failures"] = failures
            st.rerun()

    if not visible:
        st.info("No clothes match the current category and attribute filters.")

    for start in range(0, len(visible), 4):
        for col, item in zip(st.columns(4), visible[start:start + 4]):
            with col:
                st.image(
                    preview_bytes(item.get("cutout_data") or item["image_data"], background),
                    width="stretch",
                )
                st.text(item["display_name"])
                st.caption(item.get("brand") or "Unknown / No brand")
                st.checkbox("Select", key=f'select_{item["id"]}')
                with st.expander("Rename"):
                    with st.form(f'rename_{item["id"]}'):
                        name = st.text_input(
                            "New name",
                            value=item["display_name"],
                            key=f'rename_input_{item["id"]}',
                        )
                        save = st.form_submit_button("Save")
                        cancel = st.form_submit_button(
                            "Cancel",
                            on_click=cancel_rename,
                            args=(item["id"], item["display_name"]),
                        )
                    if save:
                        try:
                            db.rename_item(uid, item["id"], name)
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))
                    if cancel:
                        st.rerun()

                with st.expander("Edit Attributes"):
                    saved_attrs = json.loads(item["attributes_json"])
                    prefix = f'edit_{item["id"]}_'
                    st.caption("Review and correct the automatically detected attributes.")

                    attribute_selectbox(
                        "Category",
                        sorted(CATEGORIES.keys(), key=str.casefold),
                        prefix + "category",
                        saved_attrs.get("Category"),
                    )
                    selected_category = st.session_state[prefix + "category"]

                    attribute_selectbox(
                        "Subcategory",
                        SUBCATEGORIES.get(selected_category, ["Other / unspecified"]) + ["Other / unspecified"],
                        prefix + "Subcategory",
                        saved_attrs.get("Subcategory"),
                    )
                    attribute_selectbox(
                        "Color", COLORS, prefix + "Color", saved_attrs.get("Color")
                    )
                    attribute_selectbox(
                        "Pattern", BASE_PATTERNS.keys(),
                        prefix + "Base pattern", saved_attrs.get("Base pattern")
                    )
                    attribute_selectbox(
                        "Decoration", DECORATIONS.keys(),
                        prefix + "Decoration", saved_attrs.get("Decoration")
                    )

                    st.divider()
                    st.markdown("**Additional Attributes**")
                    attribute_selectbox(
                        "Fit", FITS.keys(), prefix + "Fit", saved_attrs.get("Fit")
                    )
                    attribute_selectbox(
                        "Sleeve Length", SLEEVE_LENGTHS.keys(),
                        prefix + "Sleeve Length", saved_attrs.get("Sleeve Length")
                    )
                    attribute_selectbox(
                        "Neckline", NECKLINES.keys(),
                        prefix + "Neckline", saved_attrs.get("Neckline")
                    )
                    attribute_selectbox(
                        "Clothing Length", CLOTHING_LENGTHS.keys(),
                        prefix + "Clothing Length", saved_attrs.get("Clothing Length")
                    )

                    if st.button("Save Attribute Changes", key=prefix + "save"):
                        updated_attrs = dict(saved_attrs)
                        field_names = [
                            "Subcategory", "Color", "Base pattern", "Decoration",
                            "Fit", "Sleeve Length", "Neckline", "Clothing Length",
                        ]
                        updated_attrs["Category"] = selected_category
                        for field in field_names:
                            updated_attrs[field] = st.session_state[prefix + field]
                        try:
                            success = db.update_attributes(uid, item["id"], updated_attrs)
                            if success:
                                st.session_state["notice"] = "Clothing attributes updated successfully."
                                st.session_state.pop("outfits", None)
                                st.rerun()
                            else:
                                st.error("Could not update clothing attributes.")
                        except Exception as exc:
                            logging.exception("Attribute update failed")
                            st.error(f"Could not save attributes: {exc}")

with today:
    st.subheader("Outfits for your day")
    occasion = st.selectbox("Occasion", list(OCCASIONS))
    mood = st.text_input("Mood or style (optional)", placeholder="Relaxed, minimalist, colorful…")
    layer = st.checkbox("Include a jacket or coat")
    context = (occasion, mood.strip(), layer, tuple(i["id"] for i in items))
    if st.session_state.get("outfit_context") != context:
        st.session_state["outfit_context"] = context
        st.session_state.pop("outfits", None)
        st.session_state["variant"] = 0
    left, right = st.columns(2)
    generate = left.button("Suggest outfits", type="primary", disabled=not items)
    refresh = right.button("Refresh", disabled=not items or not st.session_state.get("outfits"))
    if generate or refresh:
        try:
            with st.spinner("Finding combinations…"):
                model = get_model()
                for item in items:
                    if not item.get("embedding_json"):
                        cutout = item.get("cutout_data") or remove_background(item["image_data"])
                        result = model.analyze(read_image(cutout))
                        db.update_analysis(uid, item["id"], result)
                        if not item.get("cutout_data"):
                            db.set_cutout(uid, item["id"], cutout)
                items = db.list_items(uid)
                query = OCCASIONS[occasion] + (f", {mood.strip()}" if mood.strip() else "")
                scores = model.occasion_scores(items, query)
                previous = st.session_state.get("outfits", [])
                st.session_state["variant"] = st.session_state.get("variant", 0) + 1
                outfits, notes = recommend(items, scores, layer,
                    variant=st.session_state["variant"],
                    exclude=[signature(o) for o in previous])
                # Store IDs so renames, deletions and cutouts never leave stale cards.
                st.session_state["outfits"] = [[{"id": i["id"]} for i in o] for o in outfits]
                st.session_state["outfit_notes"] = notes
        except Exception as exc:
            logging.exception("Recommendation failed")
            st.error(f"Could not generate outfits: {exc}")
    if not items:
        st.info("Add clothes to get started.")
    for note in st.session_state.get("outfit_notes", []) if st.session_state.get("outfits") is not None else []:
        st.info(note)
    lookup = {i["id"]: i for i in items}
    outfits = st.session_state.get("outfits", [])
    if outfits:
        for n, outfit in enumerate(outfits, 1):
            with st.container(border=True):
                st.subheader(f"Outfit {n}")
                outfit_items = [lookup[ref["id"]] for ref in outfit if ref["id"] in lookup]
                columns = st.columns(max(4, len(outfit_items)))
                for col, item in zip(columns, outfit_items):
                    with col:
                        photo = preview_bytes(item.get("cutout_data") or item["image_data"],
                                              background, size=180, square=True)
                        st.image(photo, width=180)
                        st.text(item["display_name"])
                        st.caption(item.get("brand") or "Unknown / No brand")

