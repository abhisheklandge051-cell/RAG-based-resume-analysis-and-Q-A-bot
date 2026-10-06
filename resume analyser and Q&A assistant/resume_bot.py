import streamlit as st
from groq import Groq
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
from pypdf import PdfReader
from docx import Document
from dotenv import load_dotenv
import os
import time
from langchain_text_splitters import RecursiveCharacterTextSplitter
import io
from pathlib import Path
import re
from streamlit_frontend import show_auth_page, show_user_sidebar, update_user_resumes, get_user_data


# ------------------ CONFIG ------------------
load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    st.error("❌ GROQ_API_KEY not found in .env file")
    st.stop()

# Initialize Groq client
client = Groq(api_key=api_key)

# Create user uploads directory
UPLOADS_DIR = "user_uploads"
Path(UPLOADS_DIR).mkdir(exist_ok=True)

# ------------------ PAGE ------------------
st.set_page_config(
    page_title="Resume AI Bot",
    page_icon="🤖",
    layout="wide"
)

# ==================== AUTHENTICATION CHECK ====================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_email = None
    st.session_state.user_name = None
    st.session_state.user_resumes = []
    st.session_state.auth_page = "login"

# Redirect to login if not authenticated
if not st.session_state.authenticated:
    show_auth_page()
    st.stop()

# ==================== MAIN APP ====================
st.title("🤖 Resume AI Assistant")

# Show user sidebar
show_user_sidebar()

# ------------------ SESSION STATE ------------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "index" not in st.session_state:
    st.session_state.index = None
if "chunks" not in st.session_state:
    st.session_state.chunks = []
if "resume_uploaded" not in st.session_state:
    st.session_state.resume_uploaded = False
if "processing" not in st.session_state:
    st.session_state.processing = False
if "embedding_model" not in st.session_state:
    st.session_state.embedding_model = None
if "resume_text" not in st.session_state:
    st.session_state.resume_text = ""
if "current_file_name" not in st.session_state:
    st.session_state.current_file_name = None
if "last_uploaded_file_name" not in st.session_state:
    st.session_state.last_uploaded_file_name = None
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

# ------------------ LOAD MODEL ONCE ------------------
@st.cache_resource
def load_embedding_model():
    with st.spinner("Loading AI model... This may take a moment."):
        return SentenceTransformer("all-MiniLM-L6-v2")

# Load model only once
if st.session_state.embedding_model is None:
    st.session_state.embedding_model = load_embedding_model()

embedding_model = st.session_state.embedding_model

# Initialize selected resume index
if "selected_resume_idx" not in st.session_state:
    st.session_state.selected_resume_idx = None

if "auto_load_attempted" not in st.session_state:
    st.session_state.auto_load_attempted = False

# Auto-load saved resume on login if available and not already loaded/attempted
if not st.session_state.resume_uploaded and st.session_state.user_resumes and not st.session_state.auto_load_attempted:
    st.session_state.selected_resume_idx = 0
    st.session_state.auto_load_attempted = True

# Get user-specific directory
def get_user_upload_dir(user_email):
    """Get user-specific upload directory"""
    user_dir = Path(UPLOADS_DIR) / user_email.replace("@", "_").replace(".", "_")
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir

# ------------------ FUNCTIONS ------------------

