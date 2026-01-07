"""Pydantic models for API requests and responses."""

from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


# ============ Enums ============

class PRState(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"
    ALL = "all"


class ReviewAssessment(str, Enum):
    APPROVE = "APPROVE"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    COMMENT = "COMMENT"


class IssueSeverity(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class IssueType(str, Enum):
    BUG = "bug"
    SECURITY = "security"
    PERFORMANCE = "performance"
    STYLE = "style"
    BEST_PRACTICE = "best_practice"
    TYPO = "typo"  # Naming typos and spelling errors
    STATIC_DEFECT = "static_defect"  # Missing imports, undefined variables, type mismatches
    LOGIC_DEFECT = "logic_defect"  # Intent vs implementation mismatch, incomplete implementation
    ENCAPSULATION = "encapsulation"  # Accessing internal fields, breaking abstraction layers


# ============ GitHub Models ============

class GitHubRepoRequest(BaseModel):
    """Request to add a GitHub repository."""
    url: str = Field(..., description="GitHub repository URL")


class GitHubRepo(BaseModel):
    """GitHub repository information."""
    id: int
    name: str
    full_name: str
    owner: str
    description: Optional[str] = None
    url: str
    default_branch: str
    private: bool = False
    language: Optional[str] = None
    stargazers_count: int = 0
    forks_count: int = 0


class PullRequest(BaseModel):
    """Pull request information."""
    id: int
    number: int
    title: str
    state: str
    author: str
    created_at: str
    updated_at: str
    html_url: str
    head_branch: str
    base_branch: str
    draft: bool = False
    additions: Optional[int] = None
    deletions: Optional[int] = None
    changed_files: Optional[int] = None


class PullRequestDetail(PullRequest):
    """Detailed pull request information."""
    body: Optional[str] = None
    merged: bool = False
    merged_at: Optional[str] = None
    head_sha: str = ""
    base_sha: str = ""
    commits: int = 0
    mergeable: Optional[bool] = None


class PRFile(BaseModel):
    """File changed in a pull request."""
    filename: str
    status: str  # added, removed, modified, renamed
    additions: int
    deletions: int
    changes: int
    patch: str = ""
    previous_filename: Optional[str] = None


class PRReviewData(BaseModel):
    """Complete PR data for code review."""
    pr: PullRequestDetail
    files: List[PRFile]
    diff: str
    context: Dict[str, Any]


# ============ Code Review Models ============

class ReviewIssue(BaseModel):
    """Issue found during code review."""
    severity: str  # HIGH, MEDIUM, LOW - using str to handle LLM variations
    type: str  # bug, security, performance, style, best_practice - using str for flexibility
    file: str
    line: Optional[Union[int, str]] = None
    end_line: Optional[Union[int, str]] = None  # For multi-line suggestions
    description: str
    suggestion: Optional[str] = None
    suggested_change: Optional[str] = None  # The actual code to replace the original


class CodeReviewResult(BaseModel):
    """Result of AI code review."""
    summary: str
    overall_assessment: str  # APPROVE, REQUEST_CHANGES, COMMENT - using str for flexibility
    score: int = Field(default=5, ge=1, le=10)
    issues: List[ReviewIssue] = []
    positive_feedback: List[str] = []
    suggestions: List[str] = []
    raw_review: Optional[str] = None


class StartReviewRequest(BaseModel):
    """Request to start a code review."""
    repo_owner: str
    repo_name: str
    pr_number: int
    provider: str = "glm"  # 'glm' or 'anthropic'
    model: Optional[str] = None
    enable_sast: bool = True  # Enable SAST analysis before AI review
    enable_intent_analysis: bool = True  # Enable intent analysis with LLM
    enable_context_extraction: bool = True  # Enable full file content and repo structure extraction
    # Retry settings: retry if no issues found, up to max_retries times
    # If still no issues after all retries, accept that the code is clean
    retry_until_issues_found: bool = True  # Enable retry logic
    max_retries: int = 5  # Maximum retry attempts (if no issues found after 5 tries, code is clean)


# ============ SAST Models ============

class SastFinding(BaseModel):
    """A single SAST finding from static analysis."""
    rule_id: str
    severity: str  # HIGH, MEDIUM, LOW
    message: str
    file: str
    line: int
    end_line: Optional[int] = None
    column: Optional[int] = None
    end_column: Optional[int] = None
    category: str = "security"  # security, correctness, performance, style
    cwe: Optional[str] = None
    owasp: Optional[str] = None
    fix: Optional[str] = None
    code_snippet: Optional[str] = None


class SastResult(BaseModel):
    """Result of SAST analysis."""
    success: bool
    findings: List[SastFinding] = []
    error: Optional[str] = None
    tool: str = "semgrep"
    duration_ms: Optional[int] = None
    languages_detected: List[str] = []


# ============ Intent Analysis Models ============

class IntentAnalysisResult(BaseModel):
    """Result of intent analysis by LLM."""
    success: bool
    purpose: str = ""  # What the PR is trying to achieve
    implementation_approach: str = ""  # How it's being implemented
    key_changes: List[str] = []  # Main changes being made
    potential_issues: List[str] = []  # Issues identified from intent perspective
    missing_considerations: List[str] = []  # Things that might be missing
    architectural_impact: str = ""  # Impact on system architecture
    confidence: float = 0.0  # Confidence score 0-1
    error: Optional[str] = None
    duration_ms: Optional[int] = None


class ContextExtractionResult(BaseModel):
    """Result of context extraction."""
    success: bool
    changed_files_count: int = 0
    related_files_count: int = 0
    repo_structure_depth: int = 0
    languages_detected: List[str] = []
    error: Optional[str] = None


class ReviewResponse(BaseModel):
    """Response from code review endpoint."""
    success: bool
    review: Optional[CodeReviewResult] = None
    error: Optional[str] = None
    pr_info: Optional[PullRequestDetail] = None
    duration_ms: Optional[int] = None
    sast_result: Optional[SastResult] = None  # SAST analysis result
    intent_analysis: Optional[IntentAnalysisResult] = None  # Intent analysis result
    context_extraction: Optional[ContextExtractionResult] = None  # Context extraction info


# ============ GitHub Comment Models ============

class InlineComment(BaseModel):
    """Inline comment for GitHub PR review."""
    path: str
    line: int
    side: str = "RIGHT"  # LEFT or RIGHT
    body: str
    start_line: Optional[int] = None  # For multi-line comments
    start_side: Optional[str] = None
    suggested_change: Optional[str] = None  # Code suggestion to include


class PostCommentRequest(BaseModel):
    """Request to post comments to GitHub PR."""
    repo_owner: str
    repo_name: str
    pr_number: int
    summary: str  # Main review summary comment
    overall_assessment: str  # APPROVE, REQUEST_CHANGES, COMMENT
    score: int
    issues: List[ReviewIssue] = []
    positive_feedback: List[str] = []
    suggestions: List[str] = []


class PostCommentResponse(BaseModel):
    """Response from posting GitHub comments."""
    success: bool
    error: Optional[str] = None
    review_id: Optional[int] = None
    comment_count: int = 0
    url: Optional[str] = None


# ============ Settings Models ============

class ProviderConfig(BaseModel):
    """LLM provider configuration."""
    provider: str
    displayName: str = ""
    isEnabled: bool = False
    apiKey: str = ""
    baseURL: str = ""
    selectedChatModel: Optional[str] = None


class SettingsData(BaseModel):
    """Application settings."""
    providers: List[ProviderConfig] = []
    github_token: Optional[str] = None


# ============ Health Models ============

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    timestamp: str
