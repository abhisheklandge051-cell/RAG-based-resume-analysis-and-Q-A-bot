import streamlit as st
import json
import os
import hashlib
from datetime import datetime
from pathlib import Path

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
        return False, "❌ Email already registered. Please use another email or login."
    
    users = load_users()
    users[email.lower()] = {
        "full_name": full_name,
        "password": hash_password(password),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "resumes": []
    }
    save_users(users)
    return True, "✅ Registration successful! Please login with your credentials."

def verify_login(email, password):
    """Verify login credentials"""
    users = load_users()
    user_email = email.lower()
    
    if user_email not in users:
        return False, "❌ Email not found. Please register first."
    
    if users[user_email]["password"] != hash_password(password):
        return False, "❌ Incorrect password. Please try again."
    
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

# ==================== AUTH UI FUNCTIONS ====================

def show_login_page():
    """Display login page"""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("## 🔐 Login to Resume AI Assistant")
        st.markdown("---")
        
        email = st.text_input(
            "📧 Email",
            placeholder="your.email@example.com",
            key="login_email"
        )
        
        password = st.text_input(
            "🔑 Password",
            type="password",
            placeholder="Enter your password",
            key="login_password"
        )
        
        col_login, col_demo = st.columns(2)
        
        with col_login:
            if st.button("🚀 Login", use_container_width=True, type="primary"):
                if not email or not password:
                    st.error("❌ Please fill in all fields")
                else:
                    success, result = verify_login(email, password)
                    
                    if success:
                        st.session_state.authenticated = True
                        st.session_state.user_email = email.lower()
                        st.session_state.user_name = result["full_name"]
                        st.session_state.user_resumes = result["resumes"]
                        st.success("✅ Login successful! Redirecting...")
                        st.rerun()
                    else:
                        st.error(result)
        
        with col_demo:
            if st.button("👤 Demo Login", use_container_width=True):
                # Ensure demo user exists in DB so their uploads can be tracked/saved
                if not user_exists("demo@example.com"):
                    register_user("demo@example.com", "demopassword", "Demo User")
                
                user_data = get_user_data("demo@example.com")
                
                st.session_state.authenticated = True
                st.session_state.user_email = "demo@example.com"
                st.session_state.user_name = "Demo User"
                st.session_state.user_resumes = user_data["resumes"] if user_data else []
                st.info("✅ Using demo account for testing")
                st.rerun()
        
        st.markdown("---")
        
        if st.button("📝 Don't have an account? Register here", use_container_width=True):
            st.session_state.auth_page = "register"
            st.rerun()

def show_register_page():
    """Display registration page"""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("## 📋 Create Your Account")
        st.markdown("---")
        
        full_name = st.text_input(
            "👤 Full Name",
            placeholder="Abhishek Landge",
            key="register_name"
        )
        
        email = st.text_input(
            "📧 Email",
            placeholder="your.email@example.com",
            key="register_email"
        )
        
        password = st.text_input(
            "🔑 Password",
            type="password",
            placeholder="At least 6 characters",
            key="register_password"
        )
        
        confirm_password = st.text_input(
            "🔑 Confirm Password",
            type="password",
            placeholder="Re-enter your password",
            key="register_confirm_password"
        )
        
        col_register, col_back = st.columns(2)
        
        with col_register:
            if st.button("✅ Register", use_container_width=True, type="primary"):
                if not all([full_name, email, password, confirm_password]):
                    st.error("❌ Please fill in all fields")
                elif password != confirm_password:
                    st.error("❌ Passwords do not match")
                elif len(password) < 6:
                    st.error("❌ Password must be at least 6 characters")
                else:
                    success, message = register_user(email, password, full_name)
                    
                    if success:
                        st.success(message)
                        st.info("🔄 Redirecting to login...")
                        import time
                        time.sleep(1)
                        st.session_state.auth_page = "login"
                        st.rerun()
                    else:
                        st.error(message)
        
        with col_back:
            if st.button("🔙 Back to Login", use_container_width=True):
                st.session_state.auth_page = "login"
                st.rerun()
        
        st.markdown("---")
        
        # Show info box
        st.info("""
        **Registration Info:**
        - Secure account creation
        - Store multiple resumes
        - Access your data anytime
        - AI-powered resume analysis
        """)

def show_auth_page():
    """Main authentication page"""
    # Initialize auth_page in session state
    if "auth_page" not in st.session_state:
        st.session_state.auth_page = "login"
    
    # Header
    st.markdown("""
    <div style='text-align: center; margin-bottom: 2rem;'>
        <h1>🤖 Resume AI Assistant</h1>
        <p style='color: gray;'>Intelligent Resume Analysis & Career Guidance</p>
    </div>
    """, unsafe_allow_html=True)
    
    if st.session_state.auth_page == "login":
        show_login_page()
    elif st.session_state.auth_page == "register":
        show_register_page()

# ==================== USER SIDEBAR ====================

def show_user_sidebar():
    """Display user information in sidebar"""
    with st.sidebar:
        st.markdown("---")
        st.markdown(f"### 👤 {st.session_state.user_name}")
        st.markdown(f"📧 {st.session_state.user_email}")
        
        st.markdown("---")
        
        # Show active resume
        if st.session_state.user_resumes:
            st.markdown("### 📄 Active Resume")
            resume = st.session_state.user_resumes[0]
            st.caption(f"📄 **{resume['filename']}**")
            st.caption(f"⏰ {resume['uploaded_at']}")
        else:
            st.caption("No resume uploaded yet")
        
        st.markdown("---")
        
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.clear()
            st.rerun()