def is_resume(text):
    text_lower = text.lower()
    
    # 1. Length check: Resumes are typically between 300 and 30000 characters.
    if len(text) < 300 or len(text) > 30000:
        return False, 0, 0, [], []
        
    # 2. Contact Information Check (essential characteristic of resumes)
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    phone_pattern = r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}'
    
    has_email = bool(re.search(email_pattern, text))
    has_phone = bool(re.search(phone_pattern, text))
    
    # 3. Resume Section Headers Check
    # We look for common section headers. In resumes, these are typically on their own line or at the beginning of a line.
    education_headers = [
        r'education', r'academic background', r'academics', r'educational qualification'
    ]
    experience_headers = [
        r'experience', r'work experience', r'professional experience', 
        r'work history', r'employment history', r'professional background'
    ]
    skills_headers = [
        r'skills', r'technical skills', r'key skills', r'expertise', 
        r'areas of expertise', r'technologies', r'core competencies'
    ]
    projects_headers = [
        r'projects', r'academic projects', r'key projects', r'personal projects'
    ]
    
    def check_header(patterns, text):
        for pattern in patterns:
            # Matches header at the start of any line (with optional numbers/bullets and trailing spaces/colons)
            regex = rf'(?m)^[\s•\-\d\.]*{pattern}[\s:]*$'
            if re.search(regex, text, re.IGNORECASE):
                return True
        return False

    has_education_hdr = check_header(education_headers, text)
    has_experience_hdr = check_header(experience_headers, text)
    has_skills_hdr = check_header(skills_headers, text)
    has_projects_hdr = check_header(projects_headers, text)
    
    headers_matched = sum([has_education_hdr, has_experience_hdr, has_skills_hdr, has_projects_hdr])
    
    # 4. Fallback keyword check (in case text extraction doesn't preserve line breaks well)
    core_found = []
    edu_match = any(re.search(rf'\b{kw}\b', text_lower) for kw in ["education", "academics", "degree", "university", "college", "school", "bachelor", "master", "studies"])
    exp_match = any(re.search(rf'\b{kw}\b', text_lower) for kw in ["experience", "employment", "work", "history", "career", "professional", "engineer", "developer", "analyst"])
    skills_match = any(re.search(rf'\b{kw}\b', text_lower) for kw in ["skills", "expertise", "technologies", "languages", "proficiencies", "competencies"])
    
    if not has_education_hdr and edu_match:
        core_found.append("education (fallback)")
    if not has_experience_hdr and exp_match:
        core_found.append("experience (fallback)")
    if not has_skills_hdr and skills_match:
        core_found.append("skills (fallback)")
        
    fallback_core_matches = len(core_found)
    
    # 5. Validation Logic
    is_valid = False
    if headers_matched >= 2:
        is_valid = True
    elif headers_matched >= 1 and (has_email or has_phone):
        is_valid = True
    elif (has_email or has_phone) and fallback_core_matches >= 2:
        is_valid = True
        
    # Prepare details for UI validation reporting
    core_found_list = []
    if has_education_hdr: core_found_list.append("Education Section")
    if has_experience_hdr: core_found_list.append("Experience Section")
    if has_skills_hdr: core_found_list.append("Skills Section")
    core_found_list.extend(core_found)
    
    supporting_found_list = []
    if has_projects_hdr: supporting_found_list.append("Projects Section")
    if has_email: supporting_found_list.append("Email Address")
    if has_phone: supporting_found_list.append("Phone Number")
    
    return is_valid, len(core_found_list), len(supporting_found_list), core_found_list, supporting_found_list


def get_resume_validation_result(text):
    """Get detailed validation result for debugging"""
    is_valid, core_count, support_count, core_found, support_found = is_resume(text)
    return {
        "is_valid": is_valid,
        "core_keywords_found": core_count,
        "support_keywords_found": support_count,
        "core_examples": core_found[:3],
        "support_examples": support_found[:3]
    }


def extract_text_from_pdf(uploaded_file):

    """Extract text from PDF with multiple fallback methods"""
    text = ""
    try:
        # Reset file pointer
        uploaded_file.seek(0)
        
        # Try PyPDF2 first
        reader = PdfReader(uploaded_file)
        total_pages = len(reader.pages)
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, page in enumerate(reader.pages):
            status_text.text(f"📖 Reading page {i+1}/{total_pages}")
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
            progress_bar.progress((i + 1) / total_pages)
        
        progress_bar.empty()
        status_text.empty()
        
        # If no text extracted, try alternative method
        if not text.strip():
            st.warning("⚠️ No text extracted with standard method. Trying alternative...")
            # Try to extract text with different method
            for i, page in enumerate(reader.pages):
                try:
                    # Try to extract using different parameters
                    page_text = page.extract_text(extraction_mode="layout")
                    if page_text:
                        text += page_text + "\n"
                except:
                    pass
        
        return text.strip()
        
    except Exception as e:
        st.error(f"Error reading PDF: {e}")
        return None

