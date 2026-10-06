import streamlit as st
import json
import os
import hashlib
from datetime import datetime
from pathlib import Path
import time

# ==================== CONFIG ====================
USERS_DB_FILE = "users_db.json"
UPLOADS_DIR = "user_uploads"

# Create uploads directory if it doesn't exist
Path(UPLOADS_DIR).mkdir(exist_ok=True)

# ==================== HELPER FUNCTIONS ====================

def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def load_users():
    """Load users from JSON file"""
    if os.path.exists(USERS_DB_FILE):
        try:
            with open(USERS_DB_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_users(users):
    """Save users to JSON file"""
    with open(USERS_DB_FILE, 'w') as f:
        json.dump(users, f, indent=4)

def user_exists(email):
    """Check if user already exists"""
    users = load_users()
    return email.lower() in users

def register_user(email, password, full_name):
    """Register a new user"""
    if user_exists(email):
        return False, "Email already registered. Please use another email or login."
    
    users = load_users()
    users[email.lower()] = {
        "full_name": full_name,
        "password": hash_password(password),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "resumes": []
    }
    save_users(users)
    return True, "Registration successful! Please login with your credentials."

def verify_login(email, password):
    """Verify login credentials"""
    users = load_users()
    user_email = email.lower()
    
    if user_email not in users:
        return False, "Email not found. Please register first."
    
    if users[user_email]["password"] != hash_password(password):
        return False, "Incorrect password. Please try again."
    
    return True, users[user_email]

def get_user_data(email):
    """Get user data"""
    users = load_users()
    return users.get(email.lower())

def update_user_resumes(email, resume_info):
    """Update user's resume (overwrites any previous resume to store a single resume)"""
    users = load_users()
    user_email = email.lower()
    
    if user_email in users:
        users[user_email]["resumes"] = [{
            "filename": resume_info["filename"],
            "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "file_path": resume_info["file_path"]
        }]
        save_users(users)
        return True
    return False

def get_user_initials(name):
    """Generate initials for user profile avatar"""
    if not name:
        return "U"
    parts = name.strip().split()
    if len(parts) >= 2:
        return f"{parts[0][0]}{parts[-1][0]}".upper()
    return parts[0][:2].upper()

# ==================== CUSTOM STYLING ====================

def inject_custom_css():
    """Inject modern, attractive custom CSS without emojis"""
    custom_css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    /* Brand Hero Header */
    .app-brand-hero {
        text-align: center;
        padding: 1.75rem 1rem 1.25rem 1rem;
        margin-bottom: 1.5rem;
    }

    .brand-badge {
        display: inline-block;
        padding: 0.3rem 0.9rem;
        background: rgba(99, 102, 241, 0.12);
        border: 1px solid rgba(99, 102, 241, 0.3);
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #6366f1;
        margin-bottom: 0.75rem;
    }

    .brand-title {
        font-size: 2.35rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        margin: 0;
        background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 50%, #db2777 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .brand-subtitle {
        font-size: 0.95rem;
        opacity: 0.75;
        margin-top: 0.45rem;
        font-weight: 400;
    }

    /* Form Container & Titles */
    .auth-card-header {
        margin-bottom: 1.25rem;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid rgba(148, 163, 184, 0.2);
    }

    .auth-title {
        font-size: 1.35rem;
        font-weight: 700;
        letter-spacing: -0.01em;
        margin: 0;
    }

    .auth-desc {
        font-size: 0.85rem;
        opacity: 0.7;
        margin-top: 0.25rem;
        margin-bottom: 0;
    }

    /* Feature Box in Register Page */
    .feature-box {
        background: rgba(99, 102, 241, 0.05);
        border: 1px solid rgba(99, 102, 241, 0.18);
        border-radius: 12px;
        padding: 1.1rem 1.3rem;
        margin-top: 1.25rem;
    }

    .feature-box-title {
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #6366f1;
        margin-bottom: 0.6rem;
    }

    .feature-item {
        display: flex;
        align-items: center;
        font-size: 0.83rem;
        opacity: 0.85;
        margin-bottom: 0.45rem;
        line-height: 1.4;
    }

    .feature-item::before {
        content: "";
        display: inline-block;
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: #6366f1;
        margin-right: 0.65rem;
        flex-shrink: 0;
    }

    /* Sidebar Profile Card */
    .profile-card {
        background: rgba(148, 163, 184, 0.08);
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-radius: 14px;
        padding: 1.2rem;
        margin-bottom: 1rem;
    }

    .profile-avatar {
        width: 44px;
        height: 44px;
        border-radius: 10px;
        background: linear-gradient(135deg, #4f46e5, #7c3aed);
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 1rem;
        color: #ffffff;
        margin-bottom: 0.75rem;
        box-shadow: 0 4px 10px rgba(79, 70, 229, 0.3);
    }

    .profile-name {
        font-size: 1.05rem;
        font-weight: 700;
        margin: 0;
        line-height: 1.2;
    }

    .profile-email {
        font-size: 0.8rem;
        opacity: 0.75;
        margin-top: 0.25rem;
        word-break: break-all;
    }

    .profile-chip {
        display: inline-block;
        margin-top: 0.65rem;
        padding: 0.2rem 0.65rem;
        border-radius: 6px;
        font-size: 0.7rem;
        font-weight: 600;
        background: rgba(16, 185, 129, 0.12);
        color: #059669;
        border: 1px solid rgba(16, 185, 129, 0.25);
    }

    /* Sidebar Resume Card */
    .resume-section-title {
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #6366f1;
        margin-top: 1rem;
        margin-bottom: 0.4rem;
    }

    .resume-card {
        background: rgba(99, 102, 241, 0.06);
        border: 1px solid rgba(99, 102, 241, 0.18);
        border-radius: 10px;
        padding: 0.85rem 1rem;
        margin-bottom: 0.75rem;
    }

    .resume-card-title {
        font-size: 0.85rem;
        font-weight: 600;
        word-break: break-word;
    }

    .resume-card-date {
        font-size: 0.72rem;
        opacity: 0.75;
        margin-top: 0.25rem;
    }

    /* Button Enhancements */
    div.stButton > button {
        border-radius: 8px;
        font-weight: 600;
        font-size: 0.88rem;
        transition: all 0.18s ease;
    }

    div.stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    }

    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%) !important;
        border: none !important;
        color: #ffffff !important;
    }

    div.stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #4338ca 0%, #6d28d9 100%) !important;
        box-shadow: 0 4px 14px rgba(79, 70, 229, 0.35) !important;
    }
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)

