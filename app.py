import streamlit as st
import os
from dotenv import load_dotenv
from services.github_service import GitHubService
from services.parser_service import ParserService
from services.chunk_service import ChunkService
from agents.reviewer import ReviewerAgent
from models.review_schema import ReviewResult, Category, Severity
import logging
from typing import List
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables (only for local development)
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

def get_api_key():
    """Get API key from Streamlit secrets (production) or environment variable (local)"""
    if hasattr(st, 'secrets') and 'OPENAI_API_KEY' in st.secrets:
        return st.secrets['OPENAI_API_KEY']
    return os.getenv('OPENAI_API_KEY', '')

def initialize_session_state():
    """Initialize session state variables"""
    if 'review_complete' not in st.session_state:
        st.session_state.review_complete = False
    if 'review_results' not in st.session_state:
        st.session_state.review_results = None
    if 'clone_path' not in st.session_state:
        st.session_state.clone_path = None
    if 'selected_category' not in st.session_state:
        st.session_state.selected_category = "All"
    if 'selected_severity' not in st.session_state:
        st.session_state.selected_severity = "All"

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
            'files_count': len(parsed_files),
            'repo_url': repo_url
        }
        
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        logger.error(f"Pipeline error: {str(e)}", exc_info=True)
        return None
    finally:
        if clone_path:
            cleanup_repository(clone_path)

def get_severity_badge(severity: Severity) -> str:
    """Get colored badge for severity"""
    badges = {
        Severity.LOW: "🟢 **LOW**",
        Severity.MEDIUM: "🟡 **MEDIUM**",
        Severity.HIGH: "🟠 **HIGH**",
        Severity.CRITICAL: "🔴 **CRITICAL**"
    }
    return badges.get(severity, "⚪ **UNKNOWN**")

def get_confidence_badge(confidence: int) -> str:
    """Get colored badge for confidence score.
    
    Thresholds match confidence.py:
        HIGH   >= 80  (green)
        MEDIUM >= 50  (amber)
        VERIFY  < 50  (red)
    """
    if confidence >= 80:
        return f"🟢 **{confidence}%** (High Confidence)"
    elif confidence >= 50:
        return f"🟡 **{confidence}%** (Medium Confidence)"
    else:
        return f"🔴 **{confidence}%** (Low — Verify This!)"

def generate_markdown_report(results: dict) -> str:
    """Generate downloadable Markdown report"""
    reviews: List[ReviewResult] = results['reviews']
    
    md = f"""# Code Review Report
    
**Repository:** {results['repo_name']}  
**URL:** {results['repo_url']}  
**Files Analyzed:** {results['files_count']}  
**Code Chunks Reviewed:** {len(reviews)}  
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## Summary

"""
    
    # Calculate statistics
    total_issues = sum(len(r.comments) for r in reviews)
    high_conf_issues = sum(len(r.high_confidence_comments) for r in reviews)
    low_conf_issues = sum(len(r.low_confidence_comments) for r in reviews)
    
    md += f"""
- **Total Issues Found:** {total_issues}
- **High Confidence Issues:** {high_conf_issues}
- **Low Confidence Issues (Need Verification):** {low_conf_issues}

---

"""
    
    # Detailed reviews
    for idx, review in enumerate(reviews, 1):
        md += f"""
## Review {idx}: {review.file_path}

**Type:** {review.chunk_type}  
**Lines:** {review.line_start}-{review.line_end}  
**Overall Quality:** {review.overall_quality}/10

**Summary:** {review.summary}

"""
        
        if review.high_confidence_comments:
            md += "\n### ✅ High Confidence Issues\n\n"
            for comment in review.high_confidence_comments:
                md += f"""
**Category:** {comment.category.value.replace('_', ' ').title()}  
**Severity:** {comment.severity.value.upper()}  
**Confidence:** {comment.confidence}%  
**Lines:** {comment.line_start}-{comment.line_end}

**Issue:** {comment.issue}

**Suggestion:** {comment.suggestion}

---

"""
        
        if review.low_confidence_comments:
            md += "\n### ⚠️ Low Confidence Issues (Needs Verification)\n\n"
            for comment in review.low_confidence_comments:
                md += f"""
**Category:** {comment.category.value.replace('_', ' ').title()}  
**Severity:** {comment.severity.value.upper()}  
**Confidence:** {comment.confidence}% ⚠️  
**Lines:** {comment.line_start}-{comment.line_end}

**Issue:** {comment.issue}

**Suggestion:** {comment.suggestion}

**⚠️ Please manually verify this issue**

---

"""
    
    return md