def extract_text_from_docx(uploaded_file):
    """Extract text from DOCX"""
    text = ""
    try:
        # Reset file pointer
        uploaded_file.seek(0)
        
        doc = Document(uploaded_file)
        total_paragraphs = len(doc.paragraphs)
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, para in enumerate(doc.paragraphs):
            status_text.text(f"📄 Reading paragraph {i+1}/{total_paragraphs}")
            if para.text:
                text += para.text + "\n"
            progress_bar.progress((i + 1) / total_paragraphs)
        
        # Also extract from tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text:
                        text += cell.text + "\n"
        
        progress_bar.empty()
        status_text.empty()
        
        return text.strip()
        
    except Exception as e:
        st.error(f"Error reading DOCX: {e}")
        return None

def extract_text(uploaded_file):
    """Extract text with file type detection"""
    if uploaded_file.name.endswith(".pdf"):
        return extract_text_from_pdf(uploaded_file)
    elif uploaded_file.name.endswith(".docx"):
        return extract_text_from_docx(uploaded_file)
    else:
        st.error("Unsupported file format")
        return None

def chunk_text(text):
    """Split text into chunks"""
    if not text or len(text) < 50:
        st.warning("⚠️ Text is too short. Minimum 50 characters required.")
        return []
    
    with st.spinner("🔄 Splitting text into chunks..."):
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=100,
            separators=["\n\n", "\n", ".", " ", ""]
        )
        chunks = splitter.split_text(text)
        return chunks

def create_vector_store(chunks):
    """Create FAISS index with progress"""
    if not chunks:
        return None, None
    
    with st.spinner(f"🧠 Creating vector embeddings for {len(chunks)} chunks..."):
        batch_size = 50
        all_embeddings = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i+batch_size]
            status_text.text(f"🔢 Processing batch {i//batch_size + 1}/{(len(chunks)//batch_size) + 1}")
            
            batch_embeddings = embedding_model.encode(batch, normalize_embeddings=True)
            all_embeddings.extend(batch_embeddings)
            
            progress_bar.progress(min((i + batch_size) / len(chunks), 1.0))
        
        progress_bar.empty()
        status_text.empty()
        
        embeddings = np.array(all_embeddings).astype("float32")
        dimension = embeddings.shape[1]
        
        with st.spinner("📊 Building FAISS index..."):
            index = faiss.IndexFlatIP(dimension)
            index.add(embeddings)
            
        return index, embeddings

def retrieve_context(question, chunks, index, k=3):
    """Retrieve relevant context"""
    if not chunks or index is None:
        return ""
    
    query_embedding = embedding_model.encode([question], normalize_embeddings=True)
    distances, indices = index.search(
        np.array(query_embedding).astype("float32"),
        min(k, len(chunks))
    )
    
    context = ""
    for idx in indices[0]:
        if idx >= 0 and idx < len(chunks):
            context += chunks[idx] + "\n\n"
    
    return context[:4000]

