"""LangGraph workflow for code review with SAST and Intent Analysis agents.

This module implements a two-agent workflow:
1. SAST Agent: Runs static code analysis using Semgrep
2. Intent Analysis Agent: Analyzes code intent and implementation quality using LLM

Both agents run in PARALLEL and their results are combined for the final code review.
"""

import time
import asyncio
from typing import Dict, Any, List, Optional, TypedDict
from dataclasses import dataclass

from langgraph.graph import StateGraph, END

from client.github_client import GitHubClient, get_github_client
from client.semgrep_client import get_semgrep_client
from client.symbol_extractor import get_symbol_extractor
from client.context_extractor import ContextExtractor, ExtractedContext, get_context_extractor
from client.claude_api_client import get_claude_api_client
from client.glm_api_client import get_glm_api_client
from configs.pr_size_limits import (
    DEFAULT_LIMITS, PRSizeMetrics, calculate_pr_metrics,
    truncate_content, prioritize_files, smart_diff_truncate
)
from utils.logger import get_logger
from utils.json_parser import parse_json_with_fallbacks

logger = get_logger(__name__)


# ============ State Definitions ============

class ReviewState(TypedDict, total=False):
    """State shared across all workflow nodes.

    Input fields are plain types (set once, never overwritten).
    Output fields from parallel nodes use plain types too - LangGraph
    handles merging automatically since each parallel node writes to
    different keys.
    """
    # Input data - set once at start, read-only by nodes
    repo_owner: str
    repo_name: str
    pr_number: int
    provider: str
    model: Optional[str]
    github_token: Optional[str]
    api_key: Optional[str]

    # PR data from GitHub - set by fetch_pr_data
    pr_info: Dict[str, Any]
    diff_content: str
    files: List[Dict[str, Any]]
    pr_context: Dict[str, Any]

    # Extracted context - set by fetch_pr_data
    extracted_context: Optional[Dict[str, Any]]
    context_prompt_section: str

    # SAST results - set by run_sast_analysis only
    sast_success: bool
    sast_findings: List[Dict[str, Any]]
    sast_error: Optional[str]
    sast_prompt_section: str
    sast_duration_ms: int
    languages_detected: List[str]

    # Symbol table - set by run_sast_analysis
    symbol_table_prompt: str

    # Intent analysis results - set by run_intent_analysis only
    intent_success: bool
    intent_analysis: Dict[str, Any]
    intent_error: Optional[str]
    intent_duration_ms: int

    # Final output - set by combine_results
    combined_prompt: str
    workflow_error: Optional[str]


@dataclass
class IntentAnalysis:
    """Result of intent analysis."""
    purpose: str
    implementation_approach: str
    key_changes: List[str]
    potential_issues: List[str]
    missing_considerations: List[str]
    architectural_impact: str
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "purpose": self.purpose,
            "implementation_approach": self.implementation_approach,
            "key_changes": self.key_changes,
            "potential_issues": self.potential_issues,
            "missing_considerations": self.missing_considerations,
            "architectural_impact": self.architectural_impact,
            "confidence": self.confidence
        }


# ============ Workflow Nodes ============

