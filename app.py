# ===================== SHELF LIFE REPORT ===================== #
import pandas as pd
import streamlit as st

st.divider()
st.header("📊 Shelf Life Report")

# -------- Filters -------- #
c1, c2, c3 = st.columns(3)

with c1:
    f_invoice = st.text_input("Invoice Number (optional)")

with c2:
    from_date = st.date_input("From Arrival Date")

with c3:
    to_date = st.date_input("To Arrival Date")

show_all = st.checkbox("Show All (ignore filters)", value=True)

# -------- Generate -------- #
if st.button("📥 Generate Report"):
    try:
        # ---- Fetch shipments with filters ---- #
        q = supabase.table("shipments").select("*")

        if not show_all:
            if f_invoice:
                q = q.eq("invoice_number", f_invoice)
            if from_date:
                q = q.gte("arrival_port_date", str(from_date))
            if to_date:
                q = q.lte("arrival_port_date", str(to_date))

        shipments_res = q.execute()
        shipments = shipments_res.data or []

        if not shipments:
            st.warning("No shipments found for given filters")
        else:
            shipment_ids = [s["id"] for s in shipments]

            # ---- Fetch all items in ONE call (fast) ---- #
            items_res = supabase.table("shipment_items") \
                .select("*") \
                .in_("shipment_id", shipment_ids) \
                .execute()

            items = items_res.data or []

            if not items:
                st.warning("No items found")
            else:
                # ---- Map shipment info ---- #
                ship_map = {s["id"]: s for s in shipments}

                rows = []
                for it in items:
                    sh = ship_map.get(it["shipment_id"], {})
                    rows.append({
                        "Invoice": sh.get("invoice_number"),
                        "Bill Entry No": sh.get("bill_entry_number"),
                        "Arrival Port Date": sh.get("arrival_port_date"),
                        "Barcode": it.get("barcode"),
                        "Description": it.get("description"),
                        "Ordered Qty": it.get("ordered_qty"),
                        "Received Qty": it.get("received_qty"),
                        "MFG Date": it.get("mfg_date"),
                        "EXP Date": it.get("exp_date"),
                        "Shelf Life %": it.get("shelf_life_percent"),
                        "Status": it.get("status")
                    })

                df = pd.DataFrame(rows)

                # ---- KPIs ---- #
                total = len(df)
                expired = (df["Status"] == "Expired").sum()
                near = (df["Status"] == "Near Expiry").sum()
                ok = (df["Status"] == "OK").sum()
                avg_pct = round(df["Shelf Life %"].mean(), 2) if total else 0

                k1, k2, k3, k4, k5 = st.columns(5)
                k1.metric("Total Items", total)
                k2.metric("Expired", expired)
                k3.metric("Near Expiry", near)
                k4.metric("OK", ok)
                k5.metric("Avg Shelf Life %", avg_pct)

                # ---- Styling (simple + readable) ---- #
                def highlight_status(val):
                    if val == "Expired":
                        return "background-color:#ffcccc"
                    elif val == "Near Expiry":
                        return "background-color:#fff3cd"
                    elif val == "OK":
                        return "background-color:#d4edda"
                    return ""

                styled_df = df.style.applymap(highlight_status, subset=["Status"])

                # ---- Table ---- #
                st.subheader("Detailed Report")
                st.dataframe(styled_df, use_container_width=True)

                # ---- Download ---- #
                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "⬇️ Download CSV",
                    csv,
                    "shelf_life_report.csv",
                    "text/csv"
                )

    except Exception as e:
        st.error(f"Report Error: {e}")