def ask_groq(question, context="", chat_history=None):
    """Get response from Groq API - answers all user queries without restricting to resume only"""
    
    system_instruction = (
        "You are an intelligent, helpful AI Assistant and Career Advisor.\n\n"
        "Guidelines:\n"
        "1. You are fully capable and responsible for answering ANY query from the user (technical topics, career guidance, interview preparation, coding, general knowledge, explanations, writing help, etc.).\n"
        "2. Do NOT restrict your answers only to the resume.\n"
        "3. When relevant candidate resume context is provided below, use it to personalize answers, discuss qualifications, skills, and experience, or provide tailored career recommendations.\n"
        "4. If the user asks a question not covered by the resume, or if no resume is loaded, use your broad general knowledge to provide a comprehensive, accurate, and helpful response.\n"
        "5. If the user asks for a specific personal fact that is absent from their resume (e.g., 'What is my GPA?' or 'What is my phone number?'), clarify politely that this specific detail is not found in the uploaded resume, while still providing helpful related information or suggestions.\n"
        "6. Keep responses well-structured, professional, and clear."
    )
    
    if context and context.strip():
        system_instruction += f"\n\n--- Candidate Resume Context ---\n{context.strip()}\n--------------------------------"
    
    api_messages = [{"role": "system", "content": system_instruction}]
    
    # Include recent conversation turns for context continuity
    if chat_history:
        past_turns = chat_history[:-1] if chat_history and chat_history[-1].get("content") == question else chat_history
        for msg in past_turns[-6:]:
            if msg.get("role") in ["user", "assistant"] and msg.get("content"):
                api_messages.append({"role": msg["role"], "content": msg["content"]})
                
    api_messages.append({"role": "user", "content": question})

    max_retries = 3
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=api_messages,
                temperature=0.4,
                max_tokens=1000
            )

            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content

            return "No response generated."

        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    st.warning(f"⏳ Rate limited. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                return "❌ API rate limit exceeded. Please wait a few minutes and try again."
            return f"❌ Groq Error: {e}"

    return "❌ Failed to get response after retries."

# ==================== SIDEBAR - Status Section ====================
with st.sidebar:
    st.header("📊 Status")
    
    if st.session_state.resume_uploaded:
        st.success("✅ Resume uploaded")
        st.info(f"📄 Chunks: {len(st.session_state.chunks)}")
        st.info(f"📝 Text length: {len(st.session_state.resume_text)} characters")
        
        # Show preview
        with st.expander("📄 Resume Preview"):
            preview = st.session_state.resume_text[:500]
            st.text(preview + "..." if len(st.session_state.resume_text) > 500 else preview)
    else:
        st.info("⏳ No resume loaded")
    
    if st.session_state.processing:
        st.warning("⏳ Processing...")
    
    # Clear chat button
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()
    


# ==================== FILE UPLOAD SECTION ====================
# User info in main area
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    st.markdown(f"### 👋 Welcome back, {st.session_state.user_name}!")
with col3:
    st.markdown(f"*Logged in as: {st.session_state.user_email}*")

st.markdown("---")

# File upload section
st.markdown("### 📄 Upload Your Resume")

uploaded_file = st.file_uploader(
    "Choose a PDF or DOCX file",
    type=["pdf", "docx"],
    key=f"resume_uploader_{st.session_state.uploader_key}",
    help="Upload your resume to analyze it with AI"
)

# Detect if the user cleared the file uploader
if uploaded_file is None:
    if st.session_state.last_uploaded_file_name is not None:
        st.session_state.resume_uploaded = False
        st.session_state.resume_text = ""
        st.session_state.index = None
        st.session_state.chunks = []
        st.session_state.current_file_name = None
        st.session_state.last_uploaded_file_name = None
        st.session_state.processing = False
        st.rerun()

# Debug info
if uploaded_file:
    st.info(f"📁 File: {uploaded_file.name} ({uploaded_file.size/1024:.1f} KB)")

# Process selected resume
if st.session_state.selected_resume_idx is not None and not st.session_state.processing:
    st.session_state.processing = True
    idx = st.session_state.selected_resume_idx
    st.session_state.selected_resume_idx = None
    
    if 0 <= idx < len(st.session_state.user_resumes):
        resume_info = st.session_state.user_resumes[idx]
        file_path = Path(resume_info["file_path"])
        
        if file_path.exists():
            with st.spinner("📄 Loading selected resume..."):
                with open(file_path, "rb") as f:
                    resume_text = extract_text(f)
            
            if resume_text:
                st.success(f"✅ Text extracted: {len(resume_text)} characters")
                
                # Check if it's actually a resume (always validate)
                is_valid_resume, core_count, support_count, core_found, support_found = is_resume(resume_text)
                
                if not is_valid_resume:
                    st.error("❌ This file doesn't appear to be a resume.")
                    with st.expander("📋 Detection Details"):
                        st.write(f"**Core resume sections found:** {core_count}/2 required")
                        if core_found:
                            st.write(f"Examples: {', '.join(core_found[:3])}")
                        st.write(f"**Supporting keywords found:** {support_count}/1 required")
                        if support_found:
                            st.write(f"Examples: {', '.join(support_found[:5])}")
                    st.session_state.processing = False
                    st.stop()
                
                st.session_state.resume_text = resume_text
                st.session_state.current_file_name = resume_info["filename"]
                
                # Show preview
                with st.expander("📄 Preview extracted text"):
                    st.text(resume_text[:1000] + "..." if len(resume_text) > 1000 else resume_text)
                
                # Chunk text
                chunks = chunk_text(resume_text)
                
                if chunks:
                    st.success(f"✅ Created {len(chunks)} chunks")
                    
                    # Create vector store
                    index, _ = create_vector_store(chunks)
                    
                    if index is not None:
                        # Store in session state
                        st.session_state.index = index
                        st.session_state.chunks = chunks
                        st.session_state.resume_uploaded = True
                        
                        # Welcome message
                        welcome_msg = f"👋 Hello {st.session_state.user_name}! I've loaded your resume '{resume_info['filename']}'. Feel free to ask me anything about your experience, skills, education, career guidance, interview prep, or any other topic!"
                        st.session_state.messages = [{"role": "assistant", "content": welcome_msg}]
                        
                        st.success(f"✅ Loaded resume: {resume_info['filename']}")
                        st.balloons()
                        time.sleep(1)
                        st.session_state.processing = False
                        st.rerun()
                    else:
                        st.error("❌ Failed to create vector index")
                else:
                    st.error("❌ Failed to create chunks from resume.")
            else:
                st.error("❌ Failed to extract text from resume.")
        else:
            st.error(f"❌ Resume file not found at: {file_path}")
            
    st.session_state.processing = False

# Process uploaded file - process only if it's a new upload and not already processing
is_new_upload = uploaded_file is not None and uploaded_file.name != st.session_state.last_uploaded_file_name

if is_new_upload and not st.session_state.processing:
    st.session_state.processing = True
    
    with st.spinner("📄 Extracting text from resume..."):
        resume_text = extract_text(uploaded_file)
    
    if resume_text:
        # Check if it's actually a resume
        is_valid_resume, core_count, support_count, core_found, support_found = is_resume(resume_text)
        
        if not is_valid_resume:
            st.error("❌ This file doesn't appear to be a resume.")
            
            # Show what was detected for debugging
            with st.expander("📋 Detection Details"):
                st.write(f"**Core resume sections found:** {core_count}/2 required")
                if core_found:
                    st.write(f"Examples: {', '.join(core_found[:3])}")
                st.write(f"**Supporting keywords found:** {support_count}/1 required")
                if support_found:
                    st.write(f"Examples: {', '.join(support_found[:5])}")
                st.write("---")
                st.write("💡 **Tip:** Make sure your resume clearly contains sections like 'Education', 'Experience', or 'Skills'")
            
            # Reset active resume state so we don't display old/inconsistent state
            st.session_state.resume_uploaded = False
            st.session_state.resume_text = ""
            st.session_state.index = None
            st.session_state.chunks = []
            st.session_state.current_file_name = None
            # Keep the last uploaded file name so we don't re-process it infinitely
            st.session_state.last_uploaded_file_name = uploaded_file.name
            
            st.session_state.processing = False
            st.stop()
        
        # Get user upload directory
        user_upload_dir = get_user_upload_dir(st.session_state.user_email)
        
        # Save file to user directory ONLY after validation succeeds
        file_path = user_upload_dir / uploaded_file.name
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
            
        st.success(f"✅ Text extracted: {len(resume_text)} characters")
        st.session_state.resume_text = resume_text
        st.session_state.current_file_name = uploaded_file.name
        st.session_state.last_uploaded_file_name = uploaded_file.name
        
        # Update user's resume list
        resume_info = {
            "filename": uploaded_file.name,
            "file_path": str(file_path)
        }
        update_user_resumes(st.session_state.user_email, resume_info)
        
        # Update session state
        user_data = get_user_data(st.session_state.user_email)
        st.session_state.user_resumes = user_data["resumes"] if user_data else []
        
        # Show preview
        with st.expander("📄 Preview extracted text"):
            st.text(resume_text[:1000] + "..." if len(resume_text) > 1000 else resume_text)
        
        # Chunk text
        chunks = chunk_text(resume_text)
        
        if chunks:
            st.success(f"✅ Created {len(chunks)} chunks")
            
            # Create vector store
            index, _ = create_vector_store(chunks)
            
            if index is not None:
                # Store in session state
                st.session_state.index = index
                st.session_state.chunks = chunks
                st.session_state.resume_uploaded = True
                
                # Welcome message
                welcome_msg = f"👋 Hello {st.session_state.user_name}! I've analyzed your resume. Feel free to ask me anything about your experience, skills, education, career guidance, interview prep, or any other topic!"
                st.session_state.messages = [{"role": "assistant", "content": welcome_msg}]
                
                st.success("✅ Resume processing complete!")
                st.balloons()
                time.sleep(1)
                st.session_state.processing = False
                st.rerun()
            else:
                st.error("❌ Failed to create vector index")
        else:
            st.error("❌ Failed to create chunks from resume. Text might be too short or in unsupported format.")
    else:
        st.error("❌ Failed to extract text from resume. Please check if the file is a valid PDF or DOCX.")
    
    st.session_state.processing = False

# ------------------ CHAT INTERFACE ------------------
# Initialize greeting if chat is empty
if not st.session_state.messages:
    if st.session_state.resume_uploaded:
        welcome_greeting = f"👋 Hello {st.session_state.user_name}! Your resume is loaded. Feel free to ask me anything about your background, career advice, interview questions, technical concepts, or any general topic."
    else:
        welcome_greeting = f"👋 Hello {st.session_state.user_name}! I am your AI assistant. You can ask me any question, or upload your resume above for personalized analysis and guidance."
    st.session_state.messages = [{"role": "assistant", "content": welcome_greeting}]

# Information notice if no resume is currently loaded
if not st.session_state.resume_uploaded:
    st.info("💡 **Tip:** No resume uploaded yet. You can ask any questions right away, or upload a resume above for personalized analysis!")

# Display chat messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Chat input
input_placeholder = (
    "Ask anything about your resume, career advice, technical concepts, or any question..."
    if st.session_state.resume_uploaded
    else "Ask any question, career advice, or upload a resume above..."
)
question = st.chat_input(input_placeholder)

if question:
    # Add user message
    with st.chat_message("user"):
        st.write(question)
    st.session_state.messages.append({"role": "user", "content": question})
    
    # Retrieve resume context if available
    context = ""
    if st.session_state.resume_uploaded and st.session_state.index is not None and st.session_state.chunks:
        with st.spinner("🔍 Checking resume context..."):
            context = retrieve_context(
                question,
                st.session_state.chunks,
                st.session_state.index,
                k=3
            )
    
    # Get response from LLM
    with st.spinner("🤖 Generating response..."):
        answer = ask_groq(question, context, st.session_state.messages)
    
    # Add assistant response
    with st.chat_message("assistant"):
        st.write(answer)
    
    st.session_state.messages.append({"role": "assistant", "content": answer})

# ------------------ FOOTER ------------------
st.markdown("---")
st.caption("💡 Tip: Ask about skills, experience, education, career guidance, interview preparation, technical concepts, or any general topic!")