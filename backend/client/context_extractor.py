"""Context extractor for enriching PR review with additional context.

Extracts:
1. Full content of changed files (not just diff)
2. Repository directory structure
3. Related context files (imports, references)
4. Files imported in diff additions (+ lines) - for cross-file analysis
"""

import re
from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, field

from client.github_client import GitHubClient
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class FileContext:
    """Context information for a single file."""
    path: str
    content: str
    language: str
    size: int
    is_changed: bool = True


@dataclass
class RepoStructure:
    """Repository directory structure."""
    tree: Dict[str, Any]  # Nested directory structure
    file_count: int
    dir_count: int
    languages: List[str]

    def to_tree_string(self, max_depth: int = 3) -> str:
        """Convert structure to tree-like string representation."""
        lines = []
        self._build_tree_string(self.tree, "", lines, 0, max_depth)
        return "\n".join(lines)

    def _build_tree_string(self, node: Dict, prefix: str, lines: List[str], depth: int, max_depth: int):
        """Recursively build tree string."""
        if depth >= max_depth:
            if node:
                lines.append(f"{prefix}... ({len(node)} more items)")
            return

        items = sorted(node.items())
        for i, (name, content) in enumerate(items):
            is_last = i == len(items) - 1
            current_prefix = "└── " if is_last else "├── "
            next_prefix = "    " if is_last else "│   "

            if isinstance(content, dict):
                # Directory
                lines.append(f"{prefix}{current_prefix}{name}/")
                self._build_tree_string(content, prefix + next_prefix, lines, depth + 1, max_depth)
            else:
                # File
                lines.append(f"{prefix}{current_prefix}{name}")


