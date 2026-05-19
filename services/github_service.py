import os
import shutil
import tempfile
from git import Repo
import logging

logger = logging.getLogger(__name__)

class GitHubService:
    """Service for handling GitHub repository operations"""
    
    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
        
    def clone_repository(self, repo_url: str) -> str:
        """
        Clone a GitHub repository to a temporary directory
        
        Args:
            repo_url: GitHub repository URL
            
        Returns:
            Path to the cloned repository
        """
        try:
            # Extract repo name from URL
            repo_name = repo_url.rstrip('/').split('/')[-1].replace('.git', '')
            
            # Create unique clone path
            clone_path = os.path.join(self.temp_dir, f"code_review_{repo_name}")
            
            # Remove existing directory if it exists
            if os.path.exists(clone_path):
                shutil.rmtree(clone_path)
            
            # Clone repository
            logger.info(f"Cloning {repo_url} to {clone_path}")
            Repo.clone_from(repo_url, clone_path)
            
            return clone_path
            
        except Exception as e:
            logger.error(f"Error cloning repository: {str(e)}")
            raise Exception(f"Failed to clone repository: {str(e)}")
    
    def cleanup_repository(self, clone_path: str):
        """
        Clean up cloned repository
        
        Args:
            clone_path: Path to the cloned repository
        """
        try:
            if clone_path and os.path.exists(clone_path):
                shutil.rmtree(clone_path)
                logger.info(f"Cleaned up repository at {clone_path}")
        except Exception as e:
            logger.error(f"Error cleaning up repository: {str(e)}")