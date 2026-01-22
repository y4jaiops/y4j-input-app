import streamlit as st
import io
import os
from datetime import date
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.auth.transport.requests import Request

# --- 0. CRITICAL FIXES ---
# Allow the app to accept "Full Drive" scope if the user granted it previously
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="Y4J Volunteer Portal", page_icon="🏗️", layout="centered")

# --- 2. CONFIGURATION & CONSTANTS ---
# Folder where uploads will go (The 2TB Drive Folder)
FOLDER_ID = "1Vavl3N2vLsJtIY7xdsrjB_fi2LMS1tfU"

# Check for secrets
if "auth" not in st.secrets:
    st.error("Missing [auth] section in secrets.toml.")
    st.stop()
if "google_auth" not in st.secrets:
    st.error("Missing [google_auth] section in secrets.toml (needed for Drive uploads).")
    st.stop()

# --- 3. HELPER FUNCTIONS ---

def get_google_flow():
    """Creates the OAuth flow for User Login."""
    auth_secrets = st.secrets["auth"]
    
    # Construct the client config dictionary
    client_config = {
        "web": {
            "client_id": auth_secrets["client_id"],
            "client_secret": auth_secrets["client_secret"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [auth_secrets["redirect_uri"]],
        }
    }

    return Flow.from_client_config(
        client_config,
        scopes=[
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/drive.file"
        ],
        redirect_uri=auth_secrets["redirect_uri"]
    )

def get_production_drive_service():
    """
    Creates a Drive Service using the 'refresh_token' from secrets.
    This ensures uploads go to YOUR central 2TB account.
    """
    auth = st.secrets["google_auth"]
    
    creds = Credentials(
        token=None,
        refresh_token=auth["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=auth["client_id"],
        client_secret=auth["client_secret"]
    )
    
    # Refresh if expired
    if not creds.valid:
        creds.refresh(Request())
        
    return build('drive', 'v3', credentials=creds)

def upload_to_drive(file_name, file_content, mime_type):
    """Uploads a file to the configured FOLDER_ID."""
    try:
        service = get_production_drive_service()
        
        file_metadata = {
            'name': file_name,
            'parents': [FOLDER_ID]
        }
        
        media = MediaIoBaseUpload(
            io.BytesIO(file_content), 
            mimetype=mime_type, 
            resumable=True
        )
        
        file = service.files().create(
            body=file_metadata, 
            media_body=media, 
            fields='id'
        ).execute()
        
        return file.get('id')
        
    except Exception as e:
        st.error(f"Upload failed: {e}")
        return None

# --- 4. AUTHENTICATION LOGIC (THE GATEKEEPER) ---

# Check if we are already logged in
if "credentials" not in st.session_state:
    
    # A. Handle the Return Trip (Google sending user back)
    if "code" in st.query_params:
        try:
            # Get the code from the URL
            code = st.query_params["code"]
            
            # Exchange the code for a token
            flow = get_google_flow()
            flow.fetch_token(code=code)
            
            # Save login state
            st.session_state["credentials"] = flow.credentials
            
            # Clear URL query params to prevent reload loops
            st.query_params.clear()
            st.rerun()
            
        except Exception as e:
            st.error(f"Login failed: {e}")
            st.stop()

    # B. Show Login Button (If no code and no credentials)
    else:
        st.title("🏗️ Y4J Volunteer Portal")
        st.info("Please log in to access the system.")
        
        flow = get_google_flow()
        
        # Disable PKCE to prevent invalid_grant errors
        auth_url, _ = flow.authorization_url(
            prompt='consent',
            access_type='offline',
            include_granted_scopes='true',
            pkce=False
        )
        
        st.link_button("Log in with Google", auth_url)
        st.stop()

# --- 5. MAIN APP (LOGGED IN ONLY) ---

# If code reaches here, user is logged in
creds = st.session_state["credentials"]

# --- FETCH USER INFO ---
try:
    # Build the OAuth2 service to get user details
    user_service = build('oauth2', 'v2', credentials=creds)
    user_info = user_service.userinfo().get().execute()
    
    user_email = user_info.get('email')
    user_id = user_info.get('id')
    user_name = user_info.get('name', 'Volunteer')
    user_pic = user_info.get('picture')
    
    # Display in Sidebar
    st.sidebar.success(f"✅ Logged In")
    if user_pic:
        st.sidebar.image(user_pic, width=50)
    st.sidebar.write(f"**{user_name}**")
    st.sidebar.caption(f"{user_email}")
    
except Exception as e:
    st.sidebar.warning("Logged in, but couldn't fetch profile info.")
    # Fallback values if API fails
    user_email = "Unknown User"
    user_id = "N/A"
    user_name = "Volunteer"

# Logout Button
if st.sidebar.button("Logout"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# --- MAIN FORM UI ---
st.title("🏗️ Y4J Candidate Info Builder")
st.write(f"Welcome, **{user_name}**!")

with st.form("entry_form", clear_on_submit=True):
    st.subheader("New Contribution")
    info_title = st.text_input("Candidate/Info Title")
    category = st.selectbox("Category", ["Finance", "Legal", "Marketing", "Research", "Other"])
    entry_date = st.date_input("Document Date", date.today())
    details = st.text_area("Details/Description")
