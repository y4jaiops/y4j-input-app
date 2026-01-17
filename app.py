import streamlit as st
import io
from datetime import date
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# --- CONSTANTS ---
FOLDER_ID = "1_XXSyakCqZdKq72LFTd2g7iqH0enpt9L"

if "google_auth" not in st.secrets:
    st.error("Missing [google_auth] in Streamlit Secrets! Check your App Settings.")
    st.stop()

def get_admin_creds():
    """This function is SAFE. It looks for keys in your Streamlit dashboard."""
    # Ensure "google_auth" exists in your Streamlit Cloud Secrets menu
    auth = st.secrets["google_auth"]
    
    creds = Credentials(
        token=None,
        refresh_token=auth["refresh_token"],  # Looks for the name 'refresh_token'
        token_uri="https://oauth2.googleapis.com/token",
        client_id=auth["client_id"],          # Looks for the name 'client_id'
        client_secret=auth["client_secret"]   # Looks for the name 'client_secret'
    )
    
    if not creds.valid:
        creds.refresh(Request())
        
    return creds



# --- CORE FUNCTIONS ---
def get_gdrive_service():
    """SAFE VERSION: Uses your 2 TB Refresh Token from Secrets."""
    # This pulls from the [google_auth] section of your Streamlit Secrets
    auth = st.secrets["google_auth"]
    
    creds = Credentials(
        token=None,
        refresh_token=auth["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=auth["client_id"],
        client_secret=auth["client_secret"]
    )
    
    # Automatically refresh the token if it's expired
    if not creds.valid:
        creds.refresh(Request())
        
    return build('drive', 'v3', credentials=creds)

def upload_to_drive(file_name, file_content, mime_type):
    """Uploads files using YOUR 2 TB quota."""
    try:
        service = get_gdrive_service()
        file_metadata = {
            'name': file_name,
            'parents': [FOLDER_ID]
        }
        
        media = MediaIoBaseUpload(
            io.BytesIO(file_content), 
            mimetype=mime_type, 
            resumable=True
        )
        
        # This bills storage to the account associated with the Refresh Token
        file = service.files().create(
            body=file_metadata, 
            media_body=media, 
            fields='id'
        ).execute()
        return file.get('id')
    except Exception as e:
        st.error(f"Upload failed: {e}")
        return None

# --- PAGE SETUP ---
st.set_page_config(page_title="Y4J Input App", page_icon="🏗️", layout="centered")

# --- 1. AUTHENTICATION WALL ---
if not st.user.is_logged_in:
    st.title("🏗️ Y4J Volunteer Portal")
    st.info("Please log in to access the 2 TB Production Drive.")
    if st.button("Log in with Google", type="primary"):
        st.login()
    st.stop()

# --- 2. AUTHENTICATED INTERFACE ---
st.sidebar.write(f"Logged in: **{st.user.email}**")
if st.sidebar.button("Logout"):
    st.logout()

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

# --- 4. SUBMISSION LOGIC ---
if submit:
    if not info_title:
        st.error("Error: Please provide a title.")
    else:
        with st.spinner("Pushing to 2 TB Storage..."):
            # A. Upload the Text Details
            text_filename = f"{entry_date}_{category}_{info_title}_notes.txt"
            upload_to_drive(text_filename, details.encode('utf-8'), 'text/plain')

            # B. Upload File/Camera Photo
            if uploaded_file:
                upload_to_drive(uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)
            if camera_photo:
                photo_name = f"{entry_date}_{info_title}_photo.jpg"
                upload_to_drive(photo_name, camera_photo.getvalue(), 'image/jpeg')

            st.success(f"Successfully uploaded '{info_title}' records!")
            st.balloons()
