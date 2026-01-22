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
        
        # --- THE FIX: pkce=False ---
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
st.sidebar.success("✅ Logged In")

if st.sidebar.button("Logout"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

st.title("🏗️ Y4J Candidate Info Builder")

with st.form("entry_form", clear_on_submit=True):
    st.subheader("New Contribution")
    info_title = st.text_input("Candidate/Info Title")
    category = st.selectbox("Category", ["Finance", "Legal", "Marketing", "Research", "Other"])
    entry_date = st.date_input("Document Date", date.today())
    details = st.text_area("Details/Description")
    
    st.divider()
    uploaded_file = st.file_uploader("Upload PDF or Image", type=["pdf", "png", "jpg", "jpeg"])
    camera_photo = st.camera_input("OR Take a photo now")

    submit = st.form_submit_button("🚀 Upload to Production Drive", use_container_width=True)

# --- 6. SUBMISSION LOGIC ---
if submit:
    if not info_title:
        st.error("Error: Please provide a title.")
    else:
        with st.spinner("Pushing to 2 TB Storage..."):
            success = True
            
            # A. Upload the Text Details
            text_filename = f"{entry_date}_{category}_{info_title}_notes.txt"
            res_text = upload_to_drive(text_filename, details.encode('utf-8'), 'text/plain')
            if not res_text: success = False

            # B. Upload File
            if uploaded_file:
                res_file = upload_to_drive(uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)
                if not res_file: success = False

            # C. Upload Camera Photo
            if camera_photo:
                photo_name = f"{entry_date}_{info_title}_photo.jpg"
                res_cam = upload_to_drive(photo_name, camera_photo.getvalue(), 'image/jpeg')
                if not res_cam: success = False

            if success:
                st.success(f"Successfully uploaded '{info_title}' records!")
                st.balloons()
