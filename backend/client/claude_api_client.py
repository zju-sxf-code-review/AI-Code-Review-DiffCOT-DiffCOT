"""Claude API client for direct Anthropic API calls."""

import os
import json
import time
from typing import Dict, Any, Tuple, Optional
from pathlib import Path

from anthropic import Anthropic

from configs.constants import (
    DEFAULT_CLAUDE_MODEL, DEFAULT_TIMEOUT_SECONDS, DEFAULT_MAX_RETRIES,
    RATE_LIMIT_BACKOFF_MAX, PROMPT_TOKEN_LIMIT,
)
from configs.review_rules import get_review_filtering_section, get_security_filtering_section
from utils.json_parser import parse_json_with_fallbacks
from utils.logger import get_logger

logger = get_logger(__name__)


class ClaudeAPIClient:
    """Client for calling Claude API directly for security analysis tasks."""
    
    def __init__(self, 
                 model: Optional[str] = None,
                 api_key: Optional[str] = None,
                 timeout_seconds: Optional[int] = None,
                 max_retries: Optional[int] = None):
        """Initialize Claude API client.
        
        Args:
            model: Claude model to use
            api_key: Anthropic API key (if None, reads from ANTHROPIC_API_KEY env var)
            timeout_seconds: Request timeout in seconds
            max_retries: Maximum retry attempts for API calls
        """
        self.model = model or DEFAULT_CLAUDE_MODEL
        self.timeout_seconds = timeout_seconds or DEFAULT_TIMEOUT_SECONDS
        self.max_retries = max_retries or DEFAULT_MAX_RETRIES
        
        # Get API key from environment or parameter
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "No Anthropic API key found. Please set ANTHROPIC_API_KEY environment variable "
                "or provide api_key parameter."
            )
        
        # Initialize Anthropic client
        self.client = Anthropic(api_key=self.api_key)
        logger.info("Claude API client initialized successfully")
    
    def validate_api_access(self) -> Tuple[bool, str]:
        """Validate that API access is working.
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Simple test call to verify API access
            self.client.messages.create(
                model="claude-opus-4-5-20251101",
                max_tokens=10,
                messages=[{"role": "user", "content": "Hello"}],
                timeout=10
            )
            logger.info("Claude API access validated successfully")
            return True, ""
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Claude API validation failed: {error_msg}")
            return False, f"API validation failed: {error_msg}"
    
    def call_with_retry(self, 
                       prompt: str,
                       system_prompt: Optional[str] = None,
                       max_tokens: int = PROMPT_TOKEN_LIMIT) -> Tuple[bool, str, str]:
        """Make Claude API call with retry logic.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens to generate
            
        Returns:
            Tuple of (success, response_text, error_message)
        """
        retries = 0
        last_error = None
        
        while retries <= self.max_retries:
            try:
                logger.info(f"Claude API call attempt {retries + 1}/{self.max_retries + 1}")
                
                # Prepare messages
                messages = [{"role": "user", "content": prompt}]
                
                # Build API call parameters
                api_params = {
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "messages": messages,
                    "timeout": self.timeout_seconds
                }
                
                if system_prompt:
                    api_params["system"] = system_prompt
                
                # Make API call
                start_time = time.time()
                response = self.client.messages.create(**api_params)
                duration = time.time() - start_time
                
                # Extract text from response
                response_text = ""
                for content_block in response.content:
                    if hasattr(content_block, 'text'):
                        response_text += content_block.text
                
                logger.info(f"Claude API call successful in {duration:.1f}s")
                return True, response_text, ""
                
            except Exception as e:
                error_msg = str(e)
                last_error = error_msg
                logger.error(f"Claude API call failed: {error_msg}")
                
                # Check if it's a rate limit error
                if "rate limit" in error_msg.lower() or "429" in error_msg:
                    logger.warning("Rate limit detected, increasing backoff")
                    backoff_time = min(RATE_LIMIT_BACKOFF_MAX, 5 * (retries + 1))  # Progressive backoff
                    time.sleep(backoff_time)
                elif "timeout" in error_msg.lower():
                    logger.warning("Timeout detected, retrying")
                    time.sleep(2)
                else:
                    # For other errors, shorter backoff
                    time.sleep(1)
                
                retries += 1
        
        # All retries exhausted
        return False, "", f"API call failed after {self.max_retries + 1} attempts: {last_error}"

    def review_code(self,
                   diff_content: str,
                   pr_context: Optional[Dict[str, Any]] = None,
                   sast_findings: Optional[str] = None) -> Tuple[bool, Dict[str, Any], str]:
        """Review code changes and provide analysis.

        Args:
            diff_content: Git diff content to review
            pr_context: Optional PR context for better analysis
            sast_findings: Optional SAST findings formatted for prompt

        Returns:
            Tuple of (success, review_result, error_message)
        """
        try:
            prompt = self._generate_review_prompt(diff_content, pr_context, sast_findings)
            system_prompt = self._generate_review_system_prompt(has_sast=bool(sast_findings))

            success, response_text, error_msg = self.call_with_retry(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=PROMPT_TOKEN_LIMIT
            )

            if not success:
                return False, {}, error_msg

            # Parse JSON response
            success, review_result = parse_json_with_fallbacks(response_text, "Claude API response")
            if success:
                logger.info("Successfully parsed Claude API response for code review")
                return True, review_result, ""
            else:
                # Return raw text if JSON parsing fails
                return True, {"raw_review": response_text}, ""

        except Exception as e:
            logger.exception(f"Error during code review: {str(e)}")
            return False, {}, f"Code review failed: {str(e)}"

    def _generate_review_system_prompt(self, has_sast: bool = False) -> str:
        """Generate system prompt for code review."""
        base_prompt = """You are an expert code reviewer with deep knowledge of software engineering best practices.
