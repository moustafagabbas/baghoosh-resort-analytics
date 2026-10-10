# Baghoosh Resort – Sales & Pricing Dashboard
# Run with:  streamlit run app.py

import os

import joblib
import pandas as pd
import plotly.express as px
import streamlit as st

# ---------------- CONFIG ----------------
# paths are built from the folder this file is in, so the app works from any terminal location
APP_FOLDER = os.path.dirname(os.path.abspath(__file__))
CLEAN_FILE = os.path.join(APP_FOLDER, "data", "cleaned_data.csv")
LEADS_FILE = os.path.join(APP_FOLDER, "data", "leads_clean.csv")
PLANS_FILE = os.path.join(APP_FOLDER, "data", "raw", "COM_Payment_Plans.xlsx")
MODEL_FILE = os.path.join(APP_FOLDER, "models", "model.joblib")

LAUNCH_DATE = pd.to_datetime("2024-04-15")   # Phase 1 sales launch

BLUE = "#2a78d6"
ORANGE = "#eb6834"
GREEN = "#1baf7a"
GREY = "#898781"
STATUS_COLORS = {"Available": BLUE, "Reserved": ORANGE, "Sold": GREEN}

# the columns the model was trained on (Section 9 of analysis.ipynb)
NUMERIC_FEATURES = ["price_vs_policy", "price_vs_type_median", "built_up_area_sqm", "dist_beach_km"]
CATEGORICAL_FEATURES = ["property_type", "sea_view", "private_pool", "beachfront", "default_plan"]

st.set_page_config(page_title="Baghoosh Resort – Sales Dashboard", page_icon="🏖️", layout="wide")


# ---------------- LOAD DATA AND MODEL ----------------
@st.cache_data
def load_data():
    units = pd.read_csv(CLEAN_FILE, parse_dates=["expected_handover_date", "reservation_date", "contract_date"])
    units = units[units["phase"] == 1]   # only Phase 1 is on sale; Phase 2 has no prices or sales yet
    leads = pd.read_csv(LEADS_FILE, parse_dates=["created_date"])
    leads = leads[leads["unit_id"].isin(units["unit_id"])]
    plans = pd.read_excel(PLANS_FILE)
    return units, leads, plans


@st.cache_resource
def load_model():
    return joblib.load(MODEL_FILE)


units, leads, plans = load_data()
model = load_model()

plan_premium = dict(zip(plans["Payment Plan"], plans["Payment Plan Premium %"]))
plan_names = [plan for plan in plans["Payment Plan"] if plan != "Cash"]   # units are never launched with a cash default plan

# median launch price per sqm of each property type (used for price_vs_type_median)
type_median_ppsqm = units.groupby("property_type")["launch_price_per_sqm"].median()


# ---------------- SIDEBAR FILTERS ----------------
st.sidebar.header("Filters")

start_default = pd.to_datetime("2024-04-15").date()
end_default = pd.to_datetime("2025-12-30").date()
date_range = st.sidebar.date_input("Sales / leads date range", value=(start_default, end_default),
                                   min_value=start_default, max_value=end_default)
if len(date_range) != 2:   # the user has clicked only the first date so far
    st.sidebar.info("Pick an end date.")
    st.stop()
start_date = pd.to_datetime(date_range[0])
end_date = pd.to_datetime(date_range[1])

clusters = st.sidebar.multiselect("Cluster", sorted(units["cluster"].unique()), default=sorted(units["cluster"].unique()))
types = st.sidebar.multiselect("Property type", sorted(units["property_type"].unique()),
                               default=sorted(units["property_type"].unique()))

st.sidebar.caption("Phase 1 units only. Filters apply to every KPI and chart and to the Data tab "
                   "(not to the Prediction tab). Data is synthetic, report date 30 Dec 2025.")

# units that match the cluster / type filters
filtered_units = units[units["cluster"].isin(clusters) & units["property_type"].isin(types)].copy()