# ==================== AUTH UI FUNCTIONS ====================

def show_login_page():
    """Display login page"""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        <div class="auth-card-header">
            <h2 class="auth-title">Account Login</h2>
            <p class="auth-desc">Enter your credentials to access your assistant workspace</p>
        </div>
        """, unsafe_allow_html=True)
        
        email = st.text_input(
            "Email Address",
            placeholder="your.email@example.com",
            key="login_email"
        )
        
        password = st.text_input(
            "Password",
            type="password",
            placeholder="Enter your password",
            key="login_password"
        )
        
        col_login, col_demo = st.columns(2)
        
        with col_login:
            if st.button("Sign In", use_container_width=True, type="primary"):
                if not email or not password:
                    st.error("Please fill in all fields")
                else:
                    success, result = verify_login(email, password)
                    
                    if success:
                        st.session_state.authenticated = True
                        st.session_state.user_email = email.lower()
                        st.session_state.user_name = result["full_name"]
                        st.session_state.user_resumes = result["resumes"]
                        st.success("Login successful. Redirecting...")
                        st.rerun()
                    else:
                        st.error(result)
        
        with col_demo:
            if st.button("Demo Account", use_container_width=True):
                # Ensure demo user exists in DB so their uploads can be tracked/saved
                if not user_exists("demo@example.com"):
                    register_user("demo@example.com", "demopassword", "Demo User")
                
                user_data = get_user_data("demo@example.com")
                
                st.session_state.authenticated = True
                st.session_state.user_email = "demo@example.com"
                st.session_state.user_name = "Demo User"
                st.session_state.user_resumes = user_data["resumes"] if user_data else []
                st.info("Authenticated with demo account")
                st.rerun()
        
        st.markdown("---")
        
        if st.button("Create New Account", use_container_width=True):
            st.session_state.auth_page = "register"
            st.rerun()

def show_register_page():
    """Display registration page"""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        <div class="auth-card-header">
            <h2 class="auth-title">Create Account</h2>
            <p class="auth-desc">Register to analyze your resumes and chat with AI</p>
        </div>
        """, unsafe_allow_html=True)
        
        full_name = st.text_input(
            "Full Name",
            placeholder="Abhishek Landge",
            key="register_name"
        )
        
        email = st.text_input(
            "Email Address",
            placeholder="your.email@example.com",
            key="register_email"
        )
        
        password = st.text_input(
            "Password",
            type="password",
            placeholder="At least 6 characters",
            key="register_password"
        )
        
        confirm_password = st.text_input(
            "Confirm Password",
            type="password",
            placeholder="Re-enter your password",
            key="register_confirm_password"
        )
        
        col_register, col_back = st.columns(2)
        
        with col_register:
            if st.button("Register", use_container_width=True, type="primary"):
                if not all([full_name, email, password, confirm_password]):
                    st.error("Please fill in all fields")
                elif password != confirm_password:
                    st.error("Passwords do not match")
                elif len(password) < 6:
                    st.error("Password must be at least 6 characters")
                else:
                    success, message = register_user(email, password, full_name)
                    
                    if success:
                        st.success(message)
                        st.info("Redirecting to login...")
                        time.sleep(1)
                        st.session_state.auth_page = "login"
                        st.rerun()
                    else:
                        st.error(message)
        
        with col_back:
            if st.button("Back to Sign In", use_container_width=True):
                st.session_state.auth_page = "login"
                st.rerun()
        
        st.markdown("""
        <div class="feature-box">
            <div class="feature-box-title">Account Benefits</div>
            <div class="feature-item">Secure personal credential management</div>
            <div class="feature-item">Upload and store PDF and DOCX resume profiles</div>
            <div class="feature-item">Instant access to resume vector embeddings</div>
            <div class="feature-item">AI-assisted career guidance and query answering</div>
        </div>
        """, unsafe_allow_html=True)