Your task is to review code changes (git diff) and provide constructive feedback.

**CRITICAL: You must ONLY review the changes shown in the Git Diff. Do NOT review or comment on code that wasn't modified in this PR.**
- Lines starting with + are additions (new code) - these should be reviewed
- Lines starting with - are deletions (removed code) - you may comment on if the removal is problematic
- Lines without +/- are context lines - do NOT report issues in these lines unless they are directly affected by the changes

The full file content provided is for CONTEXT ONLY - to help you understand the surrounding code.
Do NOT report issues in code that exists outside the diff changes.

Focus on:
1. Code quality and maintainability of the CHANGED code
2. Potential bugs and logic errors INTRODUCED by the changes
3. Security vulnerabilities INTRODUCED by the changes
4. Performance considerations of the NEW code
5. Best practices and design patterns
6. **Static defects**: Missing imports, undefined variables, type mismatches, API contract violations - ONLY in changed code
7. **Logic defects**: Intent vs implementation mismatch, incomplete implementation - ONLY in changed code
8. **Naming and typos** - ONLY in identifiers that were added or modified in this PR

IMPORTANT: For each issue you find, if you can provide a concrete code fix, include it in the "suggested_change" field.
The suggested_change should contain the EXACT code that should replace the problematic code.
This will be used to create GitHub suggested changes that can be applied directly.

Provide your review in a structured JSON format with clear, actionable feedback."""

        if has_sast:
            base_prompt += """

