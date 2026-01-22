import streamlit as st
import io
from datetime import date
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.auth.transport.requests import Request

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="Y4J Volunteer Portal", page_icon="🏗️", layout="centered")

# --- 2. CONFIGURATION & CONSTANTS ---
# Folder where uploads will go (The 2TB Drive Folder)
FOLDER_ID = "1_XXSyakCqZdKq72LFTd2g7iqH0enpt9L"

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
    
    # Construct the client config
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
    This ensures uploads go to YOUR central 2TB account, not the user's account.
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