def render_comment(comment, is_low_confidence: bool = False):
    """Render a single review comment with confidence progress bar visual indicator."""
    with st.container():
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(
                f"{get_severity_badge(comment.severity)} &nbsp; "
                f"**{comment.category.value.replace('_', ' ').title()}** &nbsp; "
                f"Lines {comment.line_start}–{comment.line_end}",
                unsafe_allow_html=True,
            )
        with col2:
            st.markdown(get_confidence_badge(comment.confidence))

        # ── Visual confidence indicator (progress bar) ──────────────────────
        # Color driven by bucket: green ≥80, amber 50-79, red <50
        if comment.confidence >= 80:
            bar_color = "#22c55e"
            bucket_label = "High Confidence"
        elif comment.confidence >= 50:
            bar_color = "#f59e0b"
            bucket_label = "Medium Confidence"
        else:
            bar_color = "#ef4444"
            bucket_label = "⚠️ Verify This"

        st.markdown(
            f"""
            <div style="margin: 4px 0 8px 0;">
                <div style="display:flex; justify-content:space-between;
                            font-size:0.75rem; color:#9ca3af; margin-bottom:3px;">
                    <span>{bucket_label}</span>
                    <span>{comment.confidence}%</span>
                </div>
                <div style="background:#374151; border-radius:6px; height:8px; width:100%;">
                    <div style="background:{bar_color}; border-radius:6px;
                                height:8px; width:{comment.confidence}%;
                                transition: width 0.4s ease;"></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        # ────────────────────────────────────────────────────────────────────

        st.markdown(f"**Issue:** {comment.issue}")
        st.markdown(f"**Suggestion:** {comment.suggestion}")

        if is_low_confidence:
            st.error("🔍 **VERIFY THIS MANUALLY** — confidence below 50%")

        st.divider()


def display_review_results(results):
    """Display review results with filtering and download"""
    if not results:
        return
    
    reviews: List[ReviewResult] = results['reviews']
    
    st.header("📊 Review Results")
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Repository", results['repo_name'])
    with col2:
        st.metric("Files Analyzed", results['files_count'])
    with col3:
        total_issues = sum(len(r.comments) for r in reviews)
        st.metric("Total Issues", total_issues)
    with col4:
        avg_quality = sum(r.overall_quality for r in reviews) / len(reviews) if reviews else 0
        st.metric("Avg Quality", f"{avg_quality:.1f}/10")
    
    st.divider()
    
    # Filters and Download
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        categories = ["All"] + [c.value for c in Category]
        selected_category = st.selectbox(
            "Filter by Category",
            categories,
            key="category_filter"
        )
    
    with col2:
        severities = ["All"] + [s.value for s in Severity]
        selected_severity = st.selectbox(
            "Filter by Severity",
            severities,
            key="severity_filter"
        )
    
    with col3:
        st.write("")
        st.write("")
        markdown_report = generate_markdown_report(results)
        st.download_button(
            label="📥 Download Report",
            data=markdown_report,
            file_name=f"code_review_{results['repo_name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
            mime="text/markdown"
        )
    
    st.divider()
    
    # Display reviews with filters
    for idx, review in enumerate(reviews, 1):
        # Filter comments
        filtered_comments = [
            c for c in review.comments
            if (selected_category == "All" or c.category.value == selected_category)
            and (selected_severity == "All" or c.severity.value == selected_severity)
        ]
        
        if not filtered_comments and (selected_category != "All" or selected_severity != "All"):
            continue  # Skip this review if no comments match filters
        
        with st.expander(f"📝 Review {idx} - {review.file_path}", expanded=False):
            
            # Overall quality score
            col1, col2 = st.columns([1, 3])
            with col1:
                quality_color = "🟢" if review.overall_quality >= 7 else "🟡" if review.overall_quality >= 5 else "🔴"
                st.metric("Quality Score", f"{quality_color} {review.overall_quality}/10")
            with col2:
                st.info(f"**Summary:** {review.summary}")
            
            st.markdown(f"**Type:** {review.chunk_type} | **Lines:** {review.line_start}-{review.line_end}")
            
            st.divider()
            
            # Separate high/medium confidence from low-confidence (needs verification)
            # Thresholds aligned with confidence.py: HIGH>=80, MEDIUM>=50, VERIFY<50
            high_conf = [c for c in filtered_comments if c.confidence >= 50]
            low_conf = [c for c in filtered_comments if c.confidence < 50]

            # High / medium confidence comments
            if high_conf:
                st.subheader("✅ Reviewed Issues")
                for comment in high_conf:
                    render_comment(comment, is_low_confidence=False)
            
            # Low confidence comments (need verification)
            if low_conf:
                st.subheader("⚠️ Needs Verification (Low Confidence)")
                st.warning("⚠️ These comments have confidence < 50% and should be manually verified")
                for comment in low_conf:
                    render_comment(comment, is_low_confidence=True)
            
            if not filtered_comments:
                st.success("✨ No issues found in this chunk!")

def main():
    """Main application"""
    initialize_session_state()
    
    # Header
    st.title("🔍 AI Code Review Agent")
    st.markdown("*Autonomous code analysis powered by AST parsing + GPT-4o-mini with confidence scoring*")
    
    st.divider()
    
    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        default_key = get_api_key()
        
        api_key_input = st.text_input(
            "OpenAI API Key",
            type="password",
            value="",
            placeholder="sk-..." if not default_key else "Using configured key",
            help="Your OpenAI API key for GPT-4o-mini"
        )
        
        api_key = api_key_input if api_key_input else default_key
        
        if default_key:
            st.success("✅ API key configured")
        elif not api_key:
            st.warning("⚠️ Please enter your API key")
        
        chunk_limit = st.slider(
            "Max Chunks to Review",
            min_value=1,
            max_value=10,
            value=3,
            help="Limit the number of chunks to review (for cost control)"
        )
        
        st.divider()
        
        st.markdown("""
        ### How to use:
        1. Enter your OpenAI API key
        2. Paste a GitHub repository URL
        3. Click 'Start Review'
        4. Filter results by category/severity
        5. Download the full report
        
        ### Features:
        - ✅ Confidence scoring (0-100%)
        - ✅ Severity ratings
        - ✅ Category filtering
        - ✅ Downloadable reports
        - ✅ Low-confidence verification
        """)
    
    # Main content area — wrap in a form so Enter key submits
    with st.form(key="review_form"):
        col1, col2 = st.columns([3, 1])

        with col1:
            repo_url = st.text_input(
                "GitHub Repository URL",
                placeholder="https://github.com/username/repo",
                help="Enter the URL of a public GitHub repository"
            )

        with col2:
            st.write("")
            st.write("")
            start_button = st.form_submit_button(
                "🚀 Start Review", type="primary", use_container_width=True
            )

    # Run review
    if start_button:
        if not repo_url:
            st.error("⚠️ Please enter a repository URL")
        elif not api_key:
            st.error("⚠️ Please enter your OpenAI API key")
        else:
            # Validate URL format before running the pipeline
            try:
                from services.github_service import _GITHUB_URL_RE
                if not _GITHUB_URL_RE.match(repo_url.strip()):
                    st.error(
                        "⚠️ Invalid GitHub URL. "
                        "Expected format: https://github.com/owner/repo"
                    )
                    st.stop()
            except Exception:
                pass  # Let the pipeline surface any URL error naturally
            st.session_state.review_complete = False
            st.session_state.review_results = None
            
            results = run_review_pipeline(repo_url, api_key, chunk_limit)
            
            if results:
                st.session_state.review_complete = True
                st.session_state.review_results = results
                st.rerun()
    
    # Display results if available
    if st.session_state.review_complete and st.session_state.review_results:
        st.divider()
        display_review_results(st.session_state.review_results)
        
        if st.button("🔄 Review Another Repository"):
            st.session_state.review_complete = False
            st.session_state.review_results = None
            st.rerun()

if __name__ == "__main__":
    main()