When SAST (Static Application Security Testing) findings are provided:
1. Validate each SAST finding - determine if it's a true positive or false positive
2. Include confirmed issues in your review with appropriate severity
3. Add context and explanation for each confirmed SAST issue
4. Filter out obvious false positives and explain why they're false positives"""

        return base_prompt

    def _generate_review_prompt(self,
                               diff_content: str,
                               pr_context: Optional[Dict[str, Any]] = None,
                               sast_findings: Optional[str] = None) -> str:
        """Generate prompt for code review.

        Args:
            diff_content: Git diff content
            pr_context: Optional PR context
            sast_findings: Optional SAST findings formatted string

        Returns:
            Formatted prompt string
        """
        pr_info = ""
        if pr_context and isinstance(pr_context, dict):
            pr_info = f"""
Pull Request Information:
- Repository: {pr_context.get('repo_name', 'unknown')}
- PR #{pr_context.get('pr_number', 'unknown')}
- Title: {pr_context.get('title', 'unknown')}
- Author: {pr_context.get('author', 'unknown')}
- Description: {(pr_context.get('description') or 'No description')[:500]}
- Base Branch: {pr_context.get('base_branch', 'main')}
- Head Branch: {pr_context.get('head_branch', 'unknown')}
"""

        # Build SAST section if findings provided
        sast_section = ""
        if sast_findings:
            sast_section = f"""
---
## Static Analysis (SAST) Findings

The following issues were detected by Semgrep static analysis. Please validate these findings and include confirmed issues in your review:

{sast_findings}

---
"""

        # Get filtering rules
        filtering_rules = get_review_filtering_section(include_static_defects=True, include_logic_defects=True)

        return f"""Please review the following code changes and provide detailed feedback.

{pr_info}
{sast_section}

## Review Guidelines

{filtering_rules}

---

Code Changes (Git Diff):
```diff
{diff_content[:50000]}
```

Provide your review in the following JSON format:
{{
  "summary": "Brief summary of the changes",
  "overall_assessment": "APPROVE | REQUEST_CHANGES | COMMENT",
  "score": 8,
  "issues": [
    {{
      "severity": "HIGH | MEDIUM | LOW",
      "type": "bug | security | performance | style | best_practice | typo | static_defect | logic_defect | encapsulation",
      "file": "path/to/filename.py",
      "line": 42,
      "end_line": 45,
      "description": "Description of the issue",
      "suggestion": "Explanation of how to fix this issue",
      "suggested_change": "The exact replacement code"
    }}
  ],
  "positive_feedback": [
    "Good aspects of the code"
  ],
  "suggestions": [
    "General improvement suggestions"
  ]
}}

IMPORTANT NOTES:
1. **CRITICAL: ONLY review code that was CHANGED in this PR (lines with + or - in the diff).**
   - Do NOT report issues in unchanged context lines (lines without + or -)
   - Do NOT report issues in code outside the diff, even if the full file content is provided
   - The full file content is for CONTEXT ONLY to help you understand the changes
2. The "file" field MUST be the full file path as shown in the diff (e.g., "src/main/java/com/example/File.java")
3. The "line" field is the starting line number in the NEW version of the file (lines marked with + in diff)
4. The "end_line" field is optional, use it for multi-line code suggestions
5. The "suggested_change" field should contain the EXACT replacement code (not a diff, just the new code)
6. Use \\n for newlines in suggested_change, and escape special characters properly for JSON
7. If SAST findings are provided, validate them and include confirmed issues
8. **Check for typos ONLY in NEWLY ADDED code** (lines with +):
   - Misspelled words (e.g., "groupUuuids" → "groupUuids", "recieve" → "receive")
   - Extra or missing characters (e.g., "paramter" → "parameter")
   Use type "typo" for naming/spelling issues.
9. **Check for static defects ONLY in CHANGED code**:
   - Missing imports for newly added code
   - Undefined variables in new code
   - Type mismatches in new code
   Use type "static_defect" for these issues.
10. **USE THE SYMBOL TABLE** (if provided) to validate imports and method calls in the CHANGED code only
11. **Check for logic defects ONLY in CHANGED code**:
   - Intent vs implementation mismatch in new code
   - Incomplete implementations
   Use type "logic_defect" for these issues.
12. **Check for encapsulation violations ONLY if INTRODUCED by this PR**

Respond with ONLY the JSON object, no additional text or markdown formatting."""

    def analyze_single_finding(self, 
                              finding: Dict[str, Any], 
                              pr_context: Optional[Dict[str, Any]] = None,
                              custom_filtering_instructions: Optional[str] = None) -> Tuple[bool, Dict[str, Any], str]:
        """Analyze a single security finding to filter false positives using Claude API.
        
        Args:
            finding: Single security finding to analyze
            pr_context: Optional PR context for better analysis
            
        Returns:
            Tuple of (success, analysis_result, error_message)
        """
        try:
            # Generate analysis prompt with file content
            prompt = self._generate_single_finding_prompt(finding, pr_context, custom_filtering_instructions)
            system_prompt = self._generate_system_prompt()
            
            # Call Claude API
            success, response_text, error_msg = self.call_with_retry(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=PROMPT_TOKEN_LIMIT 
            )
            
            if not success:
                return False, {}, error_msg
            
            # Parse JSON response using json_parser
            success, analysis_result = parse_json_with_fallbacks(response_text, "Claude API response")
            if success:
                logger.info("Successfully parsed Claude API response for single finding")
                return True, analysis_result, ""
            else:
                # Fallback: return error
                return False, {}, "Failed to parse JSON response"
                
        except Exception as e:
            logger.exception(f"Error during single finding security analysis: {str(e)}")
            return False, {}, f"Single finding security analysis failed: {str(e)}"

    
    def _generate_system_prompt(self) -> str:
        """Generate system prompt for security analysis."""
        return """You are a security expert reviewing findings from an automated code audit tool.
Your task is to filter out false positives and low-signal findings to reduce alert fatigue.
You must maintain high recall (don't miss real vulnerabilities) while improving precision.

Respond ONLY with valid JSON in the exact format specified in the user prompt.
Do not include explanatory text, markdown formatting, or code blocks."""

    def _generate_single_finding_prompt(self,
                                       finding: Dict[str, Any],
                                       pr_context: Optional[Dict[str, Any]] = None,
                                       custom_filtering_instructions: Optional[str] = None) -> str:
        """Generate prompt for analyzing a single security finding.

        Args:
            finding: Single security finding
            pr_context: Optional PR context
            custom_filtering_instructions: Optional custom filtering rules

        Returns:
            Formatted prompt string
        """
        pr_info = ""
        if pr_context and isinstance(pr_context, dict):
            pr_info = f"""
PR Context:
- Repository: {pr_context.get('repo_name', 'unknown')}
- PR #{pr_context.get('pr_number', 'unknown')}
- Title: {pr_context.get('title', 'unknown')}
- Description: {(pr_context.get('description') or 'No description')[:500]}...
"""

        # Get file content if available
        file_path = finding.get('file', '')
        file_content = ""
        if file_path:
            success, content, error = self._read_file(file_path)
            if success:
                file_content = f"""

File Content ({file_path}):
```
{content}
```"""
            else:
                file_content = f"""

File Content ({file_path}): Error reading file - {error}
"""

        finding_json = json.dumps(finding, indent=2)

        # Use custom filtering instructions if provided, otherwise use shared rules
        if custom_filtering_instructions:
            filtering_section = custom_filtering_instructions
        else:
            filtering_section = get_security_filtering_section()

        return f"""I need you to analyze a security finding from an automated code audit and determine if it's a false positive.

{pr_info}

{filtering_section}

Assign a confidence score from 1-10:
- 1-3: Low confidence, likely false positive or noise
- 4-6: Medium confidence, needs investigation
- 7-10: High confidence, likely true vulnerability

Finding to analyze:
```json
{finding_json}
```
{file_content}

Respond with EXACTLY this JSON structure (no markdown, no code blocks):
{{
  "original_severity": "HIGH",
  "confidence_score": 8,
  "keep_finding": true,
  "exclusion_reason": null,
  "justification": "Clear SQL injection vulnerability with specific exploit path"
}}"""

    
    def _read_file(self, file_path: str) -> Tuple[bool, str, str]:
        """Read a file and format it with line numbers.
        
        Args:
            file_path: Path to the file to read
            
        Returns:
            Tuple of (success, formatted_content, error_message)
        """
        try:
            # Check if REPO_PATH is set and use it as base path
            repo_path = os.environ.get('REPO_PATH')
            if repo_path:
                # Convert file_path to Path and check if it's absolute
                path = Path(file_path)
                if not path.is_absolute():
                    # Make it relative to REPO_PATH
                    path = Path(repo_path) / file_path
            else:
                path = Path(file_path)
            
            if not path.exists():
                return False, "", f"File not found: {path}"
            
            if not path.is_file():
                return False, "", f"Path is not a file: {path}"
            
            # Read file with error handling for encoding issues
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                # Try with latin-1 encoding as fallback
                with open(path, 'r', encoding='latin-1') as f:
                    content = f.read()
            
            return True, content, ""
            
        except Exception as e:
            error_msg = f"Error reading file {file_path}: {str(e)}"
            logger.error(error_msg)
            return False, "", error_msg


def get_claude_api_client(model: str = DEFAULT_CLAUDE_MODEL,
                         api_key: Optional[str] = None,
                         timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> ClaudeAPIClient:
    """Convenience function to get Claude API client.
    
    Args:
        model: Claude model identifier
        api_key: Optional API key (reads from environment if not provided)
        timeout_seconds: API call timeout
        
    Returns:
        Initialized ClaudeAPIClient instance
    """
    return ClaudeAPIClient(
        model=model,
        api_key=api_key,
        timeout_seconds=timeout_seconds
    )