async def fetch_pr_data(state: ReviewState) -> Dict[str, Any]:
    """Fetch PR data from GitHub including extended context with size limits."""
    logger.info(f"Fetching PR data for {state.get('repo_owner', '')}/{state.get('repo_name', '')}#{state.get('pr_number', 0)}")
    logger.debug(f"fetch_pr_data received state keys: {list(state.keys())}")
    logger.debug(f"fetch_pr_data state values: repo_owner={state.get('repo_owner')!r}, repo_name={state.get('repo_name')!r}, pr_number={state.get('pr_number')!r}")

    try:
        github_client = get_github_client(token=state.get('github_token'))

        repo_owner = state.get('repo_owner', '')
        repo_name = state.get('repo_name', '')
        pr_number = state.get('pr_number', 0)

        if not repo_owner or not repo_name or not pr_number:
            logger.error(f"Missing required state values: repo_owner={repo_owner!r}, repo_name={repo_name!r}, pr_number={pr_number!r}")
            return {'workflow_error': 'Missing required PR identification in state'}

        # Get basic PR review data
        review_data = github_client.get_pr_review_data(
            repo_owner,
            repo_name,
            pr_number
        )

        # Calculate PR size metrics for optimization decisions
        pr_metrics = calculate_pr_metrics(review_data['files'], review_data['diff'])
        processing_mode = pr_metrics.get_recommended_mode()

        logger.info(f"PR metrics: {pr_metrics.file_count} files, {pr_metrics.total_changes} lines changed, "
                   f"diff size: {pr_metrics.diff_size_chars} chars, mode: {processing_mode}")

        # Apply size limits based on PR size
        files_to_process = review_data['files']
        diff_content = review_data['diff']

        # Handle diff-only mode: too many files, skip fetching full file content
        if processing_mode == "diff_only":
            logger.warning(f"Diff-only mode: {pr_metrics.file_count} files exceeds limit "
                          f"({DEFAULT_LIMITS.max_files_for_file_content}), skipping full file content fetch")

            # Only truncate diff if needed
            diff_content = smart_diff_truncate(
                review_data['diff'],
                DEFAULT_LIMITS.max_diff_size * 2,  # Allow larger diff in diff-only mode
                files_to_process
            )

            # Return with empty extracted_context - only diff will be used for analysis
            return {
                'pr_info': review_data['pr'],
                'diff_content': diff_content,
                'files': files_to_process,
                'pr_context': review_data['context'],
                'extracted_context': {
                    'changed_files': [],  # No full file content
                    'related_files': [],
                    'repo_structure': None,
                    'import_graph': {},
                    'diff_only_mode': True,  # Flag to indicate diff-only mode
                },
                'context_prompt_section': f"## Analysis Mode\nDiff-only analysis ({pr_metrics.file_count} files - full content fetch skipped for performance)\n",
            }

        if processing_mode == "summary":
            # Very large PR: prioritize files and heavily truncate
            files_to_process = prioritize_files(review_data['files'], DEFAULT_LIMITS.max_files_for_full_analysis)
            diff_content = smart_diff_truncate(
                review_data['diff'],
                DEFAULT_LIMITS.max_diff_size,
                files_to_process
            )
            logger.warning(f"Large PR detected: reduced from {len(review_data['files'])} to {len(files_to_process)} files")
        elif processing_mode == "truncated":
            # Large PR: moderate truncation
            diff_content = truncate_content(
                review_data['diff'],
                DEFAULT_LIMITS.max_diff_size,
                "\n... [diff truncated due to size]"
            )

        # Extract extended context (with reduced scope for large PRs)
        context_extractor = get_context_extractor(github_client)
        head_ref = review_data['pr'].get('head_sha')

        # Adjust context extraction based on PR size
        include_related = processing_mode == "full"
        max_files_for_context = DEFAULT_LIMITS.max_files_for_full_analysis if processing_mode != "summary" else 10

        # Pass diff_content to extract newly added imports
        extracted = await asyncio.to_thread(
            context_extractor.extract_context,
            owner=repo_owner,
            repo=repo_name,
            pr_files=files_to_process[:max_files_for_context],
            head_ref=head_ref,
            include_structure=True,
            include_related=include_related,
            diff_content=diff_content  # NEW: Pass diff to extract new imports
        )

        # Convert to dict for state storage
        # Keep full content for SAST analysis, truncated content for LLM prompts
        extracted_context = {
            'changed_files': [
                {
                    'path': f.path,
                    'content': f.content,  # Full content for SAST/symbol extraction
                    'content_for_prompt': f.content[:DEFAULT_LIMITS.max_file_content_size],  # Truncated for LLM
                    'language': f.language,
                    'size': f.size
                }
                for f in extracted.changed_files[:DEFAULT_LIMITS.max_files_for_full_analysis]
            ],
            'related_files': [
                {'path': f.path, 'content': f.content[:DEFAULT_LIMITS.max_related_file_size], 'language': f.language, 'size': f.size}
                for f in extracted.related_files[:DEFAULT_LIMITS.max_related_files]
            ],
            # NEW: Newly imported files from diff additions (high priority for cross-file analysis)
            'diff_imported_files': [
                {'path': f.path, 'content': f.content[:DEFAULT_LIMITS.max_diff_imported_file_size], 'language': f.language, 'size': f.size}
                for f in extracted.diff_imported_files[:DEFAULT_LIMITS.max_diff_imported_files]
            ],
            'repo_structure': {
                'tree_string': extracted.repo_structure.to_tree_string()[:2000] if extracted.repo_structure else "",
                'languages': extracted.repo_structure.languages[:10] if extracted.repo_structure else [],
                'file_count': extracted.repo_structure.file_count if extracted.repo_structure else 0,
            } if extracted.repo_structure else None,
            'import_graph': extracted.import_graph,
            'diff_only_mode': False,
        }

        logger.info(f"Fetched PR data: {len(files_to_process)} files (of {len(review_data['files'])}), "
                   f"{len(extracted.changed_files)} with full content, "
                   f"{len(extracted.related_files)} related files, "
                   f"{len(extracted.diff_imported_files)} newly imported files")

        return {
            'pr_info': review_data['pr'],
            'diff_content': diff_content,
            'files': files_to_process,
            'pr_context': review_data['context'],
            'extracted_context': extracted_context,
            'context_prompt_section': extracted.to_prompt_section(max_total_size=DEFAULT_LIMITS.max_context_prompt_size),
        }

    except Exception as e:
        logger.exception(f"Error fetching PR data: {e}")
        return {
            'workflow_error': f"Failed to fetch PR data: {str(e)}"
        }