# status of each unit on the end date of the range (a unit sold after the end date still counts as Available)
filtered_units["status_at_end"] = filtered_units["status"]
sold_later = (filtered_units["status"] == "Sold") & (filtered_units["contract_date"] > end_date)
filtered_units.loc[sold_later, "status_at_end"] = "Available"

# sales = filtered units that were sold inside the date range
in_date_range = (filtered_units["contract_date"] >= start_date) & (filtered_units["contract_date"] <= end_date)
filtered_sales = filtered_units[(filtered_units["is_sold"] == 1) & in_date_range]

# leads for the filtered units, created inside the date range
filtered_leads = leads[leads["unit_id"].isin(filtered_units["unit_id"]) &
                       (leads["created_date"] >= start_date) & (leads["created_date"] <= end_date)]

if len(filtered_units) == 0:
    st.warning("No units match the filters. Please select at least one cluster and property type.")
    st.stop()


# ---------------- TITLE AND KPI CARDS ----------------
st.title("🏖️ Baghoosh Resort – Sales & Pricing Dashboard")
st.caption("Al Riyadh Real Estate · North Coast · all values in EGP")

units_sold = len(filtered_sales)
revenue = filtered_sales["contract_price"].sum()
sell_through = units_sold / len(filtered_units)
if units_sold > 0:
    avg_price_sqm = (filtered_sales["contract_price"] / filtered_sales["built_up_area_sqm"]).mean()
else:
    avg_price_sqm = 0
if len(filtered_leads) > 0:
    conversion = (filtered_leads["lead_status"] == "Won").mean()
else:
    conversion = 0

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric(f"Units sold (of {len(filtered_units):,})", f"{units_sold:,}")
col2.metric("Contracted revenue", f"EGP {revenue / 1e6:,.0f}M")
col3.metric("Sell-through", f"{sell_through:.0%}")
col4.metric("Avg sold price per sqm", f"EGP {avg_price_sqm:,.0f}")
col5.metric(f"Lead-to-sale conversion ({len(filtered_leads):,} leads)", f"{conversion:.1%}")

# Data comes before Prediction because it follows the sidebar filters; Prediction does not
tab_overview, tab_detail, tab_sales, tab_data, tab_prediction = st.tabs(
    ["Overview", "Detailed Analysis", "Sales & Brokers", "Data", "Prediction"])