def show_auth_page():
    """Main authentication page"""
    inject_custom_css()
    
    # Initialize auth_page in session state
    if "auth_page" not in st.session_state:
        st.session_state.auth_page = "login"
    
    # Header Hero
    st.markdown("""
    <div class="app-brand-hero">
        <span class="brand-badge">AI Career Platform</span>
        <h1 class="brand-title">Resume AI Assistant</h1>
        <p class="brand-subtitle">Intelligent Resume Analysis & Career Guidance</p>
    </div>
    """, unsafe_allow_html=True)
    
    if st.session_state.auth_page == "login":
        show_login_page()
    elif st.session_state.auth_page == "register":
        show_register_page()

# ==================== USER SIDEBAR ====================

def show_user_sidebar():
    """Display user information in sidebar"""
    inject_custom_css()
    
    with st.sidebar:
        st.markdown("---")
        
        # User Profile Card
        initials = get_user_initials(st.session_state.user_name)
        st.markdown(f"""
        <div class="profile-card">
            <div class="profile-avatar">{initials}</div>
            <div class="profile-name">{st.session_state.user_name}</div>
            <div class="profile-email">{st.session_state.user_email}</div>
            <span class="profile-chip">Active Session</span>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Show active resume
        st.markdown('<div class="resume-section-title">Active Resume</div>', unsafe_allow_html=True)
        if st.session_state.user_resumes:
            resume = st.session_state.user_resumes[0]
            st.markdown(f"""
            <div class="resume-card">
                <div class="resume-card-title">{resume['filename']}</div>
                <div class="resume-card-date">Uploaded: {resume['uploaded_at']}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.caption("No resume uploaded yet")
        
        st.markdown("---")
        
        if st.button("Sign Out", use_container_width=True):
            st.session_state.clear()
            st.rerun()
