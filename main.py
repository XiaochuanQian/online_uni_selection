import streamlit as st
import pandas as pd
import os
from datetime import datetime, timezone
import filelock
import time

# List of 50 universities
universities = [
    "Harvard University", "Stanford University", "MIT", "University of California, Berkeley",
    "University of Oxford", "University of Cambridge", "California Institute of Technology",
    "Columbia University", "University of Chicago", "Yale University",
    # Add 40 more universities here to complete the list of 50
]

# File to store selections
EXCEL_FILE = "university_selections.xlsx"
LOCK_FILE = "university_selections.lock"

# Set the start and end times for selections (UTC)
START_TIME = datetime(2024, 9, 1, 0, 0, 0, tzinfo=timezone.utc)
END_TIME = datetime(2024, 9, 20, 23, 59, 59, tzinfo=timezone.utc)

# Refresh interval in seconds
REFRESH_INTERVAL = 2


@st.cache_data(ttl=REFRESH_INTERVAL)
def get_dataframe():
    with filelock.FileLock(LOCK_FILE):
        if not os.path.exists(EXCEL_FILE):
            df = pd.DataFrame(columns=["University", "Names", "Slots", "Selected"])
            for uni in universities:
                new_row = pd.DataFrame({"University": [uni], "Names": [""], "Slots": [4], "Selected": [False]})
                df = pd.concat([df, new_row], ignore_index=True)
            df.to_excel(EXCEL_FILE, index=False)
        else:
            df = pd.read_excel(EXCEL_FILE)
            if "Selected" not in df.columns:
                df["Selected"] = False
            if len(df) < len(universities):
                existing_unis = df["University"].tolist()
                for uni in universities:
                    if uni not in existing_unis:
                        new_row = pd.DataFrame({"University": [uni], "Names": [""], "Slots": [4], "Selected": [False]})
                        df = pd.concat([df, new_row], ignore_index=True)
                df.to_excel(EXCEL_FILE, index=False)
    return df


def add_selections(names, university):
    with filelock.FileLock(LOCK_FILE):
        df = pd.read_excel(EXCEL_FILE)
        uni_row = df[df["University"] == university].index[0]
        if df.at[uni_row, "Selected"]:
            return False, "This university has already been selected. Please choose another."
        if df.at[uni_row, "Slots"] < len(names):
            return False, f"Not enough slots available. Only {df.at[uni_row, 'Slots']} slots left for this university."

        current_names = str(df.at[uni_row, "Names"]).split(", ") if pd.notna(df.at[uni_row, "Names"]) and df.at[
            uni_row, "Names"] != "" else []
        current_names.extend(names)
        df.at[uni_row, "Names"] = ", ".join(current_names)
        df.at[uni_row, "Slots"] = max(0, df.at[uni_row, "Slots"] - len(names))
        df.at[uni_row, "Selected"] = True
        df.to_excel(EXCEL_FILE, index=False)
        # Clear the cache to reflect changes immediately
        get_dataframe.clear()
        return True, "Selection successful"


def are_names_used(names):
    df = get_dataframe()
    all_names = [name for names_str in df["Names"] if pd.notna(names_str) for name in names_str.split(", ") if name]
    return any(name in all_names for name in names)


@st.cache_data(ttl=REFRESH_INTERVAL)
def get_available_universities():
    df = get_dataframe()
    return df[(df["Slots"] > 0) & (df["Selected"] == False)]["University"].tolist()


def is_selection_time():
    now = datetime.now(timezone.utc)
    return START_TIME <= now <= END_TIME


def main():
    st.title("University Selection")

    if not is_selection_time():
        st.error(f"Selections are only allowed between {START_TIME} and {END_TIME} UTC.")
        return

    num_names = st.number_input("Number of names to submit (2-4)", min_value=2, max_value=4, value=2)
    names = [st.text_input(f"Name {i + 1}") for i in range(num_names)]

    available_universities = get_available_universities()

    if not available_universities:
        st.warning("All universities have been selected. No more selections can be made.")
        return

    university = st.selectbox("Choose a University", available_universities)

    if st.button("Submit"):
        if any(not name for name in names):
            st.error("Please enter all names.")
        elif are_names_used(names):
            st.error("One or more of these names have already been used.")
        else:
            success, message = add_selections(names, university)
            if success:
                st.success(f"Thank you! The selection of {university} has been recorded for {', '.join(names)}.")
            else:
                st.error(message)

    st.markdown(
        """
        <style>
       div[data-testid="stStatusWidget"] div button {
            display: none;
            }
        
        
            </style>
        
    """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <style>
       div[data-testid="stBaseButton-headerNoPadding"] div div {
            display: none;
            }
        
        
            </style>
        
    """,
        unsafe_allow_html=True,
    )
    # Display current selections
    st.subheader("Current Selections")
    df = get_dataframe()
    st.dataframe(df[["University", "Names", "Slots", "Selected"]])

    # Add a placeholder for the refresh countdown
    placeholder = st.empty()

    # Countdown for refresh
    for seconds in range(REFRESH_INTERVAL, 0, -1):
        placeholder.text(f"Page will refresh in {seconds} seconds...")
        time.sleep(1)

    # Rerun the app
    st.rerun()


if __name__ == "__main__":
    main()