import pandas as pd
import streamlit as st

import tree_care_common as common

BOOKING_LOG = common.BASE_DIR / "booking-log.csv"

st.set_page_config(
    page_title="Tree Care Business Intelligence", page_icon="🌲", layout="wide"
)


@st.cache_data(ttl=600)
def load_data():
  """Load tables from the project database. Duplicates are dropped by key."""
  conn = common.connect()
  try:
    trees = pd.read_sql_query("SELECT * FROM vulnerable_trees", conn)
    competitors = pd.read_sql_query("SELECT * FROM competitors", conn)
    zips = pd.read_sql_query("SELECT * FROM zip_profile", conn)
    weather = pd.read_sql_query(
        """
        SELECT * FROM weather_triggers
        WHERE forecast_start IS NOT NULL
        ORDER BY forecast_start DESC, id DESC
        LIMIT 10
        """,
        conn,
    )
  except Exception as e:
    st.error(f"Database error: {e}. Run `tree_care_pipeline.py` first.")
    return None
  finally:
    conn.close()
  return (
      trees.drop_duplicates(subset=["tree_id"]),
      competitors.drop_duplicates(subset=["entity_id"]),
      zips,
      weather,
  )


def load_bookings():
  """The booking log is a plain CSV (see booking-log.csv)."""
  if not BOOKING_LOG.exists():
    return pd.DataFrame()
  bookings = pd.read_csv(BOOKING_LOG, dtype=str).dropna(how="all")
  return bookings


data = load_data()
if data is None:
  st.stop()
trees_df, competitors_df, zips_df, weather_df = data

# Distance from Golden, from the ZIP table for competitors and from the
# coordinates for trees.
zip_miles = dict(zip(zips_df["zip"], zips_df["miles_from_golden"]))
competitors_df["miles_from_golden"] = competitors_df["principal_zip"].map(zip_miles)
trees_df["miles_from_golden"] = [
    common.miles_from_golden(lat, lon)
    for lat, lon in zip(trees_df["latitude"], trees_df["longitude"])
]

st.sidebar.header("Service area")
radius = st.sidebar.slider("Radius from Golden (miles)", 5, 50, 25, step=5)
st.sidebar.caption("Golden base: 39.7555, -105.2211")

trees_in = trees_df[trees_df["miles_from_golden"] <= radius]
comp_in = competitors_df[competitors_df["miles_from_golden"] <= radius]
zips_in = zips_df[zips_df["miles_from_golden"] <= radius]

st.title("🌲 Golden Base: Tree Care Intelligence")
st.markdown(
    "Ash trees in the Denver inventory, tree-business competitors, ZIP medians"
    " and the winter forecast, measured from Golden."
)

col1, col2, col3, col4 = st.columns(4)
with col1:
  st.metric(f"Ash trees within {radius} mi", f"{len(trees_in):,}")
with col2:
  st.metric(f"Tree businesses within {radius} mi", f"{len(comp_in):,}")
with col3:
  st.metric(f"ZIPs within {radius} mi", f"{len(zips_in):,}")
with col4:
  latest = weather_df.iloc[0]["forecast_start"][:10] if not weather_df.empty else "n/a"
  open_now = (
      int(weather_df["fertilization_recommended"].sum()) if not weather_df.empty else 0
  )
  st.metric("Open winter windows (latest run)", open_now, help=f"Forecast run {latest}")

st.divider()

tab_zip, tab_trees, tab_comp, tab_winter, tab_book = st.tabs([
    "📍 ZIP profile",
    "🗺️ Ash trees",
    "🏢 Competitors",
    "❄️ Winter windows",
    "📒 Booking log",
])

with tab_zip:
  st.subheader(f"ZIPs within {radius} miles of Golden, by median home value")
  st.caption(
      "Medians: ACS 2019–2023 5-year estimates. Competitor counts are"
      " tree businesses in the registry by ZIP."
  )
  comp_by_zip = comp_in.groupby("principal_zip").size().rename("tree_businesses")
  table = zips_in.set_index("zip").join(comp_by_zip).fillna({"tree_businesses": 0})
  table = table.sort_values("median_home_value", ascending=False)
  st.dataframe(
      table[[
          "miles_from_golden",
          "median_home_value",
          "median_hh_income",
          "tree_businesses",
      ]],
      use_container_width=True,
  )

with tab_trees:
  st.subheader(f"Ash trees within {radius} miles (Denver city inventory)")
  st.caption(
      "Inventory dates vary (2014 to 2026). These are public street trees, so"
      " they show neighborhoods, not customers."
  )
  if trees_in.empty:
    st.info("No ash trees within this radius.")
  else:
    species = ["All"] + sorted(trees_in["common_name"].dropna().unique().tolist())
    chosen = st.selectbox("Species", species)
    shown = trees_in if chosen == "All" else trees_in[trees_in["common_name"] == chosen]
    mapped = shown.dropna(subset=["latitude", "longitude"])
    mapped = mapped[(mapped["latitude"] != 0) & (mapped["longitude"] != 0)]
    if not mapped.empty:
      st.map(mapped[["latitude", "longitude"]])
    st.dataframe(
        shown[[
            "tree_id", "common_name", "address", "street", "neighbor",
            "condition", "inventory_date", "miles_from_golden",
        ]],
        use_container_width=True,
    )

with tab_comp:
  st.subheader(f"Tree businesses within {radius} miles")
  if comp_in.empty:
    st.info("No competitors within this radius.")
  else:
    city_options = ["All"] + sorted(comp_in["principal_city"].dropna().unique().tolist())
    city = st.selectbox("City", city_options)
    search = st.text_input("Business name contains", "")
    shown = comp_in.copy()
    if city != "All":
      shown = shown[shown["principal_city"] == city]
    if search:
      shown = shown[shown["entity_name"].str.contains(search, case=False, na=False)]
    st.bar_chart(shown["principal_city"].value_counts())
    st.dataframe(
        shown[[
            "entity_id", "entity_name", "principal_address", "principal_city",
            "principal_zip", "status", "miles_from_golden",
        ]].sort_values("miles_from_golden"),
        use_container_width=True,
    )

with tab_winter:
  st.subheader("Winter windows (Golden forecast)")
  st.caption(
      f"Open when forecast air temperature is above 40°F, the forecast text has"
      f" no snow, and 30-day precipitation is under 1.00 in. Soil temperature"
      f" and frost depth are not checked. The rule is an assumption for the crew"
      f" lead to confirm."
  )
  if weather_df.empty:
    st.warning("No forecast rows yet. Run `winter_weather_fert.py` with TREE_CARE_CONTACT set.")
  else:
    shown = weather_df[[
        "period_name", "forecast_start", "temperature", "conditions",
        "precip_30d_in", "precip_station", "fertilization_recommended",
    ]].copy()
    shown["fertilization_recommended"] = shown["fertilization_recommended"].map(
        {1: "✅ Open", 0: "⏸️ Hold"}
    )
    st.dataframe(shown, use_container_width=True)

with tab_book:
  st.subheader("Booking log")
  bookings = load_bookings()
  if bookings.empty:
    st.info(f"No bookings yet. Add rows to {BOOKING_LOG.name} (see the playbook, section 5).")
  else:
    st.dataframe(bookings, use_container_width=True)
    booked = bookings[bookings["status"].isin(["booked", "completed"])]
    st.markdown("**Booked or completed, by ZIP and service**")
    if booked.empty:
      st.caption("None yet.")
    else:
      summary = booked.groupby(["zip", "service"]).size().rename("jobs").reset_index()
      st.dataframe(summary, use_container_width=True)
