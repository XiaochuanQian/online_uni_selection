import streamlit as st
import pandas as pd
import os
from datetime import datetime, timezone
import time
import filelock
import io
import json

# List of 50 universities
universities = [
    "Barnard College", "Boston University", "Carleton College", "Carnegie Mellon University",
    "Case Western Reserve University", "Chinese University of Hong Kong", "Claremont McKenna College",
    "Cornell University", "Duke University", "Emory University", "Georgia Institute of Technology",
    "Hong Kong University of Science and Technology", "Imperial College London", "Johns Hopkins University",
    "London School of Economics and Political Science", "Middlebury College", "National University of Singapore",
    "Nanyang Technological University", "New York University", "Northeastern University", "Northwestern University",
    "Rice University", "University College London", "University of California, Berkeley",
    "University of California, Davis",
    "University of California, Irvine", "University of California, Los Angeles", "University of California, San Diego",
    "University of California, Santa Barbara", "University of Cambridge", "University of Chicago",
    "University of Florida",
    "University of Hong Kong", "University of Illinois Urbana-Champaign", "University of Michigan, Ann Arbor",
    "University of North Carolina at Chapel Hill", "University of Notre Dame",
    "University of Oxford", "University of Rochester", "University of Southern California", "University of Toronto",
    "University of Virginia", "University of Washington", "University of Waterloo", "University of Wisconsin, Madison",
    "Vanderbilt University", "Washington University in St. Louis", "Wesleyan University",
]

# File to store selections
EXCEL_FILE = "university_selections.xlsx"
LOCK_FILE = "university_selections.lock"
CONFIG_FILE = "config.json"

# Default start and end times for selections (UTC)
DEFAULT_START_TIME = datetime(2024, 9, 3, 0, 0, 0, tzinfo=timezone.utc)
DEFAULT_END_TIME = datetime(2024, 9, 20, 23, 59, 59, tzinfo=timezone.utc)

# Refresh interval in seconds
REFRESH_INTERVAL = 3

# Admin credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "123123"


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as file:
            config = json.load(file)
            start_time = datetime.fromisoformat(config.get("start_time"))
            end_time = datetime.fromisoformat(config.get("end_time"))
            return start_time, end_time
    else:
        return DEFAULT_START_TIME, DEFAULT_END_TIME


def save_config(start_time, end_time):
    config = {
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat()
    }
    with open(CONFIG_FILE, "w") as file:
        json.dump(config, file)


# Cache the start and end times
@st.cache_data(ttl=REFRESH_INTERVAL)
def get_selection_times():
    return load_config()


# Cache the dataframe
@st.cache_data(ttl=REFRESH_INTERVAL)
def get_dataframe():
    with filelock.FileLock(LOCK_FILE):
        if not os.path.exists(EXCEL_FILE):
            df = pd.DataFrame(columns=["University", "Names", "Slots", "Selected"])
            for uni in universities:
                new_row = pd.DataFrame({"University": [uni], "Names": [""], "Slots": [1], "Selected": [False]})
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
                        new_row = pd.DataFrame({"University": [uni], "Names": [""], "Slots": [1], "Selected": [False]})
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


def is_selection_time(start_time, end_time):
    now = datetime.now(timezone.utc)
    return start_time <= now <= end_time


def main():
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Home", "Admin"])

    # Check if the admin parameter is present in the URL
    try:
        query_params = st.query_params["admin"]
        is_admin = query_params.lower() == "true"
    except:
        is_admin = False


    if page == "Home":
        home_page()
    elif page == "Admin" and is_admin:
        admin_page()
    else:
        st.error("Unauthorized access")


def home_page():
    st.title("University Selection")

    start_time, end_time = get_selection_times()

    if not is_selection_time(start_time, end_time):
        st.error(f"Selections are only allowed between {start_time} and {end_time} UTC.")
        return

    # Class selection
    class_options = [f"11.{i}" for i in range(1, 8)]
    selected_class = st.selectbox("Select your class", class_options)

    num_names = st.number_input("Number of names to submit (omit this entry)", min_value=1, max_value=1, value=1)
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
            # Modify names to include class information
            names_with_class = [f"{name} ({selected_class})" for name in names]
            success, message = add_selections(names_with_class, university)
            if success:
                st.success(f"Thank you! The selection of {university} has been recorded for {', '.join(names_with_class)}.")
            else:
                st.error(message)

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


def admin_page():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if st.session_state.logged_in:
        admin_dashboard()
    else:
        st.title("Admin Login")

        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("Invalid credentials")


def admin_dashboard():
    st.title("Admin Dashboard")

    # Load current selection times
    start_time, end_time = get_selection_times()

    # Input fields for new start and end times
    new_start_date = st.date_input("New Start Date", start_time.date())
    new_start_time = st.time_input("New Start Time", start_time.time())
    new_end_date = st.date_input("New End Date", end_time.date())
    new_end_time = st.time_input("New End Time", end_time.time())

    # Combine date and time inputs into datetime objects
    new_start_datetime = datetime.combine(new_start_date, new_start_time, tzinfo=timezone.utc)
    new_end_datetime = datetime.combine(new_end_date, new_end_time, tzinfo=timezone.utc)

    # Update selection times if the new start time is before the new end time
    if st.button("Update Times"):
        if new_start_datetime < new_end_datetime:
            save_config(new_start_datetime, new_end_datetime)
            get_selection_times.clear()
            st.success("Selection times updated successfully!")
        else:
            st.error("Start time must be before end time")

    st.subheader("Download Final Excel Worksheet")
    df = get_dataframe()

    # Write the DataFrame to a BytesIO buffer
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    buffer.seek(0)

    # Download button for the final Excel worksheet
    st.download_button(
        label="Download Excel Worksheet",
        data=buffer,
        file_name="university_selections_final.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # Clear submissions section
    st.subheader("Clear All Submissions")

    if 'clear_state' not in st.session_state:
        st.session_state.clear_state = 'initial'

    if st.session_state.clear_state == 'initial':
        if st.button("Clear All Submissions"):
            st.session_state.clear_state = 'confirm'
            st.rerun()

    elif st.session_state.clear_state == 'confirm':
        st.warning("Are you sure you want to clear all submissions? This action cannot be undone.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Yes, I'm sure"):
                clear_all_submissions()
                st.session_state.clear_state = 'cleared'
                st.rerun()
        with col2:
            if st.button("Cancel"):
                st.session_state.clear_state = 'initial'
                st.rerun()

    elif st.session_state.clear_state == 'cleared':
        st.success("All submissions have been cleared.")
        if st.button("OK"):
            st.session_state.clear_state = 'initial'
            st.rerun()

    # Logout button
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()


def clear_all_submissions():
    # Clear the Excel file
    df = pd.DataFrame(columns=["University", "Names", "Slots", "Selected"])
    for uni in universities:
        new_row = pd.DataFrame({"University": [uni], "Names": [""], "Slots": [1], "Selected": [False]})
        df = pd.concat([df, new_row], ignore_index=True)
    df.to_excel(EXCEL_FILE, index=False)

    # Delete the lock file if it exists
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)

    # Clear the cache
    get_dataframe.clear()

if __name__ == "__main__":
    main()