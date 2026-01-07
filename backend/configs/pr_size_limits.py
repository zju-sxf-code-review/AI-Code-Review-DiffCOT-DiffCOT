"""Configuration for PR size limits and optimization.

Controls how large PRs are handled to prevent token overflow and timeout issues.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class PRSizeLimits:
    """Limits for PR processing to prevent resource exhaustion."""

    # File count limits
    max_files_for_full_analysis: int = 150  # Beyond this, use summary mode
    max_files_for_symbol_extraction: int = 200 # Beyond this, skip symbol extraction
    max_files_for_file_content: int = 200  # Beyond this, use diff-only mode (skip full file fetch)
    max_files_absolute: int = 250  # Beyond this, reject or heavily truncate

    # Content size limits (in characters)
    max_diff_size: int = 50000  # Total diff content
    max_file_content_size: int = 10000  # Per-file content limit
    max_total_content_size: int = 80000  # Total of all file contents
    max_context_prompt_size: int = 100000  # Context section in prompt
    max_symbol_table_size: int = 15000  # Symbol table section

    # Line count limits
    max_lines_changed: int = 2000  # Total lines added + deleted
    max_lines_per_file: int = 500  # Per-file line limit for full content

    # Related files limits
    max_related_files: int = 5
    max_related_file_size: int = 5000

    # Diff-imported files limits (higher priority - new imports in this PR)
    max_diff_imported_files: int = 10
    max_diff_imported_file_size: int = 10000  # Larger size for better context

    # Timeouts (in seconds)
    semgrep_timeout: int = 120
    symbol_extraction_timeout: int = 60
    llm_timeout: int = 180


# Default limits instance
DEFAULT_LIMITS = PRSizeLimits()


@dataclass
class PRSizeMetrics:
    """Metrics about PR size for decision making."""
    file_count: int = 0
    total_additions: int = 0
    total_deletions: int = 0
    total_changes: int = 0
    diff_size_chars: int = 0
    largest_file_lines: int = 0
    estimated_tokens: int = 0

    @property
    def is_large(self) -> bool:
        """Check if PR is considered large."""
        return (
            self.file_count > DEFAULT_LIMITS.max_files_for_full_analysis or
            self.total_changes > DEFAULT_LIMITS.max_lines_changed or
            self.diff_size_chars > DEFAULT_LIMITS.max_diff_size
        )

    @property
    def is_very_large(self) -> bool:
        """Check if PR is very large (needs heavy truncation)."""
        return (
            self.file_count > DEFAULT_LIMITS.max_files_absolute or
            self.total_changes > DEFAULT_LIMITS.max_lines_changed * 2 or
            self.diff_size_chars > DEFAULT_LIMITS.max_diff_size * 2
        )

    @property
    def needs_diff_only_mode(self) -> bool:
        """Check if PR has too many files for full content fetch.

        When True, only use diff for analysis - skip fetching full file contents.
        This significantly reduces API calls and processing time for large PRs.
        """
        return self.file_count > DEFAULT_LIMITS.max_files_for_file_content

    def get_recommended_mode(self) -> str:
        """Get recommended processing mode based on PR size.

        Returns:
            - "diff_only": Too many files, use only diff (no full file content)
            - "summary": Very large PR, analyze only most important files
            - "truncated": Large PR, analyze all but truncate content
            - "full": Normal PR, full analysis
        """
        if self.needs_diff_only_mode:
            return "diff_only"  # Too many files, use diff only
        elif self.is_very_large:
            return "summary"  # Only analyze most important files
        elif self.is_large:
            return "truncated"  # Analyze all but truncate content
        else:
            return "full"  # Full analysis


def calculate_pr_metrics(
    files: list,
    diff_content: str
) -> PRSizeMetrics:
    """Calculate PR size metrics from file list and diff.

    Args:
        files: List of file dicts from GitHub API
        diff_content: Full diff content string

    Returns:
        PRSizeMetrics with calculated values
    """
    metrics = PRSizeMetrics()
    metrics.file_count = len(files)
    metrics.diff_size_chars = len(diff_content)

    for f in files:
        additions = f.get('additions', 0)
        deletions = f.get('deletions', 0)
        metrics.total_additions += additions
        metrics.total_deletions += deletions
        metrics.largest_file_lines = max(
            metrics.largest_file_lines,
            additions + deletions
        )

    metrics.total_changes = metrics.total_additions + metrics.total_deletions

    # Rough token estimate (1 token ≈ 4 chars for code)
    metrics.estimated_tokens = metrics.diff_size_chars // 4

    return metrics


def truncate_content(content: str, max_size: int, suffix: str = "\n... [truncated]") -> str:
    """Truncate content to max size with suffix indicator.

    Args:
        content: Content to truncate
        max_size: Maximum size in characters
        suffix: Suffix to add if truncated

    Returns:
        Truncated content
    """
    if len(content) <= max_size:
        return content

    # Find a good break point (newline) near the limit
    truncate_at = max_size - len(suffix)
    last_newline = content.rfind('\n', 0, truncate_at)

    if last_newline > truncate_at * 0.8:  # If we found a newline in the last 20%
        truncate_at = last_newline

    return content[:truncate_at] + suffix


def prioritize_files(files: list, max_files: int) -> list:
    """Prioritize files for analysis when there are too many.

    Prioritization order:
    1. Source code files over config/docs
    2. Files with more changes
    3. Smaller files (more likely to be reviewable)

    Args:
        files: List of file dicts
        max_files: Maximum number of files to return

    Returns:
        Prioritized list of files
    """
    if len(files) <= max_files:
        return files

    # File type priorities (higher = more important)
    type_priority = {
        '.py': 10, '.go': 10, '.java': 10, '.ts': 10, '.tsx': 10,
        '.js': 9, '.jsx': 9, '.rs': 10, '.rb': 9, '.php': 9,
        '.c': 8, '.cpp': 8, '.h': 8, '.hpp': 8, '.cs': 9,
        '.sql': 7, '.graphql': 7,
        '.yaml': 5, '.yml': 5, '.json': 4, '.toml': 4,
        '.md': 2, '.txt': 1, '.rst': 2,
        '.css': 3, '.scss': 3, '.html': 3,
    }

    def get_priority(f):
        filename = f.get('filename', '')
        changes = f.get('additions', 0) + f.get('deletions', 0)

        # Get extension priority
        ext_priority = 0
        for ext, priority in type_priority.items():
            if filename.endswith(ext):
                ext_priority = priority
                break

        # Combine: type priority * 1000 + changes (capped at 500)
        return ext_priority * 1000 + min(changes, 500)

    sorted_files = sorted(files, key=get_priority, reverse=True)
    return sorted_files[:max_files]


def smart_diff_truncate(diff_content: str, max_size: int, files: list) -> str:
    """Intelligently truncate diff content, keeping important files.

    Args:
        diff_content: Full diff content
        max_size: Maximum size
        files: List of file info for prioritization

    Returns:
        Truncated diff
    """
    if len(diff_content) <= max_size:
        return diff_content

    # Get prioritized file names
    priority_files = prioritize_files(files, 20)
    priority_names = {f.get('filename', '') for f in priority_files}

    # Split diff by file
    file_diffs = []
    current_file = None
    current_content = []

    for line in diff_content.split('\n'):
        if line.startswith('diff --git'):
            if current_file:
                file_diffs.append((current_file, '\n'.join(current_content)))
            # Extract filename from diff header
            parts = line.split(' b/')
            current_file = parts[-1] if len(parts) > 1 else line
            current_content = [line]
        else:
            current_content.append(line)

    if current_file:
        file_diffs.append((current_file, '\n'.join(current_content)))

    # Sort by priority
    def file_priority(item):
        filename, content = item
        if filename in priority_names:
            return (1, -len(content))  # Priority files first, shorter first
        return (0, -len(content))

    file_diffs.sort(key=file_priority, reverse=True)

    # Build truncated diff
    result = []
    current_size = 0
    included_count = 0

    for filename, content in file_diffs:
        if current_size + len(content) + 100 <= max_size:
            result.append(content)
            current_size += len(content) + 1
            included_count += 1
        elif current_size < max_size * 0.9:
            # Partially include this file
            remaining = max_size - current_size - 100
            truncated = truncate_content(content, remaining)
            result.append(truncated)
            current_size += len(truncated) + 1
            included_count += 1
            break

    if included_count < len(file_diffs):
        result.append(f"\n... [{len(file_diffs) - included_count} more files not shown]")

    return '\n'.join(result)