@dataclass
class ExtractedContext:
    """Complete extracted context for a PR."""
    changed_files: List[FileContext]
    related_files: List[FileContext]
    repo_structure: Optional[RepoStructure]
    import_graph: Dict[str, List[str]]  # file -> list of imports
    # NEW: Files that are newly imported in the diff (from + lines)
    # These are high-priority for cross-file analysis
    diff_imported_files: List[FileContext] = field(default_factory=list)

    def to_prompt_section(self, max_total_size: int = 40000) -> str:
        """Convert context to prompt section for LLM with size limits.

        Args:
            max_total_size: Maximum total size of the prompt section

        Returns:
            Formatted prompt section string
        """
        sections = []
        current_size = 0

        # Repository structure (small, always include)
        if self.repo_structure:
            struct_section = "## Repository Structure\n```\n"
            struct_section += self.repo_structure.to_tree_string(max_depth=3)[:2000]
            struct_section += "\n```\n"
            struct_section += f"Languages: {', '.join(self.repo_structure.languages[:10])}\n"
            sections.append(struct_section)
            current_size += len(struct_section)

        # Budget allocation: 60% changed, 25% diff-imported (high priority), 15% related
        changed_budget = int((max_total_size - current_size) * 0.60)
        diff_imported_budget = int((max_total_size - current_size) * 0.25)
        related_budget = int((max_total_size - current_size) * 0.15)

        # Changed files with full content (as CONTEXT ONLY - not for review)
        if self.changed_files:
            sections.append("\n## Changed Files (Context Reference)\n")
            sections.append("**IMPORTANT: This section provides the FULL file content for CONTEXT ONLY.**\n")
            sections.append("**You should ONLY review changes shown in the Git Diff section, NOT the entire file.**\n")
            sections.append("**Use this context to understand the surrounding code and validate changes, but do NOT report issues in code that wasn't changed in this PR.**\n\n")
            current_size += 300

            # Limit number of files based on budget
            max_files = min(len(self.changed_files), 10)
            per_file_budget = changed_budget // max(max_files, 1)

            files_included = 0
            for f in self.changed_files[:max_files]:
                # Calculate per-file limit
                file_limit = min(per_file_budget, 10000)
                content = f.content[:file_limit] if len(f.content) > file_limit else f.content

                file_section = f"### {f.path}\n```{f.language}\n{content}\n```\n"

                if current_size + len(file_section) > max_total_size - diff_imported_budget - related_budget:
                    if files_included == 0:
                        # At least include one file, truncated
                        content = f.content[:3000]
                        file_section = f"### {f.path}\n```{f.language}\n{content}\n... [truncated]\n```\n"
                        sections.append(file_section)
                        files_included += 1
                    break

                sections.append(file_section)
                current_size += len(file_section)
                files_included += 1

            if files_included < len(self.changed_files):
                sections.append(f"\n*... and {len(self.changed_files) - files_included} more changed files*\n")

        # NEW: Diff-imported files (HIGH PRIORITY - newly added imports in this PR)
        remaining_budget = max_total_size - current_size
        if self.diff_imported_files and remaining_budget > 1000:
            sections.append("\n## Newly Imported Files (Cross-File Analysis)\n")
            sections.append("**IMPORTANT: These files are NEWLY IMPORTED in this PR's diff.**\n")
            sections.append("**Check if the usage of these imported components/functions is correct.**\n")
            sections.append("**Pay attention to: required props, function signatures, expected types.**\n\n")
            current_size += 200

            # Higher priority - more files, larger per-file limit
            max_diff_imported = min(len(self.diff_imported_files), 5)
            per_file_limit = min(diff_imported_budget // max(max_diff_imported, 1), 8000)

            for f in self.diff_imported_files[:max_diff_imported]:
                content = f.content[:per_file_limit] if len(f.content) > per_file_limit else f.content
                file_section = f"### {f.path}\n```{f.language}\n{content}\n```\n"

                if current_size + len(file_section) > max_total_size - related_budget:
                    break

                sections.append(file_section)
                current_size += len(file_section)

        # Related context files (if budget allows)
        remaining_budget = max_total_size - current_size
        if self.related_files and remaining_budget > 1000:
            sections.append("\n## Related Context Files\n")
            sections.append("*These files are referenced by the changed files.*\n")
            current_size += 60

            # Fewer related files, smaller per-file limit
            max_related = min(len(self.related_files), 3)
            per_file_limit = min(remaining_budget // max(max_related, 1), 5000)

            for f in self.related_files[:max_related]:
                content = f.content[:per_file_limit] if len(f.content) > per_file_limit else f.content
                file_section = f"### {f.path}\n```{f.language}\n{content}\n```\n"

                if current_size + len(file_section) > max_total_size:
                    break

                sections.append(file_section)
                current_size += len(file_section)

        return "\n".join(sections)


class ContextExtractor:
    """Extracts rich context from GitHub repositories for code review."""

    # Language detection by file extension
    EXTENSION_TO_LANGUAGE = {
        '.py': 'python',
        '.js': 'javascript',
        '.jsx': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.java': 'java',
        '.go': 'go',
        '.rs': 'rust',
        '.rb': 'ruby',
        '.php': 'php',
        '.c': 'c',
        '.cpp': 'cpp',
        '.h': 'c',
        '.hpp': 'cpp',
        '.cs': 'csharp',
        '.swift': 'swift',
        '.kt': 'kotlin',
        '.scala': 'scala',
        '.r': 'r',
        '.sql': 'sql',
        '.sh': 'bash',
        '.yml': 'yaml',
        '.yaml': 'yaml',
        '.json': 'json',
        '.xml': 'xml',
        '.html': 'html',
        '.css': 'css',
        '.scss': 'scss',
        '.md': 'markdown',
    }

    # Import patterns for different languages
    IMPORT_PATTERNS = {
        'python': [
            r'^import\s+([\w.]+)',
            r'^from\s+([\w.]+)\s+import',
        ],
        'javascript': [
            r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]',
            r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
        ],
        'typescript': [
            r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]',
            r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
        ],
        'java': [
            r'^import\s+([\w.]+);',
        ],
        'go': [
            r'import\s+"([^"]+)"',
            r'import\s+\(\s*"([^"]+)"',
        ],
        'ruby': [
            r"require\s+['\"]([^'\"]+)['\"]",
            r"require_relative\s+['\"]([^'\"]+)['\"]",
            r"load\s+['\"]([^'\"]+)['\"]",
        ],
    }

    def __init__(self, github_client: GitHubClient):
        """Initialize context extractor.

        Args:
            github_client: GitHub API client instance
        """
        self.github_client = github_client

    def _detect_language(self, filepath: str) -> str:
        """Detect language from file extension."""
        for ext, lang in self.EXTENSION_TO_LANGUAGE.items():
            if filepath.endswith(ext):
                return lang
        return ""

    def _extract_imports(self, content: str, language: str) -> List[str]:
        """Extract import statements from file content.

        Args:
            content: File content
            language: Programming language

        Returns:
            List of imported module/file paths
        """
        imports = []
        patterns = self.IMPORT_PATTERNS.get(language, [])

        for pattern in patterns:
            matches = re.findall(pattern, content, re.MULTILINE)
            imports.extend(matches)

        return imports

    def _resolve_import_to_file(
        self,
        import_path: str,
        source_file: str,
        language: str,
        repo_files: Set[str]
    ) -> Optional[str]:
        """Try to resolve an import path to an actual file in the repo.

        Args:
            import_path: The import statement path
            source_file: The file containing the import
            language: Programming language
            repo_files: Set of all files in the repo

        Returns:
            Resolved file path or None
        """
        # Get directory of source file
        source_dir = "/".join(source_file.split("/")[:-1])

        if language == 'python':
            # Convert module path to file path
            # e.g., "utils.logger" -> "utils/logger.py"
            candidates = [
                import_path.replace(".", "/") + ".py",
                import_path.replace(".", "/") + "/__init__.py",
                source_dir + "/" + import_path.replace(".", "/") + ".py",
            ]
        elif language in ('javascript', 'typescript'):
            # Handle relative and absolute imports
            if import_path.startswith('.'):
                # Relative import
                base = import_path
                candidates = [
                    source_dir + "/" + base.lstrip('./') + ".js",
                    source_dir + "/" + base.lstrip('./') + ".ts",
                    source_dir + "/" + base.lstrip('./') + ".tsx",
                    source_dir + "/" + base.lstrip('./') + "/index.js",
                    source_dir + "/" + base.lstrip('./') + "/index.ts",
                ]
            else:
                # Could be from node_modules or src
                candidates = [
                    "src/" + import_path + ".ts",
                    "src/" + import_path + ".tsx",
                    "src/" + import_path + "/index.ts",
                ]
        elif language == 'java':
            # Convert package path to file path
            candidates = [
                import_path.replace(".", "/") + ".java",
            ]
        elif language == 'go':
            # Go imports are typically packages
            candidates = [
                import_path + ".go",
            ]
        else:
            return None

        # Check which candidate exists
        for candidate in candidates:
            # Normalize path
            normalized = candidate.replace("//", "/").lstrip("/")
            if normalized in repo_files:
                return normalized

        return None

    def get_repo_structure(
        self,
        owner: str,
        repo: str,
        ref: Optional[str] = None,
        max_files: int = 500
    ) -> RepoStructure:
        """Get repository directory structure.

        Args:
            owner: Repository owner
            repo: Repository name
            ref: Git ref (branch/tag/sha)
            max_files: Maximum number of files to include

        Returns:
            RepoStructure object
        """
        try:
            # Use GitHub Trees API for efficient structure retrieval
            url = f"{self.github_client.base_url}/repos/{owner}/{repo}/git/trees/{ref or 'HEAD'}?recursive=1"
            response = self.github_client.session.get(url, timeout=30)
            response.raise_for_status()

            data = response.json()
            tree_data = data.get('tree', [])

            # Build nested structure
            structure: Dict[str, Any] = {}
            file_count = 0
            dir_count = 0
            languages: Set[str] = set()

            for item in tree_data[:max_files]:
                path = item['path']
                item_type = item['type']

                # Split path into parts
                parts = path.split('/')
                current = structure

                for i, part in enumerate(parts[:-1]):
                    if part not in current:
                        current[part] = {}
                        dir_count += 1
                    current = current[part]

                # Add file or directory
                if item_type == 'blob':  # File
                    current[parts[-1]] = None  # None indicates file
                    file_count += 1

                    # Detect language
                    lang = self._detect_language(path)
                    if lang:
                        languages.add(lang)
                elif item_type == 'tree':  # Directory
                    if parts[-1] not in current:
                        current[parts[-1]] = {}
                        dir_count += 1

            return RepoStructure(
                tree=structure,
                file_count=file_count,
                dir_count=dir_count,
                languages=sorted(list(languages))
            )

        except Exception as e:
            logger.warning(f"Failed to get repo structure: {e}")
            return RepoStructure(tree={}, file_count=0, dir_count=0, languages=[])

    def get_changed_files_content(
        self,
        owner: str,
        repo: str,
        files: List[Dict[str, Any]],
        ref: Optional[str] = None,
        max_file_size: int = 100000
    ) -> List[FileContext]:
        """Get full content of changed files.

        Args:
            owner: Repository owner
            repo: Repository name
            files: List of changed files from PR
            ref: Git ref to fetch from (usually head SHA)
            max_file_size: Maximum file size to fetch

        Returns:
            List of FileContext objects
        """
        contexts = []

        for file_info in files:
            filepath = file_info.get('filename', '')
            status = file_info.get('status', '')

            # Skip deleted files
            if status == 'removed':
                continue

            # Skip large files based on changes count
            changes = file_info.get('changes', 0)
            if changes > 5000:
                logger.info(f"Skipping large file: {filepath}")
                continue

            try:
                success, content, error = self.github_client.get_file_content(
                    owner, repo, filepath, ref
                )

                if success and len(content) <= max_file_size:
                    language = self._detect_language(filepath)
                    contexts.append(FileContext(
                        path=filepath,
                        content=content,
                        language=language,
                        size=len(content),
                        is_changed=True
                    ))
                    logger.debug(f"Fetched content for: {filepath}")
                elif not success:
                    logger.warning(f"Failed to fetch {filepath}: {error}")

            except Exception as e:
                logger.warning(f"Error fetching {filepath}: {e}")

        return contexts

    def get_related_files(
        self,
        owner: str,
        repo: str,
        changed_files: List[FileContext],
        ref: Optional[str] = None,
        max_related: int = 5,
        max_file_size: int = 50000
    ) -> List[FileContext]:
        """Get files related to changed files through imports/references.

        Args:
            owner: Repository owner
            repo: Repository name
            changed_files: List of changed file contexts
            ref: Git ref to fetch from
            max_related: Maximum number of related files to fetch
            max_file_size: Maximum file size to fetch

        Returns:
            List of related FileContext objects
        """
        # First get all files in repo
        try:
            url = f"{self.github_client.base_url}/repos/{owner}/{repo}/git/trees/{ref or 'HEAD'}?recursive=1"
            response = self.github_client.session.get(url, timeout=30)
            response.raise_for_status()

            tree_data = response.json().get('tree', [])
            repo_files = {item['path'] for item in tree_data if item['type'] == 'blob'}
        except Exception as e:
            logger.warning(f"Failed to get repo file list: {e}")
            return []

        # Build import graph and find related files
        related_paths: Set[str] = set()
        changed_paths = {f.path for f in changed_files}

        for file_ctx in changed_files:
            if not file_ctx.language:
                continue

            imports = self._extract_imports(file_ctx.content, file_ctx.language)

            for imp in imports:
                resolved = self._resolve_import_to_file(
                    imp, file_ctx.path, file_ctx.language, repo_files
                )
                if resolved and resolved not in changed_paths:
                    related_paths.add(resolved)

        # Fetch related files
        related_contexts = []
        for filepath in list(related_paths)[:max_related]:
            try:
                success, content, error = self.github_client.get_file_content(
                    owner, repo, filepath, ref
                )

                if success and len(content) <= max_file_size:
                    language = self._detect_language(filepath)
                    related_contexts.append(FileContext(
                        path=filepath,
                        content=content,
                        language=language,
                        size=len(content),
                        is_changed=False
                    ))
                    logger.debug(f"Fetched related file: {filepath}")

            except Exception as e:
                logger.warning(f"Error fetching related file {filepath}: {e}")

        return related_contexts

    def _extract_imports_from_diff_additions(
        self,
        diff_content: str,
        pr_files: List[Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        """Extract import statements from diff addition lines (+ lines).

        This specifically extracts NEW imports added in this PR, which are
        high-priority targets for cross-file analysis.

        Args:
            diff_content: The full diff content
            pr_files: List of changed files from PR

        Returns:
            Dict mapping source file to list of newly imported modules
        """
        new_imports: Dict[str, List[str]] = {}

        # Parse diff to extract + lines with imports for each file
        current_file = None
        current_language = None

        for line in diff_content.split('\n'):
            # Detect file header in diff
            if line.startswith('diff --git'):
                # Extract filename from diff header: diff --git a/path/file b/path/file
                match = re.search(r'b/(.+)$', line)
                if match:
                    current_file = match.group(1)
                    current_language = self._detect_language(current_file)
                continue

            # Also check for +++ header
            if line.startswith('+++'):
                match = re.search(r'\+\+\+ b/(.+)$', line)
                if match:
                    current_file = match.group(1)
                    current_language = self._detect_language(current_file)
                continue

            # Only process addition lines (starts with +, but not +++)
            if not line.startswith('+') or line.startswith('+++'):
                continue

            # Remove the leading + to get the actual line content
            line_content = line[1:]

            # Skip if no language detected
            if not current_language or not current_file:
                continue

            # Extract imports from this added line
            patterns = self.IMPORT_PATTERNS.get(current_language, [])
            for pattern in patterns:
                matches = re.findall(pattern, line_content)
                if matches:
                    if current_file not in new_imports:
                        new_imports[current_file] = []
                    new_imports[current_file].extend(matches)

        # Log what we found
        total_imports = sum(len(v) for v in new_imports.values())
        if total_imports > 0:
            logger.info(f"Found {total_imports} new imports in diff additions across {len(new_imports)} files")
            for file, imports in new_imports.items():
                logger.debug(f"  {file}: {imports}")

        return new_imports

    def get_diff_imported_files(
        self,
        owner: str,
        repo: str,
        diff_content: str,
        pr_files: List[Dict[str, Any]],
        changed_paths: Set[str],
        ref: Optional[str] = None,
        max_files: int = 10,
        max_file_size: int = 50000
    ) -> List[FileContext]:
        """Get files that are newly imported in the diff additions.

        These are HIGH PRIORITY for cross-file analysis because:
        1. The PR is adding a dependency on these files
        2. Bugs often occur when new imports are used incorrectly (e.g., missing props, wrong API)

        Args:
            owner: Repository owner
            repo: Repository name
            diff_content: The full diff content
            pr_files: List of changed files from PR
            changed_paths: Set of paths that are already changed (to avoid duplicates)
            ref: Git ref to fetch from
            max_files: Maximum number of files to fetch
            max_file_size: Maximum file size to fetch

        Returns:
            List of FileContext objects for newly imported files
        """
        # Extract new imports from diff
        new_imports = self._extract_imports_from_diff_additions(diff_content, pr_files)

        if not new_imports:
            return []

        # Get repo file list for resolution
        try:
            url = f"{self.github_client.base_url}/repos/{owner}/{repo}/git/trees/{ref or 'HEAD'}?recursive=1"
            response = self.github_client.session.get(url, timeout=30)
            response.raise_for_status()

            tree_data = response.json().get('tree', [])
            repo_files = {item['path'] for item in tree_data if item['type'] == 'blob'}
        except Exception as e:
            logger.warning(f"Failed to get repo file list for diff import resolution: {e}")
            return []

        # Resolve imports to actual files
        resolved_paths: Set[str] = set()
        for source_file, imports in new_imports.items():
            source_language = self._detect_language(source_file)
            if not source_language:
                continue

            for imp in imports:
                resolved = self._resolve_import_to_file(imp, source_file, source_language, repo_files)
                if resolved and resolved not in changed_paths:
                    resolved_paths.add(resolved)
                    logger.debug(f"Resolved new import: {imp} -> {resolved}")

        if not resolved_paths:
            logger.info("No new imports could be resolved to repo files")
            return []

        logger.info(f"Resolved {len(resolved_paths)} new import paths to fetch")

        # Fetch the files
        diff_imported_files = []
        for filepath in list(resolved_paths)[:max_files]:
            try:
                success, content, error = self.github_client.get_file_content(
                    owner, repo, filepath, ref
                )

                if success and len(content) <= max_file_size:
                    language = self._detect_language(filepath)
                    diff_imported_files.append(FileContext(
                        path=filepath,
                        content=content,
                        language=language,
                        size=len(content),
                        is_changed=False
                    ))
                    logger.debug(f"Fetched diff-imported file: {filepath}")
                elif not success:
                    logger.warning(f"Failed to fetch diff-imported file {filepath}: {error}")

            except Exception as e:
                logger.warning(f"Error fetching diff-imported file {filepath}: {e}")

        logger.info(f"Fetched {len(diff_imported_files)} newly imported files from diff")
        return diff_imported_files

    def extract_context(
        self,
        owner: str,
        repo: str,
        pr_files: List[Dict[str, Any]],
        head_ref: Optional[str] = None,
        include_structure: bool = True,
        include_related: bool = True,
        diff_content: Optional[str] = None  # NEW: Pass diff to extract new imports
    ) -> ExtractedContext:
        """Extract complete context for PR review.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_files: List of changed files from PR
            head_ref: Head commit SHA
            include_structure: Whether to include repo structure
            include_related: Whether to include related files
            diff_content: The diff content (for extracting newly added imports)

        Returns:
            ExtractedContext object with all context data
        """
        logger.info(f"Extracting context for {owner}/{repo}")

        # Get changed files content
        changed_files = self.get_changed_files_content(
            owner, repo, pr_files, head_ref
        )
        logger.info(f"Extracted {len(changed_files)} changed files")

        # Track changed paths to avoid duplicates
        changed_paths = {f.path for f in changed_files}

        # Get repo structure
        repo_structure = None
        if include_structure:
            repo_structure = self.get_repo_structure(owner, repo, head_ref)
            logger.info(f"Extracted repo structure: {repo_structure.file_count} files")

        # Get related files (from ALL imports in changed files)
        related_files = []
        if include_related and changed_files:
            related_files = self.get_related_files(
                owner, repo, changed_files, head_ref
            )
            logger.info(f"Extracted {len(related_files)} related files")

        # NEW: Get files that are NEWLY imported in the diff (high priority)
        diff_imported_files = []
        if diff_content and include_related:
            # Exclude files already in changed_files or related_files
            all_fetched_paths = changed_paths | {f.path for f in related_files}
            diff_imported_files = self.get_diff_imported_files(
                owner, repo, diff_content, pr_files, all_fetched_paths, head_ref
            )
            logger.info(f"Extracted {len(diff_imported_files)} newly imported files from diff")

        # Build import graph
        import_graph = {}
        for file_ctx in changed_files:
            if file_ctx.language:
                imports = self._extract_imports(file_ctx.content, file_ctx.language)
                if imports:
                    import_graph[file_ctx.path] = imports

        return ExtractedContext(
            changed_files=changed_files,
            related_files=related_files,
            repo_structure=repo_structure,
            import_graph=import_graph,
            diff_imported_files=diff_imported_files  # NEW
        )


def get_context_extractor(github_client: GitHubClient) -> ContextExtractor:
    """Factory function to create ContextExtractor.

    Args:
        github_client: GitHub API client

    Returns:
        ContextExtractor instance
    """
    return ContextExtractor(github_client)