# ---------------- TAB 1: OVERVIEW ----------------
with tab_overview:
    if units_sold == 0:
        st.info("No sales in the selected date range / filters.")
    else:
        # monthly revenue
        monthly = filtered_sales.groupby("contract_month").agg(units_sold=("unit_id", "count"),
                                                              revenue=("contract_price", "sum")).reset_index()
        monthly["revenue_m"] = monthly["revenue"] / 1e6
        monthly["cumulative_units"] = monthly["units_sold"].cumsum()

        left, right = st.columns(2)
        fig = px.bar(monthly, x="contract_month", y="revenue_m", title="Contracted revenue per month",
                     labels={"contract_month": "Month", "revenue_m": "Revenue (EGP millions)"},
                     color_discrete_sequence=[BLUE])
        left.plotly_chart(fig, width="stretch")

        fig = px.line(monthly, x="contract_month", y="cumulative_units", markers=True, title="Cumulative units sold",
                      labels={"contract_month": "Month", "cumulative_units": "Units sold (cumulative)"},
                      color_discrete_sequence=[BLUE])
        fig.add_hline(y=len(filtered_units), line_dash="dash", line_color=GREY,
                      annotation_text=f"Inventory: {len(filtered_units)} units")
        right.plotly_chart(fig, width="stretch")

    left, right = st.columns(2)

    # sell-through by property type
    by_type = filtered_units.groupby("property_type").agg(units=("unit_id", "count")).reset_index()
    sold_by_type = filtered_sales.groupby("property_type").size().reset_index(name="sold")
    by_type = by_type.merge(sold_by_type, on="property_type", how="left").fillna(0)
    by_type["sell_through"] = by_type["sold"] / by_type["units"]
    by_type = by_type.sort_values("sell_through")
    fig = px.bar(by_type, x="sell_through", y="property_type", orientation="h", title="Sell-through by property type",
                 labels={"sell_through": "Share of units sold", "property_type": ""},
                 text=by_type["sell_through"].map("{:.0%}".format), color_discrete_sequence=[BLUE])
    fig.update_xaxes(tickformat=".0%")
    left.plotly_chart(fig, width="stretch")

    # units by status (status at the end of the date range)
    status_counts = filtered_units["status_at_end"].value_counts().reset_index()
    status_counts.columns = ["status", "units"]
    fig = px.bar(status_counts, x="status", y="units", text="units", title=f"Units by status on {end_date:%d %b %Y}",
                 labels={"status": "", "units": "Units"}, color="status", color_discrete_map=STATUS_COLORS)
    fig.update_layout(showlegend=False)
    right.plotly_chart(fig, width="stretch")

    # inventory by cluster, coloured by status (from the old HTML dashboard)
    by_cluster = filtered_units.groupby(["cluster", "status_at_end"]).size().reset_index(name="units")
    fig = px.bar(by_cluster, x="units", y="cluster", color="status_at_end", orientation="h",
                 title=f"Inventory by cluster and status on {end_date:%d %b %Y}",
                 labels={"units": "Units", "cluster": "", "status_at_end": "Status"},
                 category_orders={"status_at_end": ["Sold", "Reserved", "Available"]}, color_discrete_map=STATUS_COLORS)
    st.plotly_chart(fig, width="stretch")


# ---------------- TAB 2: DETAILED ANALYSIS ----------------
with tab_detail:
    detail_units = filtered_units.copy()
    detail_units["sold_in_range"] = detail_units["unit_id"].isin(filtered_sales["unit_id"]).astype(int)

    left, right = st.columns(2)

    # sell-through by price vs policy
    detail_units["policy_band"] = pd.cut(detail_units["price_vs_policy"], bins=[-0.01, 0.03, 0.07, 0.12, 1],
                                         labels=["0–3%", "3–7%", "7–12%", "12%+"])
    by_band = detail_units.groupby("policy_band", observed=True).agg(units=("unit_id", "count"),
                                                                     sell_through=("sold_in_range", "mean")).reset_index()
    fig = px.bar(by_band, x="policy_band", y="sell_through", title="Sell-through by launch price above policy price",
                 labels={"policy_band": "Launch price above the policy price", "sell_through": "Share of units sold"},
                 text=by_band["sell_through"].map("{:.0%}".format), hover_data=["units"],
                 color_discrete_sequence=[BLUE])
    fig.update_yaxes(tickformat=".0%")
    left.plotly_chart(fig, width="stretch")

    # sell-through with / without each feature
    feature_rows = []
    for column, label in [("sea_view", "Sea view"), ("private_pool", "Private pool"),
                          ("corner_unit", "Corner unit"), ("beachfront", "Beachfront building")]:
        for value, group in [("Yes", "With feature"), ("No", "Without feature")]:
            subset = detail_units[detail_units[column] == value]
            if len(subset) > 0:
                feature_rows.append([label, group, subset["sold_in_range"].mean(), len(subset)])
    features = pd.DataFrame(feature_rows, columns=["feature", "group", "sell_through", "units"])
    fig = px.bar(features, x="feature", y="sell_through", color="group", barmode="group", hover_data=["units"],
                 title="Sell-through with vs without each feature",
                 labels={"feature": "", "sell_through": "Share of units sold", "group": ""},
                 color_discrete_sequence=[BLUE, ORANGE])
    fig.update_yaxes(tickformat=".0%")
    right.plotly_chart(fig, width="stretch")

    left, right = st.columns(2)

    # launch price per sqm by type
    fig = px.box(detail_units, x="property_type", y="launch_price_per_sqm", points="outliers",
                 title="Launch price per sqm by property type",
                 labels={"property_type": "", "launch_price_per_sqm": "Launch price per sqm (EGP)"},
                 color_discrete_sequence=[BLUE])
    left.plotly_chart(fig, width="stretch")

    # price distribution (from the old HTML dashboard)
    detail_units["launch_price_m"] = detail_units["launch_list_price"] / 1e6
    fig = px.histogram(detail_units, x="launch_price_m", nbins=20, title="Launch price distribution",
                       labels={"launch_price_m": "Launch list price (EGP millions)"}, color_discrete_sequence=[BLUE])
    fig.update_layout(yaxis_title="Number of units", bargap=0.05)
    right.plotly_chart(fig, width="stretch")

    # launch pricing vs days on market (from the old HTML dashboard)
    # sold units: days from launch to reservation; unsold units: days on the market up to the end date
    detail_units["result"] = "Not sold yet"
    detail_units.loc[detail_units["status_at_end"] == "Sold", "result"] = "Sold"
    detail_units["days_on_market"] = (end_date - LAUNCH_DATE).days
    sold_rows = detail_units["result"] == "Sold"
    detail_units.loc[sold_rows, "days_on_market"] = detail_units.loc[sold_rows, "days_to_sell"]
    fig = px.scatter(detail_units, x="price_vs_policy", y="days_on_market", color="result",
                     hover_data=["unit_id", "property_type", "launch_list_price"],
                     title="Launch pricing vs days on market",
                     labels={"price_vs_policy": "Launch price above the policy price", "days_on_market": "Days on market",
                             "result": ""},
                     color_discrete_map={"Sold": BLUE, "Not sold yet": ORANGE})
    fig.update_xaxes(tickformat=".0%")
    st.plotly_chart(fig, width="stretch")
    st.caption("Units that are not sold yet sit at the top (still on the market at the end date). "
               "Most of them are priced further above the policy price than the sold units.")


