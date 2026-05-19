"""
Chunk service: converts parsed files into reviewable code chunks
"""
import logging
from typing import List
from models.review_schema import ParsedFile, CodeChunk

logger = logging.getLogger(__name__)


class ChunkService:
    """Service for creating code chunks from parsed files"""
    
    def __init__(self, max_chunk_size: int = 1000):
        """
        Initialize chunk service
        
        Args:
            max_chunk_size: Maximum size of each chunk in characters
        """
        self.max_chunk_size = max_chunk_size
    
    def create_chunks(self, parsed_files: List[ParsedFile], limit: int = None) -> List[CodeChunk]:
        """
        Create code chunks from parsed files
        
        Args:
            parsed_files: List of parsed Python files
            limit: Maximum number of chunks to create (None for no limit)
            
        Returns:
            List of code chunks ready for review
        """
        chunks = []
        
        for parsed_file in parsed_files:
            # Create chunks from functions and classes
            for func in parsed_file.functions:
                chunk = CodeChunk(
                    file_path=parsed_file.relative_path,
                    chunk_content=func.source_code,
                    chunk_type='class' if func.is_class else 'function',
                    context=f"Function: {func.name}, Lines: {func.line_start}-{func.line_end}"
                )
                chunks.append(chunk)
                
                # Stop if we've reached the limit
                if limit and len(chunks) >= limit:
                    logger.info(f"Reached chunk limit of {limit}")
                    return chunks
        
        logger.info(f"Created {len(chunks)} code chunks")
        return chunks