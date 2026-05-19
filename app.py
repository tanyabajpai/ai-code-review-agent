import streamlit as st
import os
from dotenv import load_dotenv
from services.github_service import GitHubService
from services.parser_service import ParserService
from services.chunk_service import ChunkService
from agents.reviewer import ReviewerAgent
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Page config
st.set_page_config(
    page_title="AI Code Review Agent",
    page_icon="🔍",
    layout="wide"
)

# Initialize services
github_service = GitHubService()
parser_service = ParserService()
chunk_service = ChunkService()

def initialize_session_state():
    """Initialize session state variables"""
    if 'review_complete' not in st.session_state:
        st.session_state.review_complete = False
    if 'review_results' not in st.session_state:
        st.session_state.review_results = None
    if 'clone_path' not in st.session_state:
        st.session_state.clone_path = None

def cleanup_repository(clone_path):
    """Clean up cloned repository"""
    if clone_path:
        try:
            github_service.cleanup_repository(clone_path)
            logger.info(f"Cleaned up repository at {clone_path}")
        except Exception as e:
            logger.error(f"Error cleaning up repository: {str(e)}")

def run_review_pipeline(repo_url: str, api_key: str, chunk_limit: int = 3):
    """Run the complete review pipeline"""
    clone_path = None
    try:
        # Update status
        status_placeholder = st.empty()
        
        # Step 1: Clone repository
        status_placeholder.info("🔄 Cloning repository...")
        clone_path = github_service.clone_repository(repo_url)
        st.success(f"✅ Cloned: `{os.path.basename(clone_path)}`")
        
        # Step 2: Parse Python files
        status_placeholder.info("🔍 Parsing Python files...")
        parsed_files = parser_service.parse_repository(clone_path)
        
        if not parsed_files:
            st.warning("⚠️ No Python files found in repository")
            return None
            
        st.success(f"✅ Parsed {len(parsed_files)} Python files")
        
        # Step 3: Create chunks
        status_placeholder.info("📦 Creating code chunks...")
        chunks = chunk_service.create_chunks(parsed_files, chunk_limit)
        st.success(f"✅ Created {len(chunks)} chunks (limit: {chunk_limit})")
        
        # Step 4: Review code
        status_placeholder.info("🤖 Running AI code review...")
        reviewer = ReviewerAgent(api_key)
        reviews = reviewer.review_chunks(chunks)
        
        status_placeholder.success("✅ Review complete!")
        
        return {
            'chunks': chunks,
            'reviews': reviews,
            'repo_name': os.path.basename(clone_path),
            'files_count': len(parsed_files)
        }
        
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        logger.error(f"Pipeline error: {str(e)}", exc_info=True)
        return None
    finally:
        # Cleanup
        if clone_path:
            cleanup_repository(clone_path)

def display_review_results(results):
    """Display review results in a nice format"""
    if not results:
        return
        
    st.header("📊 Review Results")
    
    # Summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Repository", results['repo_name'])
    with col2:
        st.metric("Files Analyzed", results['files_count'])
    with col3:
        st.metric("Code Chunks", len(results['chunks']))
    
    st.divider()
    
    # Reviews
    for idx, review in enumerate(results['reviews'], 1):
        with st.expander(f"📝 Review {idx} - {review.get('file_path', 'Unknown')}"):
            
            # Display chunk info
            st.subheader("Code Chunk")
            st.code(review.get('chunk', ''), language='python')
            
            st.divider()
            
            # Display review content
            st.subheader("AI Review")
            st.markdown(review.get('review', 'No review available'))
            
            # Display metadata if available
            if 'confidence' in review:
                st.caption(f"Confidence: {review['confidence']}")

def main():
    """Main application"""
    initialize_session_state()
    
    # Header
    st.title("🔍 AI Code Review Agent")
    st.markdown("*Autonomous code analysis powered by AST parsing + GPT-4o-mini*")
    
    st.divider()
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # API Key input
        api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            value=os.getenv("OPENAI_API_KEY", ""),
            help="Your OpenAI API key for GPT-4o-mini"
        )
        
        # Chunk limit
        chunk_limit = st.slider(
            "Max Chunks to Review",
            min_value=1,
            max_value=10,
            value=3,
            help="Limit the number of chunks to review (for cost control)"
        )
        
        st.divider()
        
        # Instructions
        st.markdown("""
        ### How to use:
        1. Enter your OpenAI API key
        2. Paste a GitHub repository URL
        3. Click 'Start Review'
        4. Wait for analysis to complete
        
        ### Supported:
        - Public GitHub repositories
        - Python code files
        - Multiple files analysis
        """)
    
    # Main content area
    col1, col2 = st.columns([3, 1])
    
    with col1:
        repo_url = st.text_input(
            "GitHub Repository URL",
            placeholder="https://github.com/username/repo",
            help="Enter the URL of a public GitHub repository"
        )
    
    with col2:
        st.write("")  # Spacing
        st.write("")  # Spacing
        start_button = st.button("🚀 Start Review", type="primary", use_container_width=True)
    
    # Run review
    if start_button:
        if not repo_url:
            st.error("⚠️ Please enter a repository URL")
        elif not api_key:
            st.error("⚠️ Please enter your OpenAI API key")
        else:
            # Clear previous results
            st.session_state.review_complete = False
            st.session_state.review_results = None
            
            # Run pipeline
            results = run_review_pipeline(repo_url, api_key, chunk_limit)
            
            if results:
                st.session_state.review_complete = True
                st.session_state.review_results = results
                st.rerun()
    
    # Display results if available
    if st.session_state.review_complete and st.session_state.review_results:
        st.divider()
        display_review_results(st.session_state.review_results)
        
        # Reset button
        if st.button("🔄 Review Another Repository"):
            st.session_state.review_complete = False
            st.session_state.review_results = None
            st.rerun()

if __name__ == "__main__":
    main()