# ---------------- TAB 3: SALES & BROKERS ----------------
with tab_sales:
    left, right = st.columns(2)

    # sales funnel for the filtered units (whole sales period – viewings have no dates in the cleaned data)
    funnel = pd.DataFrame({
        "stage": ["Leads", "Viewings", "Reservations", "Sales"],
        "count": [filtered_units["leads"].sum(), filtered_units["viewings"].sum(),
                  filtered_units["reservations"].sum(), filtered_units["is_sold"].sum()],
    })
    fig = px.funnel(funnel, x="count", y="stage", title="Sales funnel (whole sales period)",
                    labels={"count": "Count", "stage": ""}, color_discrete_sequence=[BLUE])
    left.plotly_chart(fig, width="stretch")

    # leads per month
    if len(filtered_leads) > 0:
        leads_per_month = filtered_leads.groupby(filtered_leads["created_date"].dt.strftime("%Y-%m")).size().reset_index()
        leads_per_month.columns = ["month", "leads"]
        fig = px.line(leads_per_month, x="month", y="leads", markers=True, title="Leads per month",
                      labels={"month": "Month", "leads": "Leads"}, color_discrete_sequence=[BLUE])
        right.plotly_chart(fig, width="stretch")

    # lead sources: volume and conversion
    if len(filtered_leads) > 0:
        left, right = st.columns(2)
        by_source = filtered_leads.groupby("lead_source").agg(leads=("lead_id", "count"),
                                                              won=("lead_status", lambda s: (s == "Won").sum())).reset_index()
        by_source["conversion"] = by_source["won"] / by_source["leads"]
        by_source = by_source.sort_values("leads")
        fig = px.bar(by_source, x="leads", y="lead_source", orientation="h", title="Leads per channel",
                     labels={"leads": "Number of leads", "lead_source": ""}, color_discrete_sequence=[BLUE])
        left.plotly_chart(fig, width="stretch")
        fig = px.bar(by_source, x="conversion", y="lead_source", orientation="h", title="Lead-to-sale conversion",
                     labels={"conversion": "Share of leads that bought", "lead_source": ""},
                     text=by_source["conversion"].map("{:.1%}".format), color_discrete_sequence=[ORANGE])
        fig.update_xaxes(tickformat=".0%")
        right.plotly_chart(fig, width="stretch")

    # broker performance (from the old HTML dashboard)
    broker_info = leads[leads["broker_id"] != "Unassigned"].drop_duplicates("broker_id")[["broker_id", "broker_name", "sales_team"]]
    broker_leads = filtered_leads.groupby("broker_id").size().reset_index(name="leads")
    broker_sales = filtered_sales.groupby("sale_broker_id").agg(sales=("unit_id", "count"),
                                                                revenue=("contract_price", "sum")).reset_index()
    broker_sales = broker_sales.rename(columns={"sale_broker_id": "broker_id"})

    brokers = broker_info.merge(broker_leads, on="broker_id", how="left").merge(broker_sales, on="broker_id", how="left")
    brokers = brokers.fillna({"leads": 0, "sales": 0, "revenue": 0})
    brokers["conversion"] = 0.0
    has_leads = brokers["leads"] > 0
    brokers.loc[has_leads, "conversion"] = brokers.loc[has_leads, "sales"] / brokers.loc[has_leads, "leads"]
    brokers["revenue_m"] = brokers["revenue"] / 1e6
    brokers = brokers.sort_values("revenue", ascending=False)

    left, right = st.columns(2)
    top_brokers = brokers.head(10).sort_values("revenue")
    fig = px.bar(top_brokers, x="revenue_m", y="broker_name", orientation="h", title="Top brokers by sales value",
                 hover_data=["sales_team", "sales"], text=top_brokers["revenue_m"].map("{:,.0f}M".format),
                 labels={"revenue_m": "Sales value (EGP millions)", "broker_name": ""}, color_discrete_sequence=[BLUE])
    left.plotly_chart(fig, width="stretch")

    teams = brokers.groupby("sales_team")[["leads", "sales", "revenue_m"]].sum().reset_index().sort_values("revenue_m")
    fig = px.bar(teams, x="revenue_m", y="sales_team", orientation="h", title="Sales value by team",
                 hover_data=["leads", "sales"], text=teams["revenue_m"].map("{:,.0f}M".format),
                 labels={"revenue_m": "Sales value (EGP millions)", "sales_team": ""}, color_discrete_sequence=[BLUE])
    right.plotly_chart(fig, width="stretch")

    st.markdown("**Broker performance**")
    broker_table = brokers[["broker_name", "sales_team", "leads", "sales", "conversion", "revenue_m"]]
    st.dataframe(broker_table, width="stretch", hide_index=True,
                 column_config={"broker_name": "Broker", "sales_team": "Team", "leads": "Leads", "sales": "Sales",
                                "conversion": st.column_config.NumberColumn("Lead-to-sale", format="percent"),
                                "revenue_m": st.column_config.NumberColumn("Sales value (EGP M)", format="%.1f")})
    unassigned = (filtered_leads["broker_id"] == "Unassigned").sum()
    st.caption(f"Leads and sales follow the sidebar filters. {unassigned} leads in the selection have no broker assigned.")

    # slow-moving units (from the old HTML dashboard)
    slow = filtered_units[filtered_units["status"] == "Available"].copy()
    slow["price_changes"] = slow["price_versions"] - 1
    slow = slow.sort_values(["leads", "viewings"])
    st.markdown(f"**Slow-moving units – {len(slow)} available units, weakest demand first**")
    slow_columns = ["unit_id", "cluster", "property_type", "bedrooms", "view_type", "launch_list_price",
                    "current_list_price", "price_vs_policy", "price_changes", "leads", "viewings"]
    st.dataframe(slow[slow_columns], width="stretch", hide_index=True,
                 column_config={"launch_list_price": st.column_config.NumberColumn("Launch price", format="localized"),
                                "current_list_price": st.column_config.NumberColumn("Current price", format="localized"),
                                "price_vs_policy": st.column_config.NumberColumn("Above policy price", format="percent")})
    st.caption("All available units have been on the market since launch (15 Apr 2024). The ones at the top got the "
               "fewest leads and viewings – good candidates for a price review or a marketing push.")


