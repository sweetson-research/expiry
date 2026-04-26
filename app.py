
import streamlit as st
from datetime import date
import os
import pandas as pd
from supabase import create_client
from dotenv import load_dotenv

# ---------------- CONFIG ---------------- #
st.set_page_config(page_title="Shelf Life Tracker", layout="wide")
st.title("📦 Shipment Shelf-Life Tracker")

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------- SAFE SESSION INIT ---------------- #
if "items" not in st.session_state or not isinstance(st.session_state.items, list):
    st.session_state.items = []

# ---------------- HELPERS ---------------- #
def calculate_shelf_life(mfg, exp):
    total_days = (exp - mfg).days
    remaining_days = (exp - date.today()).days
    return total_days, remaining_days

def get_status(remaining, total, tolerance):
    if total <= 0:
        return "Invalid"
    percent = (remaining / total) * 100
    if remaining <= 0:
        return "Expired"
    elif percent < tolerance:
        return "Near Expiry"
    return "OK"

# ---------------- RESET ---------------- #
if st.button("🔄 Reset Session"):
    st.session_state.clear()
    st.rerun()

# ---------------- HEADER ---------------- #
st.header("Shipment Details")

col1, col2 = st.columns(2)

with col1:
    invoice = st.text_input("Invoice Number")

with col2:
    bill_entry_number = st.text_input("Bill of Entry Number")

col3, col4 = st.columns(2)

with col3:
    total_lines = st.number_input(
        "Number of Item Lines in Invoice",
        min_value=1,
        step=1
    )

with col4:
    received_lines = st.number_input(
        "Actual Number of Lines Received",
        min_value=0,
        step=1
    )

col5, col6, col7 = st.columns(3)

with col5:
    arrival_port = st.date_input("Arrival at Port")

with col6:
    arrival_wh = st.date_input("Arrival at Warehouse")

with col7:
    bill_entry_date = st.date_input("Bill of Entry Date")

tolerance = st.number_input(
    "Shelf Life Tolerance (%)",
    min_value=0,
    max_value=100,
    value=60,
    step=1
)

st.divider()

# ---------------- LINE ENTRY ---------------- #
st.header("Add Line Item")

barcode = st.text_input("Scan / Enter Barcode")
description = st.text_input("Item Description")

col7, col8 = st.columns(2)

with col7:
    ordered_qty = st.number_input("Ordered Quantity", min_value=0)

with col8:
    received_qty = st.number_input("Received Quantity", min_value=0)

col9, col10 = st.columns(2)

with col9:
    mfg = st.date_input("Manufacturing Date")

with col10:
    exp = st.date_input("Expiry Date")

# ---------------- ADD ITEM ---------------- #
if st.button("➕ Add Item"):
    if not barcode:
        st.error("Barcode required")
    elif exp <= mfg:
        st.error("Expiry must be after manufacturing date")
    else:
        total, remaining = calculate_shelf_life(mfg, exp)
        status = get_status(remaining, total, tolerance)

        st.session_state.items.append({
            "barcode": barcode,
            "description": description,
            "ordered_qty": int(ordered_qty),
            "received_qty": int(received_qty),
            "mfg_date": str(mfg),
            "exp_date": str(exp),
            "total_days": total,
            "remaining_days": remaining,
            "status": status
        })

        st.success("Item added")

# ---------------- DISPLAY ---------------- #
st.subheader("Items Added")

items = st.session_state.get("items", [])

# Safety check (prevents your crash)
if not isinstance(items, list):
    st.session_state.items = []
    items = []

valid_items = [i for i in items if isinstance(i, dict)]

if valid_items:
    df = pd.DataFrame(valid_items)
    st.dataframe(df, use_container_width=True)
else:
    st.info("No items added yet")

# ---------------- SAVE ---------------- #
st.divider()

if st.button("💾 Save Shipment"):
    if not invoice:
        st.error("Invoice number required")
    elif not valid_items:
        st.error("Add at least one item")
    else:
        try:
            # Insert shipment header
            res = supabase.table("shipments").insert({
                "invoice_number": invoice,
                "bill_entry_number": bill_entry_number,
                "arrival_port_date": str(arrival_port),
                "arrival_warehouse_date": str(arrival_wh),
                "bill_entry_date": str(bill_entry_date),
                "shelf_life_tolerance": int(tolerance),
                "total_lines": int(total_lines),
                "received_lines": int(received_lines)
            }).execute()

            shipment_id = res.data[0]["id"]

            # Prepare items
            for item in valid_items:
                item["shipment_id"] = shipment_id

            # Batch insert
            supabase.table("shipment_items").insert(valid_items).execute()

            st.success("✅ Shipment saved successfully")

            # Reset after save
            st.session_state.items = []

        except Exception as e:
            st.error(f"Error: {e}")
