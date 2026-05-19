"""
AI Reviewer Agent: analyzes code chunks using OpenAI GPT-4o-mini
"""
import logging
from typing import List, Dict
from openai import OpenAI
from models.review_schema import CodeChunk

logger = logging.getLogger(__name__)


class ReviewerAgent:
    """AI agent for reviewing code chunks"""
    
    def __init__(self, api_key: str):
        """
        Initialize reviewer agent
        
        Args:
            api_key: OpenAI API key
        """
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"
    
    def review_chunks(self, chunks: List[CodeChunk]) -> List[Dict]:
        """
        Review code chunks using GPT-4o-mini
        
        Args:
            chunks: List of code chunks to review
            
        Returns:
            List of review results
        """
        reviews = []
        
        for idx, chunk in enumerate(chunks, 1):
            logger.info(f"Reviewing chunk {idx}/{len(chunks)}")
            
            try:
                review = self._review_single_chunk(chunk)
                reviews.append({
                    'file_path': chunk.file_path,
                    'chunk': chunk.chunk_content,
                    'review': review,
                    'chunk_type': chunk.chunk_type,
                    'context': chunk.context
                })
            except Exception as e:
                logger.error(f"Error reviewing chunk {idx}: {str(e)}")
                reviews.append({
                    'file_path': chunk.file_path,
                    'chunk': chunk.chunk_content,
                    'review': f"Error during review: {str(e)}",
                    'chunk_type': chunk.chunk_type,
                    'context': chunk.context
                })
        
        return reviews
    
    def _review_single_chunk(self, chunk: CodeChunk) -> str:
        """
        Review a single code chunk
        
        Args:
            chunk: Code chunk to review
            
        Returns:
            Review text
        """
        prompt = f"""You are an expert code reviewer. Analyze the following Python code and provide:

1. **Code Quality**: Rate the code quality (1-10)
2. **Issues Found**: List any bugs, security issues, or code smells
3. **Best Practices**: Identify violations of Python best practices
4. **Suggestions**: Provide specific improvement recommendations
5. **Positive Points**: Highlight what's done well

**File**: {chunk.file_path}
**Type**: {chunk.chunk_type}
**Context**: {chunk.context}

**Code**:
```python
{chunk.chunk_content}
```

Provide a concise, actionable review."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an expert Python code reviewer."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        
        return response.choices[0].message.content