async def run_sast_analysis(state: ReviewState) -> Dict[str, Any]:
    """Run SAST analysis using Semgrep and symbol extraction in parallel."""
    logger.info("Running SAST analysis...")
    start_time = time.time()

    try:
        semgrep_client = get_semgrep_client()
        symbol_extractor = get_symbol_extractor()

        # Check if we're in diff-only mode
        extracted_context = state.get('extracted_context')
        diff_only_mode = extracted_context.get('diff_only_mode', False) if extracted_context else False

        # Extract full file contents from extracted_context if available
        # Use full 'content' field (not truncated 'content_for_prompt') for SAST analysis
        full_file_contents = None
        if extracted_context and not diff_only_mode:
            changed_files = extracted_context.get('changed_files', [])
            if changed_files:
                full_file_contents = {
                    f['path']: f['content']
                    for f in changed_files
                    if f.get('path') and f.get('content')
                }
                # Log total content size to verify full files are being used
                total_content_size = sum(len(c) for c in full_file_contents.values())
                logger.info(f"Using full content for {len(full_file_contents)} files in SAST (total: {total_content_size} chars)")
        elif diff_only_mode:
            logger.info("Diff-only mode: SAST will analyze diff content without full file contents")

        # Run Semgrep and Symbol extraction in PARALLEL
        semgrep_task = asyncio.to_thread(
            semgrep_client.analyze_diff,
            diff_content=state.get('diff_content', ''),
            files=state.get('files', []),
            full_file_contents=full_file_contents
        )

        # Create symbol extraction task if available (skip in diff-only mode)
        symbol_task = None
        if full_file_contents and symbol_extractor.is_available() and not diff_only_mode:
            symbol_task = asyncio.to_thread(
                symbol_extractor.extract_from_files,
                full_file_contents
            )

        # Wait for both tasks to complete in parallel
        if symbol_task:
            semgrep_result, symbol_result = await asyncio.gather(
                semgrep_task,
                symbol_task,
                return_exceptions=True
            )
        else:
            semgrep_result = await semgrep_task
            symbol_result = None

        # Process Semgrep results
        if isinstance(semgrep_result, Exception):
            raise semgrep_result
        success, findings, error = semgrep_result

        # Process Symbol extraction results
        symbol_table_prompt = ""
        if symbol_result is not None:
            if isinstance(symbol_result, Exception):
                logger.warning(f"Symbol extraction failed: {symbol_result}")
            elif isinstance(symbol_result, dict):
                try:
                    file_symbols = symbol_result
                    symbol_table_prompt = symbol_extractor.format_for_prompt(file_symbols)
                    symbol_count = sum(len(fs.symbols) for fs in file_symbols.values())
                    logger.info(f"Extracted {symbol_count} symbols from {len(file_symbols)} files")
                except Exception as e:
                    logger.warning(f"Symbol formatting failed: {e}")

        duration_ms = int((time.time() - start_time) * 1000)
        languages = semgrep_client._detect_languages(state.get('files', []))

        if success:
            findings_list = [f.to_dict() for f in findings]
            prompt_section = semgrep_client.format_findings_for_prompt(findings) if findings else ""

            logger.info(f"SAST completed: {len(findings)} findings in {duration_ms}ms (diff_only={diff_only_mode})")

            return {
                'sast_success': True,
                'sast_findings': findings_list,
                'sast_error': None,
                'sast_prompt_section': prompt_section,
                'sast_duration_ms': duration_ms,
                'languages_detected': languages,
                'symbol_table_prompt': symbol_table_prompt,
            }
        else:
            logger.warning(f"SAST analysis failed: {error}")
            return {
                'sast_success': False,
                'sast_findings': [],
                'sast_error': error,
                'sast_prompt_section': "",
                'sast_duration_ms': duration_ms,
                'languages_detected': languages,
                'symbol_table_prompt': symbol_table_prompt,
            }

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.exception(f"SAST analysis error: {e}")
        return {
            'sast_success': False,
            'sast_findings': [],
            'sast_error': str(e),
            'sast_prompt_section': "",
            'sast_duration_ms': duration_ms,
            'languages_detected': [],
            'symbol_table_prompt': "",
        }


