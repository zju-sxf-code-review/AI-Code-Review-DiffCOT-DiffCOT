"""Semgrep SAST client for static code analysis."""

import json
import subprocess
import tempfile
import os
import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, asdict

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SastFinding:
    """A single SAST finding from Semgrep."""
    rule_id: str
    severity: str  # ERROR, WARNING, INFO
    message: str
    file: str
    line: int
    end_line: Optional[int] = None
    column: Optional[int] = None
    end_column: Optional[int] = None
    category: str = "security"  # security, correctness, performance, style
    cwe: Optional[str] = None  # CWE ID if available
    owasp: Optional[str] = None  # OWASP category if available
    fix: Optional[str] = None  # Suggested fix if available
    code_snippet: Optional[str] = None  # The problematic code

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SemgrepClient:
    """Client for running Semgrep static analysis."""

    # Default rulesets for different analysis types
    DEFAULT_RULESETS = [
        "p/security-audit",  # Security issues
        "p/ci",  # CI-focused rules (performance, correctness)
    ]

    # Path to custom rules (relative to backend directory)
    CUSTOM_RULES_PATH = Path(__file__).parent.parent / "configs" / "semgrep_rules"

    # Language-specific rulesets
    LANGUAGE_RULESETS = {
        "python": ["p/python", "p/bandit"],
        "javascript": ["p/javascript", "p/nodejs"],
        "typescript": ["p/typescript", "p/react"],
        "java": ["p/java"],
        "go": ["p/golang"],
        "ruby": ["p/ruby"],
        "php": ["p/php"],
        "rust": ["p/rust"],
    }

    # Severity mapping from Semgrep to our standard
    SEVERITY_MAP = {
        "ERROR": "HIGH",
        "WARNING": "MEDIUM",
        "INFO": "LOW",
    }

    # Category mapping based on rule ID patterns
    CATEGORY_PATTERNS = {
        "security": ["security", "injection", "xss", "sqli", "auth", "crypto", "secrets"],
        "performance": ["performance", "complexity", "timeout", "memory"],
        "correctness": ["correctness", "bug", "error", "null", "undefined", "mutable", "falsy", "copy"],
        "style": ["style", "lint", "format", "naming"],
    }

    def __init__(self, rulesets: Optional[List[str]] = None, timeout: int = 120, use_custom_rules: bool = True):
        """Initialize Semgrep client.

        Args:
            rulesets: List of Semgrep rulesets to use (e.g., ["p/security-audit"])
            timeout: Timeout in seconds for Semgrep execution
            use_custom_rules: Whether to include custom rules from configs/semgrep_rules/
        """
        self.rulesets = rulesets or self.DEFAULT_RULESETS
        self.timeout = timeout
        self.use_custom_rules = use_custom_rules
        self._check_semgrep_installed()

    def _check_semgrep_installed(self) -> bool:
        """Check if Semgrep is installed."""
        try:
            result = subprocess.run(
                ["semgrep", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                logger.info(f"Semgrep version: {result.stdout.strip()}")
                return True
        except FileNotFoundError:
            logger.warning("Semgrep not installed. Install with: pip install semgrep")
        except subprocess.TimeoutExpired:
            logger.warning("Semgrep version check timed out")
        except Exception as e:
            logger.warning(f"Error checking Semgrep: {e}")
        return False

    def _detect_languages(self, files: List[Dict[str, Any]]) -> List[str]:
        """Detect programming languages from file extensions.

        Args:
            files: List of file dicts with 'filename' key

        Returns:
            List of detected language names
        """
        extension_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".java": "java",
            ".go": "go",
            ".rb": "ruby",
            ".php": "php",
            ".rs": "rust",
            ".c": "c",
            ".cpp": "cpp",
            ".cs": "csharp",
            ".swift": "swift",
            ".kt": "kotlin",
        }

        languages = set()
        for file_info in files:
            filename = file_info.get("filename", "")
            ext = Path(filename).suffix.lower()
            if ext in extension_map:
                languages.add(extension_map[ext])

        return list(languages)

    def _get_rulesets_for_languages(self, languages: List[str]) -> List[str]:
        """Get appropriate rulesets based on detected languages.

        Args:
            languages: List of detected language names

        Returns:
            Combined list of rulesets
        """
        rulesets = set(self.rulesets)

        for lang in languages:
            if lang in self.LANGUAGE_RULESETS:
                rulesets.update(self.LANGUAGE_RULESETS[lang])

        return list(rulesets)

    def _categorize_finding(self, rule_id: str, message: str) -> str:
        """Categorize a finding based on rule ID and message.

        Args:
            rule_id: Semgrep rule ID
            message: Finding message

        Returns:
            Category string
        """
        combined = f"{rule_id} {message}".lower()

        for category, patterns in self.CATEGORY_PATTERNS.items():
            for pattern in patterns:
                if pattern in combined:
                    return category

        return "security"  # Default to security

    def _extract_code_from_diff(self, diff_content: str, filename: str, line: int) -> Optional[str]:
        """Extract code snippet from diff for a specific file and line.

        Args:
            diff_content: Full diff content
            filename: File path to find
            line: Line number to extract

        Returns:
            Code snippet or None
        """
        try:
            # Find the file's diff section
            file_pattern = rf"diff --git a/.*?{re.escape(filename)}.*?(?=diff --git|$)"
            match = re.search(file_pattern, diff_content, re.DOTALL)
            if not match:
                return None

            file_diff = match.group(0)

            # Extract lines from the diff
            current_line = 0
            for diff_line in file_diff.split("\n"):
                if diff_line.startswith("@@"):
                    # Parse hunk header: @@ -old,count +new,count @@
                    hunk_match = re.search(r"\+(\d+)", diff_line)
                    if hunk_match:
                        current_line = int(hunk_match.group(1)) - 1
                elif diff_line.startswith("-"):
                    continue  # Skip removed lines
                elif diff_line.startswith("+") or not diff_line.startswith(("@@", "diff", "index", "---", "+++")):
                    current_line += 1
                    if current_line == line:
                        # Return the line content (strip the + prefix if present)
                        return diff_line[1:] if diff_line.startswith("+") else diff_line

        except Exception as e:
            logger.debug(f"Error extracting code from diff: {e}")

        return None

    def _parse_semgrep_output(
        self,
        output: Dict[str, Any],
        diff_content: Optional[str] = None
    ) -> List[SastFinding]:
        """Parse Semgrep JSON output into SastFinding objects.

        Args:
            output: Semgrep JSON output
            diff_content: Optional diff content for code extraction

        Returns:
            List of SastFinding objects
        """
        findings = []

        for result in output.get("results", []):
            try:
                rule_id = result.get("check_id", "unknown")
                extra = result.get("extra", {})
                metadata = extra.get("metadata", {})

                # Get severity
                severity_raw = extra.get("severity", "WARNING")
                severity = self.SEVERITY_MAP.get(severity_raw, "MEDIUM")

                # Get message
                message = extra.get("message", result.get("message", "No description"))

                # Get location
                start = result.get("start", {})
                end = result.get("end", {})
                file_path = result.get("path", "unknown")
                line = start.get("line", 0)
                end_line = end.get("line")
                column = start.get("col")
                end_column = end.get("col")

                # Get category
                category = self._categorize_finding(rule_id, message)

                # Get security metadata
                cwe = metadata.get("cwe")
                if isinstance(cwe, list):
                    cwe = ", ".join(cwe)
                owasp = metadata.get("owasp")
                if isinstance(owasp, list):
                    owasp = ", ".join(owasp)

                # Get fix if available
                fix = extra.get("fix")

                # Get code snippet
                code_snippet = extra.get("lines")
                if not code_snippet and diff_content:
                    code_snippet = self._extract_code_from_diff(diff_content, file_path, line)

                finding = SastFinding(
                    rule_id=rule_id,
                    severity=severity,
                    message=message,
                    file=file_path,
                    line=line,
                    end_line=end_line if end_line != line else None,
                    column=column,
                    end_column=end_column,
                    category=category,
                    cwe=cwe,
                    owasp=owasp,
                    fix=fix,
                    code_snippet=code_snippet,
                )

                findings.append(finding)

            except Exception as e:
                logger.warning(f"Error parsing Semgrep result: {e}")
                continue

        return findings

    def analyze_diff(
        self,
        diff_content: str,
        files: List[Dict[str, Any]],
        repo_path: Optional[str] = None,
        full_file_contents: Optional[Dict[str, str]] = None
    ) -> Tuple[bool, List[SastFinding], Optional[str]]:
        """Analyze code changes from a diff using Semgrep.

        This method creates a temporary directory with the changed files
        and runs Semgrep analysis on them.

        Args:
            diff_content: Git diff content
            files: List of file info dicts with 'filename' and 'patch' keys
            repo_path: Optional path to the full repo for context
            full_file_contents: Optional dict of {filepath: content} for full file analysis.
                               When provided, uses full content instead of extracting from patch.

        Returns:
            Tuple of (success, findings list, error message)
        """
        if not files:
            return True, [], None

        # Detect languages and get appropriate rulesets
        languages = self._detect_languages(files)
        if not languages:
            logger.info("No supported languages detected in PR files")
            return True, [], None

        rulesets = self._get_rulesets_for_languages(languages)
        logger.info(f"Detected languages: {languages}, using rulesets: {rulesets}")

        # Create temporary directory with the changed files
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Extract and write files
            files_created = 0
            for file_info in files:
                filename = file_info.get("filename", "")
                patch = file_info.get("patch", "")
                status = file_info.get("status", "modified")

                # Skip deleted files
                if status == "removed":
                    continue

                # Try to get full file content first, fall back to patch extraction
                file_content = None
                if full_file_contents and filename in full_file_contents:
                    file_content = full_file_contents[filename]
                    logger.debug(f"Using full content for {filename}")
                else:
                    # Extract the new file content from the patch
                    file_content = self._extract_file_content_from_patch(patch)

                if not file_content:
                    continue

                # Create the file in temp directory
                file_path = temp_path / filename
                file_path.parent.mkdir(parents=True, exist_ok=True)

                try:
                    file_path.write_text(file_content)
                    files_created += 1
                except Exception as e:
                    logger.warning(f"Error writing temp file {filename}: {e}")

            if files_created == 0:
                logger.info("No files extracted from patches for SAST analysis")
                return True, [], None

            logger.info(f"Created {files_created} temp files for SAST analysis")

            # Build Semgrep command
            cmd = [
                "semgrep",
                "--json",
                "--quiet",
                "--no-git-ignore",
                "--timeout", str(self.timeout),
            ]

            # Add rulesets
            for ruleset in rulesets:
                cmd.extend(["--config", ruleset])

            # Add custom rules if enabled and directory exists
            if self.use_custom_rules and self.CUSTOM_RULES_PATH.exists():
                custom_rule_files = list(self.CUSTOM_RULES_PATH.glob("*.yaml")) + list(self.CUSTOM_RULES_PATH.glob("*.yml"))
                for rule_file in custom_rule_files:
                    cmd.extend(["--config", str(rule_file)])
                    logger.debug(f"Added custom rule file: {rule_file.name}")
                if custom_rule_files:
                    logger.info(f"Using {len(custom_rule_files)} custom rule file(s)")

            # Add target directory
            cmd.append(str(temp_path))

            try:
                logger.info(f"Running Semgrep: {' '.join(cmd[:6])}...")
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout + 30,  # Extra buffer
                    cwd=temp_path
                )

                # Parse output
                if result.stdout:
                    try:
                        output = json.loads(result.stdout)
                        findings = self._parse_semgrep_output(output, diff_content)

                        # Adjust file paths (remove temp dir prefix)
                        for finding in findings:
                            if finding.file.startswith(str(temp_path)):
                                finding.file = finding.file[len(str(temp_path)) + 1:]

                        logger.info(f"Semgrep found {len(findings)} issues")
                        return True, findings, None

                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse Semgrep JSON output: {e}")
                        return False, [], f"Failed to parse Semgrep output: {e}"

                # No output usually means no findings
                if result.returncode == 0:
                    logger.info("Semgrep completed with no findings")
                    return True, [], None

                # Check for errors
                if result.stderr:
                    error_msg = result.stderr[:500]
                    logger.warning(f"Semgrep stderr: {error_msg}")
                    # Some warnings are normal, check if it's a real error
                    if "error" in error_msg.lower():
                        return False, [], f"Semgrep error: {error_msg}"

                return True, [], None

            except subprocess.TimeoutExpired:
                logger.error(f"Semgrep timed out after {self.timeout}s")
                return False, [], f"Semgrep analysis timed out after {self.timeout} seconds"

            except Exception as e:
                logger.exception(f"Error running Semgrep: {e}")
                return False, [], f"Failed to run Semgrep: {str(e)}"

    def _extract_file_content_from_patch(self, patch: str) -> Optional[str]:
        """Extract the new file content from a git patch.

        This reconstructs the file content by taking all lines that
        are either unchanged or added (ignoring removed lines).

        Args:
            patch: Git unified diff patch for a single file

        Returns:
            Reconstructed file content or None
        """
        if not patch:
            return None

        lines = []
        in_hunk = False

        for line in patch.split("\n"):
            # Skip diff headers
            if line.startswith(("diff ", "index ", "--- ", "+++ ", "\\ No newline")):
                continue

            # Hunk header indicates start of actual diff content
            if line.startswith("@@"):
                in_hunk = True
                continue

            if in_hunk:
                if line.startswith("-"):
                    # Skip removed lines
                    continue
                elif line.startswith("+"):
                    # Added line - include without the +
                    lines.append(line[1:])
                else:
                    # Context line (unchanged)
                    if line.startswith(" "):
                        lines.append(line[1:])
                    else:
                        lines.append(line)

        if not lines:
            return None

        return "\n".join(lines)

    def format_findings_for_prompt(
        self,
        findings: List[SastFinding],
        max_findings: int = 20
    ) -> str:
        """Format SAST findings for inclusion in AI prompt.

        Args:
            findings: List of SastFinding objects
            max_findings: Maximum number of findings to include

        Returns:
            Formatted string for prompt
        """
        if not findings:
            return "No SAST issues detected."

        # Sort by severity (HIGH first)
        severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        sorted_findings = sorted(
            findings,
            key=lambda f: severity_order.get(f.severity, 3)
        )

        # Limit findings
        if len(sorted_findings) > max_findings:
            sorted_findings = sorted_findings[:max_findings]
            truncated_msg = f"\n(Showing top {max_findings} of {len(findings)} findings)"
        else:
            truncated_msg = ""

        # Format output
        output_parts = [f"## SAST Analysis Results ({len(findings)} issues found){truncated_msg}\n"]

        for i, finding in enumerate(sorted_findings, 1):
            parts = [
                f"### Issue {i}: {finding.rule_id}",
                f"- **Severity**: {finding.severity}",
                f"- **Category**: {finding.category}",
                f"- **File**: {finding.file}:{finding.line}",
            ]

            if finding.end_line:
                parts[-1] = f"- **File**: {finding.file}:{finding.line}-{finding.end_line}"

            parts.append(f"- **Message**: {finding.message}")

            if finding.cwe:
                parts.append(f"- **CWE**: {finding.cwe}")

            if finding.owasp:
                parts.append(f"- **OWASP**: {finding.owasp}")

            if finding.code_snippet:
                parts.append(f"- **Code**:\n```\n{finding.code_snippet}\n```")

            if finding.fix:
                parts.append(f"- **Suggested Fix**: {finding.fix}")

            output_parts.append("\n".join(parts))

        return "\n\n".join(output_parts)


def get_semgrep_client(
    rulesets: Optional[List[str]] = None,
    timeout: int = 120
) -> SemgrepClient:
    """Get a Semgrep client instance.

    Args:
        rulesets: Optional list of Semgrep rulesets
        timeout: Analysis timeout in seconds

    Returns:
        SemgrepClient instance
    """
    return SemgrepClient(rulesets=rulesets, timeout=timeout)
