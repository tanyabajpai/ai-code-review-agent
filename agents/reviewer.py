"""
AI Reviewer Agent: analyzes code chunks using OpenAI GPT-4o-mini.
Loads prompt template from prompts/review_prompt.txt.
"""
import logging
import json
import os
from typing import List
from openai import OpenAI
from models.review_schema import CodeChunk, ReviewResult, ReviewComment, Category, Severity

logger = logging.getLogger(__name__)

# Path to the prompt template, relative to project root
_PROMPT_TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),  # project root
    "prompts",
    "review_prompt.txt",
)


def _load_prompt_template() -> str:
    """Load the review prompt template from disk."""
    try:
        with open(_PROMPT_TEMPLATE_PATH, "r", encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        logger.warning(
            f"review_prompt.txt not found at {_PROMPT_TEMPLATE_PATH}. "
            "Falling back to inline prompt."
        )
        return None


class ReviewerAgent:
    """AI agent for reviewing code chunks with confidence scoring."""

    def __init__(self, api_key: str):
        """
        Initialize the reviewer agent.

        Args:
            api_key: OpenAI API key.
        """
        try:
            # Support both OpenAI keys (sk-proj-...) and OpenRouter keys (sk-or-v1-...).
            # OpenRouter is API-compatible with OpenAI but uses a different base URL.
            if api_key.startswith("sk-or-"):
                self.client = OpenAI(
                    api_key=api_key,
                    base_url="https://openrouter.ai/api/v1",
                )
                self.model = "openai/gpt-4o-mini"  # OpenRouter model name
                logger.info("Using OpenRouter API endpoint")
            else:
                self.client = OpenAI(api_key=api_key)
                self.model = "gpt-4o-mini"
                logger.info("Using OpenAI API endpoint")
            self._prompt_template = _load_prompt_template()
            logger.info("ReviewerAgent initialised successfully")
        except Exception as e:
            logger.error(f"Failed to initialise OpenAI client: {e}")
            raise

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def review_chunks(self, chunks: List[CodeChunk]) -> List[ReviewResult]:
        """
        Review a list of code chunks.

        Args:
            chunks: Code chunks produced by ChunkService.

        Returns:
            List of ReviewResult objects, one per chunk.
        """
        reviews: List[ReviewResult] = []

        for idx, chunk in enumerate(chunks, 1):
            logger.info(f"Reviewing chunk {idx}/{len(chunks)}: {chunk.file_path}")
            try:
                review = self._review_single_chunk(chunk)
                reviews.append(review)
            except Exception as e:
                logger.error(f"Error reviewing chunk {idx}: {e}", exc_info=True)
                reviews.append(self._error_result(chunk, str(e)))

        return reviews

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_prompt(self, chunk: CodeChunk) -> str:
        """
        Build the review prompt.

        Uses review_prompt.txt if available; falls back to an inline template
        that already matches the ReviewResult / ReviewComment schema.
        """
        # Extract line count for context
        lines = chunk.chunk_content.split("\n")
        line_start = 1
        line_end = len(lines)

        # --- Use the file-based template when available ---
        if self._prompt_template:
            # review_prompt.txt placeholders: {file_path} {function_name}
            # {line_start} {line_end} {code}
            # Derive function_name from chunk context field
            function_name = "unknown"
            if chunk.context:
                # context looks like "Function: foo, Lines: 1-20"
                parts = chunk.context.split(",")[0]
                if ":" in parts:
                    function_name = parts.split(":", 1)[1].strip()

            return self._prompt_template.format(
                file_path=chunk.file_path,
                function_name=function_name,
                line_start=line_start,
                line_end=line_end,
                code=chunk.chunk_content,
            )

        # --- Inline fallback (schema-aligned with ReviewResult) ---
        return f"""You are an expert code reviewer. Analyze the following Python code and return a structured JSON review.

IMPORTANT: Respond with ONLY valid JSON. No markdown, no code blocks, no explanations.

File: {chunk.file_path}
Type: {chunk.chunk_type}
Context: {chunk.context or 'N/A'}

Code:
```python
{chunk.chunk_content}
```

Return this exact JSON structure (keys must match exactly):
{{
  "file_path": "{chunk.file_path}",
  "chunk_type": "{chunk.chunk_type}",
  "line_start": {line_start},
  "line_end": {line_end},
  "comments": [
    {{
      "category": "<one of: bug|security|performance|style|documentation|best_practice|maintainability>",
      "severity": "<one of: low|medium|high|critical>",
      "line_start": 1,
      "line_end": 1,
      "issue": "clear description of the problem",
      "suggestion": "specific fix recommendation",
      "confidence": 85
    }}
  ],
  "summary": "overall assessment of this code",
  "overall_quality": 7
}}

Rules:
- confidence: 85-100 = certain issue; 60-84 = likely; 40-59 = possible; <40 = speculative
- Find real issues; do NOT invent problems. Empty comments array is acceptable only if code is genuinely clean.
- overall_quality: integer 1-10
- Return ONLY the JSON object. Start with {{"""

    def _review_single_chunk(self, chunk: CodeChunk) -> ReviewResult:
        """Call the LLM and parse the structured response into a ReviewResult."""
        prompt = self._build_prompt(chunk)
        lines = chunk.chunk_content.split("\n")
        line_start, line_end = 1, len(lines)

        raw_content = ""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert Python code reviewer. "
                            "You MUST respond with valid JSON only. "
                            "No markdown, no code blocks, no extra text."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )

            raw_content = response.choices[0].message.content
            logger.debug(f"Raw LLM response (first 300 chars): {raw_content[:300]}")

            review_data = json.loads(raw_content)

            # --- Normalise: review_prompt.txt returns a list; inline returns an object ---
            if isinstance(review_data, list):
                # review_prompt.txt format → array of comment objects
                review_data = self._normalise_list_response(
                    review_data, chunk, line_start, line_end
                )

            # Coerce comment field names from review_prompt.txt schema if needed
            review_data = self._coerce_comment_fields(review_data)

            review = ReviewResult(**review_data)
            logger.info(
                f"Reviewed {chunk.file_path}: {len(review.comments)} comment(s), "
                f"quality={review.overall_quality}/10"
            )
            return review

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e} | raw: {raw_content[:500]}")
            return self._error_result(chunk, f"JSON parse error: {e}")

        except Exception as e:
            logger.error(f"Review error: {e}", exc_info=True)
            return self._error_result(chunk, str(e))

    # ------------------------------------------------------------------
    # Schema normalisation helpers
    # ------------------------------------------------------------------

    def _normalise_list_response(
        self,
        comment_list: list,
        chunk: CodeChunk,
        line_start: int,
        line_end: int,
    ) -> dict:
        """
        Convert the review_prompt.txt list-of-comments format into the
        ReviewResult dict format expected by the Pydantic model.
        """
        comments = []
        quality_scores = []

        for item in comment_list:
            comment = self._coerce_single_comment(item)
            if comment:
                comments.append(comment)
                # Estimate quality contribution (inverse of severity)
                sev = comment.get("severity", "medium")
                quality_scores.append(
                    {"critical": 2, "high": 4, "medium": 6, "low": 8, "info": 9}.get(sev, 6)
                )

        overall_quality = (
            round(sum(quality_scores) / len(quality_scores))
            if quality_scores
            else 8  # no issues → good quality
        )
        overall_quality = max(1, min(10, overall_quality))

        return {
            "file_path": chunk.file_path,
            "chunk_type": chunk.chunk_type,
            "line_start": line_start,
            "line_end": line_end,
            "comments": comments,
            "summary": f"Reviewed {chunk.chunk_type} in {chunk.file_path}. "
                       f"{len(comments)} issue(s) found.",
            "overall_quality": overall_quality,
        }

    def _coerce_comment_fields(self, review_data: dict) -> dict:
        """
        Translate review_prompt.txt field names → ReviewComment field names.
        review_prompt.txt uses: issue_type, comment, suggestion
        ReviewComment uses:     category,   issue,   suggestion  (same last one)
        """
        coerced_comments = []
        for c in review_data.get("comments", []):
            coerced_comments.append(self._coerce_single_comment(c))
        review_data["comments"] = [c for c in coerced_comments if c]
        return review_data

    @staticmethod
    def _coerce_single_comment(item: dict) -> dict:
        """Map field aliases from review_prompt.txt schema to ReviewComment schema."""
        if not isinstance(item, dict):
            return None

        coerced = dict(item)

        # issue_type → category
        if "issue_type" in coerced and "category" not in coerced:
            raw_type = coerced.pop("issue_type", "best_practice")
            # Map human-readable labels to Category enum values
            mapping = {
                "Bug Risk": "bug",
                "Security": "security",
                "Performance": "performance",
                "Readability": "style",
                "Best Practices": "best_practice",
                "Dead Code": "maintainability",
                "Maintainability": "maintainability",
                "Documentation": "documentation",
                "Style": "style",
            }
            coerced["category"] = mapping.get(raw_type, "best_practice")

        # comment → issue
        if "comment" in coerced and "issue" not in coerced:
            coerced["issue"] = coerced.pop("comment")

        # Ensure severity is lowercase (schema uses lowercase enum values)
        if "severity" in coerced:
            coerced["severity"] = coerced["severity"].lower()

        # Ensure required line numbers exist
        coerced.setdefault("line_start", 1)
        coerced.setdefault("line_end", 1)
        coerced.setdefault("confidence", 70)
        coerced.setdefault("suggestion", "See issue description for guidance.")

        return coerced

    @staticmethod
    def _error_result(chunk: CodeChunk, error_msg: str) -> ReviewResult:
        """Return a safe fallback ReviewResult when something goes wrong."""
        return ReviewResult(
            file_path=chunk.file_path,
            chunk_type=chunk.chunk_type,
            line_start=0,
            line_end=0,
            comments=[],
            summary=f"Review could not complete: {error_msg}",
            overall_quality=5,
        )