async def run_intent_analysis(state: ReviewState) -> Dict[str, Any]:
    """Analyze code change intent using LLM."""
    logger.info("Running intent analysis...")
    start_time = time.time()

    try:
        # Get AI client based on provider
        provider = state.get('provider', 'glm').lower()
        api_key = state.get('api_key')

        if provider == 'glm':
            ai_client = get_glm_api_client(model=state.get('model'), api_key=api_key)
        elif provider in ('claude', 'anthropic'):
            ai_client = get_claude_api_client(model=state.get('model'), api_key=api_key)
        else:
            raise ValueError(f"Unknown provider: {provider}")

        # Build intent analysis prompt
        prompt = _build_intent_analysis_prompt(state)
        system_prompt = _get_intent_system_prompt()

        # Call AI in thread pool
        success, response_text, error = await asyncio.to_thread(
            ai_client.call_with_retry,
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=4096
        )

        duration_ms = int((time.time() - start_time) * 1000)

        if success:
            # Parse JSON response
            parse_success, parsed_result = parse_json_with_fallbacks(response_text, "Intent analysis")

            if parse_success:
                logger.info(f"Intent analysis completed in {duration_ms}ms")
                return {
                    'intent_success': True,
                    'intent_analysis': parsed_result,
                    'intent_error': None,
                    'intent_duration_ms': duration_ms,
                }
            else:
                logger.warning("Failed to parse intent analysis response")
                return {
                    'intent_success': False,
                    'intent_analysis': {},
                    'intent_error': "Failed to parse intent analysis response",
                    'intent_duration_ms': duration_ms,
                }
        else:
            logger.warning(f"Intent analysis failed: {error}")
            return {
                'intent_success': False,
                'intent_analysis': {},
                'intent_error': error,
                'intent_duration_ms': duration_ms,
            }

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.exception(f"Intent analysis error: {e}")
        return {
            'intent_success': False,
            'intent_analysis': {},
            'intent_error': str(e),
            'intent_duration_ms': duration_ms,
        }