# ---------------- TAB 4: DATA ----------------
with tab_data:
    st.subheader("Filtered units")
    show_columns = ["unit_id", "cluster", "building", "property_type", "bedrooms", "built_up_area_sqm",
                    "view_type", "sea_view", "private_pool", "launch_list_price", "launch_price_per_sqm", "policy_price",
                    "price_vs_policy", "launch_margin", "status", "contract_date", "contract_price", "contract_plan",
                    "days_to_sell"]
    table = filtered_units[show_columns].sort_values("unit_id")
    st.write(f"{len(table):,} units match the sidebar filters (cluster, property type).")
    st.dataframe(table, width="stretch", hide_index=True)

    st.download_button("Download filtered data as CSV", data=filtered_units.to_csv(index=False).encode("utf-8"),
                       file_name="baghoosh_filtered_units.csv", mime="text/csv")


# ---------------- TAB 5: PREDICTION ----------------
def predict_probability(feature_table):
    # returns the model's probability that each row sells
    return model.predict_proba(feature_table[NUMERIC_FEATURES + CATEGORICAL_FEATURES])[:, 1]


with tab_prediction:
    st.subheader("Will this unit sell?")
    st.write("The model (Logistic Regression, about 70% accurate in cross-validation) estimates the chance that a Phase 1 "
             "unit sells, using only facts known on launch day. The biggest driver is how far the launch price is above "
             "the **policy price** (cost ÷ (1 – target margin) × the official premiums).")
    st.caption("This tab does not use the sidebar filters.")

    mode = st.radio("What do you want to do?", ["Existing unit – try a new price", "Custom unit"], horizontal=True)

    if mode == "Existing unit – try a new price":
        # only units that are still available can get a new price (sold and reserved units are left out)
        available = units[units["status"] == "Available"].sort_values("unit_id")
        unit_labels = available["unit_id"] + " – " + available["property_type"] + " – " + available["cluster"]
        chosen_label = st.selectbox(f"Available unit ({len(available)} units)", unit_labels)
        unit = available[unit_labels == chosen_label].iloc[0]

        info1, info2, info3, info4 = st.columns(4)
        info1.metric("Built-up area", f"{unit['built_up_area_sqm']:,.0f} sqm")
        info2.metric("Distance to beach", f"{unit['dist_beach_km']:.2f} km")
        info3.metric("Sea view / pool", f"{unit['sea_view']} / {unit['private_pool']}")
        info4.metric("Launch price", f"EGP {unit['launch_list_price'] / 1e6:,.2f}M")

        with st.form("existing_unit_form"):
            col_a, col_b = st.columns(2)
            new_price = col_a.number_input("Launch price to test (EGP)", min_value=1_000_000, max_value=200_000_000,
                                           value=int(unit["launch_list_price"]), step=100_000)
            new_plan = col_b.selectbox("Default payment plan", plan_names, index=plan_names.index(unit["default_plan"]))
            submitted = st.form_submit_button("Predict")

        # the policy price changes with the payment plan premium
        policy_price = unit["policy_price"] / (1 + plan_premium[unit["default_plan"]]) * (1 + plan_premium[new_plan])

        input_row = pd.DataFrame([unit[CATEGORICAL_FEATURES + ["built_up_area_sqm", "dist_beach_km"]]])
        input_row["default_plan"] = new_plan
        input_row["price_vs_policy"] = new_price / policy_price - 1
        input_row["price_vs_type_median"] = (new_price / unit["built_up_area_sqm"]) / type_median_ppsqm[unit["property_type"]] - 1
        probability = predict_probability(input_row)[0]

        result1, result2, result3 = st.columns(3)
        result1.metric("Chance of selling", f"{probability:.0%}")
        result2.metric("Policy price", f"EGP {policy_price / 1e6:,.2f}M")
        result3.metric("Price vs policy", f"{input_row['price_vs_policy'].iloc[0]:+.1%}")
        if input_row["price_vs_policy"].iloc[0] < 0:
            st.error("This price is below the policy price, which breaks the company's pricing policy. No unit was ever "
                     "launched below it, so the model has no data for this range – treat the prediction with caution.")
        elif probability >= 0.5:
            st.success("The model expects this unit to sell at this price.")
        else:
            st.warning("The model expects this unit to be hard to sell at this price.")

        # what-if curve: chance of selling for prices from the policy price up to +30%
        test_prices = [policy_price * (1 + step / 100) for step in range(0, 31)]
        curve = pd.concat([input_row] * len(test_prices), ignore_index=True)
        curve["price"] = test_prices
        curve["price_vs_policy"] = curve["price"] / policy_price - 1
        curve["price_vs_type_median"] = (curve["price"] / unit["built_up_area_sqm"]) / type_median_ppsqm[unit["property_type"]] - 1
        curve["probability"] = predict_probability(curve)
        curve["price_m"] = curve["price"] / 1e6

        fig = px.line(curve, x="price_m", y="probability", title="Chance of selling at different launch prices",
                      labels={"price_m": "Launch price (EGP millions)", "probability": "Chance of selling"},
                      color_discrete_sequence=[BLUE])
        fig.add_vline(x=new_price / 1e6, line_dash="dash", line_color=ORANGE, annotation_text="Tested price")
        fig.add_vline(x=policy_price / 1e6, line_dash="dot", line_color=GREY, annotation_text="Policy price",
                      annotation_position="bottom right")
        fig.update_yaxes(tickformat=".0%", range=[0, 1])
        st.plotly_chart(fig, width="stretch")

    else:
        with st.form("custom_unit_form"):
            col_a, col_b, col_c = st.columns(3)
            property_type = col_a.selectbox("Property type", sorted(units["property_type"].unique()))
            area = col_a.number_input("Built-up area (sqm)", min_value=40, max_value=600, value=150, step=5)
            dist_beach = col_a.number_input("Distance to beach (km)", min_value=0.05, max_value=3.0, value=0.5, step=0.05)
            sea_view = col_b.radio("Sea view", ["Yes", "No"], horizontal=True)
            private_pool = col_b.radio("Private pool", ["No", "Yes"], horizontal=True)
            beachfront = col_b.radio("Beachfront building", ["Yes", "No"], horizontal=True)
            default_plan = col_c.selectbox("Default payment plan", plan_names)
            above_policy = col_c.slider("Launch price above the policy price (%)", 0, 30, 7)
            vs_type = col_c.slider("Price per sqm vs property-type median (%)", -30, 60, 0)
            submitted = st.form_submit_button("Predict")

        input_row = pd.DataFrame([{
            "price_vs_policy": above_policy / 100,
            "price_vs_type_median": vs_type / 100,
            "built_up_area_sqm": area,
            "dist_beach_km": dist_beach,
            "property_type": property_type,
            "sea_view": sea_view,
            "private_pool": private_pool,
            "beachfront": beachfront,
            "default_plan": default_plan,
        }])
        probability = predict_probability(input_row)[0]

        st.metric("Chance of selling", f"{probability:.0%}")
        if probability >= 0.5:
            st.success("The model expects this unit to sell.")
        else:
            st.warning("The model expects this unit to be hard to sell.")

    st.caption("Limitations: trained on 320 units, so about 3 in 10 predictions are wrong – use it to compare prices and "
               "rank units by risk, not as a guarantee. It does not know about marketing or market changes after launch.")