def _get_intent_system_prompt() -> str:
    """Get system prompt for intent analysis."""
    return """You are an expert software architect analyzing code changes to understand their intent and purpose.

Your task is to:
1. Understand WHAT the code change is trying to achieve (the goal/purpose)
2. Analyze HOW it's being implemented (the approach)
3. Identify any gaps between intent and implementation
4. Consider architectural implications

Focus on understanding the "why" behind the changes, not just the "what".
Provide your analysis in structured JSON format."""


def _build_intent_analysis_prompt(state: ReviewState) -> str:
    """Build prompt for intent analysis with size limits."""
    pr_info = state.get('pr_context', {})
    context = state.get('extracted_context', {})

    # Total budget for the prompt (leave room for response)
    max_prompt_size = 60000
    current_size = 0

    # Build context sections with budget tracking
    context_section = ""
    if context:
        # Repository structure (small, always include)
        repo_struct = context.get('repo_structure', {})
        if repo_struct and repo_struct.get('tree_string'):
            struct_text = f"\n## Repository Structure\n```\n{repo_struct['tree_string'][:1500]}\n```\n"
            context_section += struct_text
            current_size += len(struct_text)

        # Changed files with full content (budget: 40% of remaining)
        changed_files = context.get('changed_files', [])
        if changed_files:
            files_budget = int((max_prompt_size - current_size) * 0.4)
            context_section += "\n## Changed Files (Full Content)\n"
            current_size += 35

            max_files = min(len(changed_files), 5)
            per_file_budget = files_budget // max(max_files, 1)

            for f in changed_files[:max_files]:
                file_limit = min(per_file_budget, 8000)
                # Use content_for_prompt if available (truncated), fall back to content
                file_content = f.get('content_for_prompt', f.get('content', ''))
                content = file_content[:file_limit] if len(file_content) > file_limit else file_content
                file_text = f"\n### {f['path']}\n```{f['language']}\n{content}\n```\n"
                context_section += file_text
                current_size += len(file_text)

        # Related files (budget: 15% of remaining, if space allows)
        related_files = context.get('related_files', [])
        remaining_for_related = max_prompt_size - current_size - 20000  # Reserve for diff
        if related_files and remaining_for_related > 2000:
            context_section += "\n## Related Context Files\n"
            current_size += 30

            max_related = min(len(related_files), 2)
            per_file_limit = min(remaining_for_related // max(max_related, 1), 3000)

            for f in related_files[:max_related]:
                content = f['content'][:per_file_limit] if len(f['content']) > per_file_limit else f['content']
                file_text = f"\n### {f['path']}\n```{f['language']}\n{content}\n```\n"
                context_section += file_text
                current_size += len(file_text)

        # NEW: Diff-imported files (HIGH PRIORITY - newly added imports in this PR)
        diff_imported_files = context.get('diff_imported_files', [])
        remaining_for_imports = max_prompt_size - current_size - 15000  # Reserve for diff
        if diff_imported_files and remaining_for_imports > 3000:
            context_section += "\n## Newly Imported Files (Cross-File Analysis)\n"
            context_section += "**IMPORTANT: These files are NEWLY IMPORTED in this PR.**\n"
            context_section += "**Check if the usage of these components/functions is correct (props, signatures, types).**\n\n"
            current_size += 180

            max_imports = min(len(diff_imported_files), 5)
            per_file_limit = min(remaining_for_imports // max(max_imports, 1), 6000)

            for f in diff_imported_files[:max_imports]:
                content = f['content'][:per_file_limit] if len(f['content']) > per_file_limit else f['content']
                file_text = f"\n### {f['path']}\n```{f['language']}\n{content}\n```\n"
                context_section += file_text
                current_size += len(file_text)

    # Calculate remaining budget for diff
    diff_budget = max(max_prompt_size - current_size - 2000, 10000)
    diff_content = state.get('diff_content', '')
    if len(diff_content) > diff_budget:
        diff_content = diff_content[:diff_budget] + "\n... [diff truncated]"

    # Truncate description if too long
    description = pr_info.get('description') or 'No description provided'
    if len(description) > 1000:
        description = description[:1000] + "... [truncated]"

    return f"""Analyze the following Pull Request to understand its intent and implementation quality.

## Pull Request Information
- Repository: {pr_info.get('repo_name', 'unknown')}
- PR #{pr_info.get('pr_number', 'unknown')}
- Title: {pr_info.get('title', 'unknown')}
- Author: {pr_info.get('author', 'unknown')}
- Description: {description}
- Branch: {pr_info.get('head_branch', 'unknown')} → {pr_info.get('base_branch', 'unknown')}

{context_section}

## Code Changes (Diff)
```diff
{diff_content}
```

Analyze this PR and provide your assessment in the following JSON format:
{{
  "purpose": "What is this PR trying to achieve? What problem is it solving?",
  "implementation_approach": "How is the solution being implemented? What patterns/techniques are used?",
  "key_changes": [
    "List of main changes being made"
  ],
  "potential_issues": [
    "Issues identified from analyzing the intent vs implementation"
  ],
  "missing_considerations": [
    "Things that might be missing or overlooked"
  ],
  "architectural_impact": "How does this change affect the overall system architecture?",
  "confidence": 0.85
}}

Focus on:
1. Understanding the developer's intent from the PR title, description, and code
2. Evaluating if the implementation matches the stated intent
3. Identifying gaps or inconsistencies
4. Considering broader architectural implications
5. Suggesting improvements based on intent understanding

Respond with ONLY the JSON object, no additional text."""


def combine_analysis_results(state: ReviewState) -> Dict[str, Any]:
    """Combine SAST and Intent Analysis results into final prompt."""
    logger.info("Combining analysis results...")

    sections = []

    # Add context section
    if state.get('context_prompt_section'):
        sections.append(state['context_prompt_section'])

    # Add SAST results section
    if state.get('sast_success') and state.get('sast_prompt_section'):
        sections.append("\n---\n## Static Analysis (SAST) Findings\n")
        sections.append(state['sast_prompt_section'])
        sections.append(f"\n*SAST completed in {state.get('sast_duration_ms', 0)}ms*\n")
    elif state.get('sast_error'):
        sections.append(f"\n---\n## SAST Analysis\n⚠️ SAST analysis failed: {state['sast_error']}\n")

    # Add Symbol Table for cross-file validation
    if state.get('symbol_table_prompt'):
        sections.append("\n---\n")
        sections.append(state['symbol_table_prompt'])

    # Add Intent Analysis results section
    if state.get('intent_success') and state.get('intent_analysis'):
        intent = state['intent_analysis']
        sections.append("\n---\n## Intent Analysis\n")
        sections.append(f"\n### Purpose\n{intent.get('purpose', 'Not determined')}\n")
        sections.append(f"\n### Implementation Approach\n{intent.get('implementation_approach', 'Not analyzed')}\n")

        if intent.get('key_changes'):
            sections.append("\n### Key Changes\n")
            for change in intent['key_changes']:
                sections.append(f"- {change}\n")

        if intent.get('potential_issues'):
            sections.append("\n### Potential Issues (from Intent Analysis)\n")
            for issue in intent['potential_issues']:
                sections.append(f"- ⚠️ {issue}\n")

        if intent.get('missing_considerations'):
            sections.append("\n### Missing Considerations\n")
            for consideration in intent['missing_considerations']:
                sections.append(f"- 💡 {consideration}\n")

        if intent.get('architectural_impact'):
            sections.append(f"\n### Architectural Impact\n{intent['architectural_impact']}\n")

        confidence = intent.get('confidence', 0)
        sections.append(f"\n*Intent Analysis Confidence: {confidence:.0%}*\n")
        sections.append(f"*Intent Analysis completed in {state.get('intent_duration_ms', 0)}ms*\n")

    elif state.get('intent_error'):
        sections.append(f"\n---\n## Intent Analysis\n⚠️ Intent analysis failed: {state['intent_error']}\n")

    combined_prompt = "".join(sections)
    logger.info(f"Combined prompt length: {len(combined_prompt)} chars")

    return {'combined_prompt': combined_prompt}


def should_continue_after_fetch(state: ReviewState) -> str:
    """Determine if workflow should continue after fetching PR data."""
    if state.get('workflow_error'):
        return "error"
    return "continue"


# ============ Workflow Builder ============

def create_review_workflow() -> StateGraph:
    """Create the LangGraph workflow for code review.

    Workflow structure with PARALLEL execution:
    1. fetch_pr_data: Get PR info and extended context
    2. PARALLEL (fan-out from fetch_pr_data):
       - run_sast_analysis: Static code analysis
       - run_intent_analysis: Intent understanding with LLM
    3. combine_results: Merge all analysis for final review (fan-in)

    Returns:
        Compiled StateGraph workflow
    """
    workflow = StateGraph(ReviewState)

    # Add nodes
    workflow.add_node("fetch_pr_data", fetch_pr_data)
    workflow.add_node("run_sast_analysis", run_sast_analysis)
    workflow.add_node("run_intent_analysis", run_intent_analysis)
    workflow.add_node("combine_results", combine_analysis_results)

    # Set entry point
    workflow.set_entry_point("fetch_pr_data")

    # Conditional routing after fetch - check for errors before parallel execution
    workflow.add_conditional_edges(
        "fetch_pr_data",
        should_continue_after_fetch,
        {
            "continue": "run_sast_analysis",  # This triggers SAST
            "error": END
        }
    )

    # Add second edge from fetch_pr_data to run_intent_analysis for parallel fan-out
    # When fetch completes successfully, BOTH edges are followed in parallel
    workflow.add_edge("fetch_pr_data", "run_intent_analysis")

    # Fan-in: Both analysis nodes converge to combine_results
    # combine_results will wait for BOTH nodes to complete before executing
    workflow.add_edge("run_sast_analysis", "combine_results")
    workflow.add_edge("run_intent_analysis", "combine_results")

    # Combine leads to end
    workflow.add_edge("combine_results", END)

    return workflow.compile()


async def run_review_workflow(
    repo_owner: str,
    repo_name: str,
    pr_number: int,
    provider: str = "glm",
    model: Optional[str] = None,
    github_token: Optional[str] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """Run the complete review workflow.

    Args:
        repo_owner: Repository owner
        repo_name: Repository name
        pr_number: PR number
        provider: AI provider ('glm' or 'anthropic')
        model: Optional model override
        github_token: GitHub API token
        api_key: AI provider API key

    Returns:
        Final workflow state with all analysis results
    """
    logger.info(f"Starting review workflow for {repo_owner}/{repo_name}#{pr_number}")
    logger.debug(f"Workflow input params: repo_owner={repo_owner!r}, repo_name={repo_name!r}, pr_number={pr_number!r}")

    # Initialize state with all required fields
    initial_state: ReviewState = {
        'repo_owner': repo_owner,
        'repo_name': repo_name,
        'pr_number': pr_number,
        'provider': provider,
        'model': model,
        'github_token': github_token,
        'api_key': api_key,
        'pr_info': {},
        'diff_content': '',
        'files': [],
        'pr_context': {},
        'extracted_context': None,
        'context_prompt_section': '',
        'sast_success': False,
        'sast_findings': [],
        'sast_error': None,
        'sast_prompt_section': '',
        'sast_duration_ms': 0,
        'languages_detected': [],
        'symbol_table_prompt': '',
        'intent_success': False,
        'intent_analysis': {},
        'intent_error': None,
        'intent_duration_ms': 0,
        'combined_prompt': '',
        'workflow_error': None
    }

    logger.debug(f"Initial state created: repo_owner={initial_state['repo_owner']!r}, repo_name={initial_state['repo_name']!r}, pr_number={initial_state['pr_number']!r}")

    # Create and run workflow
    workflow = create_review_workflow()

    # Run the workflow
    logger.debug("Invoking workflow with initial state...")
    final_state = await workflow.ainvoke(initial_state)

    logger.info("Review workflow completed")

    return final_state
