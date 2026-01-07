"""Code review API routes."""

import time
import json
import os
import asyncio
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException
from typing import Optional, Tuple, Dict, Any, List

from api.models.schemas import (
    StartReviewRequest,
    ReviewResponse,
    CodeReviewResult,
    PullRequestDetail,
    PostCommentRequest,
    PostCommentResponse,
    SastResult,
    SastFinding,
    IntentAnalysisResult,
    ContextExtractionResult,
    ReviewIssue,
)
from client.github_client import GitHubAPIError, get_github_client
from client.glm_api_client import get_glm_api_client
from client.claude_api_client import get_claude_api_client
from client.semgrep_client import get_semgrep_client
from review_engine.review_workflow import run_review_workflow
from api.config_manager import get_config_manager
from utils.logger import get_logger
from utils.paths import get_reviews_dir

logger = get_logger(__name__)
router = APIRouter(prefix="/review", tags=["Code Review"])

# Directory to save review results - uses platform-specific user directory when packaged
REVIEWS_DIR = get_reviews_dir()




def save_review_to_json(
    repo_owner: str,
    repo_name: str,
    pr_number: int,
    review_result: dict,
    pr_info: dict,
    provider: str,
    model: str,
    duration_ms: int
) -> str:
    """Save review result to JSON file.

    Args:
        repo_owner: Repository owner
        repo_name: Repository name
        pr_number: PR number
        review_result: The parsed review result from LLM
        pr_info: PR information
        provider: LLM provider used
        model: Model used
        duration_ms: Time taken for review

    Returns:
        Path to saved JSON file
    """
    # Create reviews directory if not exists
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)

    # Create subdirectory for repo
    repo_dir = REVIEWS_DIR / f"{repo_owner}_{repo_name}"
    repo_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"pr_{pr_number}_{timestamp}.json"
    filepath = repo_dir / filename

    # Build complete review data
    review_data = {
        "metadata": {
            "repo_owner": repo_owner,
            "repo_name": repo_name,
            "repo_full_name": f"{repo_owner}/{repo_name}",
            "pr_number": pr_number,
            "provider": provider,
            "model": model,
            "timestamp": datetime.now().isoformat(),
            "duration_ms": duration_ms,
        },
        "pr_info": pr_info,
        "review": review_result,
    }

    # Save to file
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(review_data, f, ensure_ascii=False, indent=2)

    logger.info(f"Review saved to {filepath}")
    return str(filepath)


async def _perform_ai_review(
    ai_client,
    workflow_state: Dict[str, Any],
    attempt: int = 1
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str], CodeReviewResult]:
    """Perform AI code review and parse results.

    Args:
        ai_client: The AI client (GLM or Claude)
        workflow_state: The workflow state containing diff and context
        attempt: Current attempt number (for logging)

    Returns:
        Tuple of (success, raw_result, error, parsed_review)
    """
    combined_prompt = workflow_state.get('combined_prompt', '')

    # Add retry hint to prompt if this is a retry attempt
    if attempt > 1:
        retry_hint = f"\n\n**IMPORTANT (Attempt {attempt})**: Previous analysis found no issues. Since this PR is known to have problems, please analyze MORE CAREFULLY. Look for:\n"
        retry_hint += "- Subtle bugs or logic errors\n"
        retry_hint += "- Missing error handling\n"
        retry_hint += "- Security vulnerabilities\n"
        retry_hint += "- Performance issues\n"
        retry_hint += "- Code style/best practice violations\n"
        retry_hint += "- Missing edge case handling\n"
        retry_hint += "- Incorrect API usage\n"
        retry_hint += "- Type mismatches or missing type checks\n"
        retry_hint += "- Resource leaks or cleanup issues\n"
        retry_hint += "- Concurrency/race condition issues\n"
        retry_hint += "\nYou MUST find at least one issue. Do not say the code is perfect.\n"

        if combined_prompt:
            combined_prompt = retry_hint + combined_prompt
        else:
            combined_prompt = retry_hint

    # Perform code review
    success, result, error = await asyncio.to_thread(
        ai_client.review_code,
        diff_content=workflow_state.get('diff_content', ''),
        pr_context=workflow_state.get('pr_context', {}),
        sast_findings=combined_prompt if combined_prompt else None
    )

    if not success:
        return False, None, error, CodeReviewResult(
            summary="Review failed",
            overall_assessment="COMMENT",
            score=0
        )

    # Parse review result
    try:
        review = CodeReviewResult(
            summary=result.get('summary', 'Review completed'),
            overall_assessment=result.get('overall_assessment', 'COMMENT'),
            score=result.get('score', 5),
            issues=[],
            positive_feedback=result.get('positive_feedback', []),
            suggestions=result.get('suggestions', []),
            raw_review=result.get('raw_review')
        )

        # Parse issues if present
        if 'issues' in result and isinstance(result['issues'], list):
            for issue in result['issues']:
                if isinstance(issue, dict):
                    review.issues.append(ReviewIssue(
                        severity=issue.get('severity', 'LOW'),
                        type=issue.get('type', 'best_practice'),
                        file=issue.get('file', 'unknown'),
                        line=issue.get('line'),
                        end_line=issue.get('end_line'),
                        description=issue.get('description', ''),
                        suggestion=issue.get('suggestion'),
                        suggested_change=issue.get('suggested_change')
                    ))

        return True, result, None, review

    except Exception as e:
        logger.warning(f"Error parsing review result: {e}")
        return True, result, None, CodeReviewResult(
            summary="Review completed with parsing issues",
            overall_assessment="COMMENT",
            score=5,
            raw_review=str(result)
        )


@router.post("/start", response_model=ReviewResponse)
async def start_review(request: StartReviewRequest) -> ReviewResponse:
    """Start a code review for a pull request using LangGraph workflow.

    The workflow includes:
    1. Fetch PR data and extract extended context (full file content, repo structure)
    2. Run SAST analysis with Semgrep (parallel)
    3. Run Intent Analysis with LLM (parallel)
    4. Combine all results for final AI code review

    Args:
        request: Review request with repo owner, name, PR number, and provider preference

    Returns:
        ReviewResponse with review results or error
    """
    start_time = time.time()
    config = get_config_manager()

    try:
        # Validate tokens before starting workflow (thread-safe access)
        github_token = config.get_github_token()
        if not github_token:
            return ReviewResponse(
                success=False,
                error="GitHub token not configured. Please set your GitHub token in settings."
            )

        api_key = None
        if request.provider.lower() == 'glm':
            api_key = config.get_api_key('glm')
            if not api_key:
                return ReviewResponse(
                    success=False,
                    error="GLM API key not configured. Please set your GLM API key in settings."
                )
        elif request.provider.lower() in ('claude', 'anthropic'):
            api_key = config.get_api_key('anthropic')
            if not api_key:
                return ReviewResponse(
                    success=False,
                    error="Claude API key not configured. Please set your Anthropic API key in settings."
                )
        else:
            return ReviewResponse(
                success=False,
                error=f"Unknown provider: {request.provider}. Supported: glm, claude"
            )

        # Run the LangGraph workflow
        logger.info(f"Starting review workflow for {request.repo_owner}/{request.repo_name}#{request.pr_number}")

        workflow_state = await run_review_workflow(
            repo_owner=request.repo_owner,
            repo_name=request.repo_name,
            pr_number=request.pr_number,
            provider=request.provider,
            model=request.model,
            github_token=github_token,
            api_key=api_key
        )

        # Check for workflow errors
        if workflow_state.get('workflow_error'):
            return ReviewResponse(
                success=False,
                error=workflow_state['workflow_error'],
                duration_ms=int((time.time() - start_time) * 1000)
            )

        # Extract PR info
        pr_info = None
        if workflow_state.get('pr_info'):
            pr_info = PullRequestDetail(**workflow_state['pr_info'])

        # Build SAST result
        sast_result = None
        if request.enable_sast:
            sast_result = SastResult(
                success=workflow_state.get('sast_success', False),
                findings=[SastFinding(**f) for f in workflow_state.get('sast_findings', [])],
                error=workflow_state.get('sast_error'),
                tool="semgrep",
                duration_ms=workflow_state.get('sast_duration_ms', 0),
                languages_detected=workflow_state.get('languages_detected', [])
            )

        # Build Intent Analysis result
        intent_result = None
        if request.enable_intent_analysis:
            intent_data = workflow_state.get('intent_analysis', {})
            intent_result = IntentAnalysisResult(
                success=workflow_state.get('intent_success', False),
                purpose=intent_data.get('purpose', ''),
                implementation_approach=intent_data.get('implementation_approach', ''),
                key_changes=intent_data.get('key_changes', []),
                potential_issues=intent_data.get('potential_issues', []),
                missing_considerations=intent_data.get('missing_considerations', []),
                architectural_impact=intent_data.get('architectural_impact', ''),
                confidence=intent_data.get('confidence', 0.0),
                error=workflow_state.get('intent_error'),
                duration_ms=workflow_state.get('intent_duration_ms', 0)
            )

        # Build Context Extraction result
        context_result = None
        if request.enable_context_extraction:
            ctx = workflow_state.get('extracted_context', {})
            if ctx:
                # Handle None repo_structure (e.g., in diff-only mode)
                repo_struct = ctx.get('repo_structure') or {}
                context_result = ContextExtractionResult(
                    success=True,
                    changed_files_count=len(ctx.get('changed_files', [])),
                    related_files_count=len(ctx.get('related_files', [])),
                    repo_structure_depth=3,  # Default depth used
                    languages_detected=repo_struct.get('languages', []) if isinstance(repo_struct, dict) else []
                )

        # Now perform the final AI code review with all the enriched context
        # Use retry logic if enabled and no issues found
        logger.info(f"Starting final AI code review with {request.provider}")

        # Get AI client
        if request.provider.lower() == 'glm':
            ai_client = get_glm_api_client(model=request.model, api_key=api_key)
        else:
            ai_client = get_claude_api_client(model=request.model, api_key=api_key)

        # Retry loop: keep trying until issues are found or max retries reached
        # If no issues found after all retries, accept that the code is clean
        max_attempts = request.max_retries if request.retry_until_issues_found else 1
        attempt = 0
        review = None
        result = None
        all_attempts_results = []  # Store results from all attempts

        while attempt < max_attempts:
            attempt += 1
            logger.info(f"AI review attempt {attempt}/{max_attempts}")

            success, result, error, review = await _perform_ai_review(
                ai_client, workflow_state, attempt
            )

            if not success:
                return ReviewResponse(
                    success=False,
                    error=error,
                    pr_info=pr_info,
                    sast_result=sast_result,
                    intent_analysis=intent_result,
                    context_extraction=context_result,
                    duration_ms=int((time.time() - start_time) * 1000)
                )

            # Store this attempt's result
            all_attempts_results.append({
                'attempt': attempt,
                'issues_count': len(review.issues),
                'score': review.score
            })

            # Check if we found any issues
            issues_found = len(review.issues)
            if issues_found > 0:
                logger.info(f"Found {issues_found} issues on attempt {attempt}")
                break

            # If retry is enabled and no issues found yet
            if request.retry_until_issues_found and attempt < max_attempts:
                logger.warning(f"Attempt {attempt}: No issues found, retrying...")
            elif attempt >= max_attempts:
                logger.info(f"Completed {max_attempts} attempts with no issues found - code appears to be clean")

        # Log retry statistics
        if attempt > 1:
            logger.info(f"Review completed after {attempt} attempts. Results: {all_attempts_results}")

        duration_ms = int((time.time() - start_time) * 1000)

        # Save review to JSON file
        try:
            json_filepath = save_review_to_json(
                repo_owner=request.repo_owner,
                repo_name=request.repo_name,
                pr_number=request.pr_number,
                review_result=result,
                pr_info=workflow_state.get('pr_info', {}),
                provider=request.provider,
                model=request.model or "default",
                duration_ms=duration_ms
            )
            logger.info(f"Review saved to: {json_filepath}")
        except Exception as e:
            logger.warning(f"Failed to save review to JSON: {e}")

        return ReviewResponse(
            success=True,
            review=review,
            pr_info=pr_info,
            duration_ms=duration_ms,
            sast_result=sast_result,
            intent_analysis=intent_result,
            context_extraction=context_result
        )

    except Exception as e:
        logger.exception(f"Error during code review: {e}")
        return ReviewResponse(
            success=False,
            error=f"Review failed: {str(e)}",
            duration_ms=int((time.time() - start_time) * 1000)
        )


@router.post("/configure")
async def configure_review(
    github_token: Optional[str] = None,
    glm_api_key: Optional[str] = None,
    claude_api_key: Optional[str] = None
) -> dict:
    """Configure API keys for code review."""
    config = get_config_manager()

    configured = []
    if github_token:
        config.set_github_token(github_token)
        configured.append("GitHub")
    if glm_api_key:
        config.set_provider_credentials("glm", glm_api_key)
        configured.append("GLM")
    if claude_api_key:
        config.set_provider_credentials("anthropic", claude_api_key)
        configured.append("Claude")

    return {
        "success": True,
        "configured": configured,
        "message": f"Configured: {', '.join(configured)}" if configured else "No tokens provided"
    }


@router.post("/comment")
async def post_review_comment(request: PostCommentRequest) -> PostCommentResponse:
    """Post review comments to GitHub PR.

    Creates a review with summary comment and inline comments for each issue.
    Inline comments with suggested_change will include GitHub suggestion blocks.

    Args:
        request: Comment request with review data

    Returns:
        PostCommentResponse with result
    """
    try:
        # Get GitHub client with thread-safe token access
        config = get_config_manager()
        github_token = config.get_github_token()
        try:
            github_client = get_github_client(token=github_token)
        except ValueError:
            return PostCommentResponse(
                success=False,
                error="GitHub token not configured. Please set your GitHub token in settings."
            )

        # Get PR files to validate paths
        pr_files = github_client.get_pr_files(
            request.repo_owner,
            request.repo_name,
            request.pr_number
        )
        file_paths = {f['filename'] for f in pr_files}

        # Get PR info for commit SHA
        pr_data = github_client.get_pull_request(
            request.repo_owner,
            request.repo_name,
            request.pr_number
        )
        commit_id = pr_data.get('head_sha')

        # Build summary comment
        assessment_emoji = {
            'APPROVE': '✅',
            'REQUEST_CHANGES': '⚠️',
            'COMMENT': '💬'
        }.get(request.overall_assessment, '💬')

        summary_body = f"""## 🤖 DiffCOT AI Code Review

{request.summary}

| Assessment | Score |
|:-----------|:------|
| {assessment_emoji} **{request.overall_assessment}** | **{request.score}**/10 |

"""

        # Add positive feedback
        if request.positive_feedback:
            summary_body += "### ✅ Positive Aspects\n\n"
            for feedback in request.positive_feedback:
                summary_body += f"- {feedback}\n"
            summary_body += "\n"

        # Add general suggestions
        if request.suggestions:
            summary_body += "### 💡 Suggestions for Improvement\n\n"
            for suggestion in request.suggestions:
                summary_body += f"- {suggestion}\n"
            summary_body += "\n"

        # Add issue count summary
        if request.issues:
            high_count = sum(1 for i in request.issues if i.severity == 'HIGH')
            medium_count = sum(1 for i in request.issues if i.severity == 'MEDIUM')
            low_count = sum(1 for i in request.issues if i.severity == 'LOW')
            summary_body += f"### 🔍 Issues Found: {len(request.issues)}\n\n"
            summary_body += f"- 🔴 High: {high_count}\n"
            summary_body += f"- 🟡 Medium: {medium_count}\n"
            summary_body += f"- 🟢 Low: {low_count}\n\n"
            summary_body += "*See inline comments below for details.*\n\n"

        summary_body += "---\n*Generated by [DiffCOT](https://github.com/your-repo/diffcot) AI Code Review*"

        # Build inline comments
        review_comments = []
        skipped_comments = []

        for issue in request.issues:
            # Skip if file not in PR
            if issue.file not in file_paths:
                skipped_comments.append(f"{issue.file} (not in PR)")
                continue

            # Skip if no line number
            if not issue.line:
                skipped_comments.append(f"{issue.file} (no line number)")
                continue

            # Parse line number (handle string ranges like "42-45")
            line_num = issue.line
            start_line_num = None

            if isinstance(line_num, str):
                if '-' in line_num:
                    parts = line_num.split('-')
                    start_line_num = int(parts[0])
                    line_num = int(parts[1])
                else:
                    line_num = int(line_num)

            # Handle end_line for multi-line comments
            if issue.end_line and not start_line_num:
                end_line = issue.end_line
                if isinstance(end_line, str):
                    end_line = int(end_line)
                start_line_num = line_num
                line_num = end_line

            # Build comment body
            severity_emoji = {'HIGH': '🔴', 'MEDIUM': '🟡', 'LOW': '🟢'}.get(issue.severity, '⚪')
            comment_body = f"**{severity_emoji} {issue.severity}** | `{issue.type}`\n\n"
            comment_body += f"{issue.description}\n\n"

            if issue.suggestion:
                comment_body += f"💡 **Suggestion:** {issue.suggestion}\n\n"

            # Add GitHub suggestion block if suggested_change is provided
            if issue.suggested_change:
                comment_body += github_client.format_suggested_change(issue.suggested_change)

            # Build comment data
            comment_data = {
                "path": issue.file,
                "line": line_num,
                "side": "RIGHT",
                "body": comment_body
            }

            if start_line_num and start_line_num != line_num:
                comment_data["start_line"] = start_line_num
                comment_data["start_side"] = "RIGHT"

            review_comments.append(comment_data)

        # Create the review with all comments
        try:
            review_event = "COMMENT"  # Always use COMMENT for bot reviews
            # Note: Using APPROVE or REQUEST_CHANGES requires write permissions

            review_result = github_client.create_pr_review(
                owner=request.repo_owner,
                repo=request.repo_name,
                pr_number=request.pr_number,
                body=summary_body,
                event=review_event,
                comments=review_comments if review_comments else None,
                commit_id=commit_id
            )

            review_url = review_result.get('html_url', '')
            review_id = review_result.get('id')

            logger.info(f"Successfully posted review to {request.repo_owner}/{request.repo_name}#{request.pr_number}")

            return PostCommentResponse(
                success=True,
                review_id=review_id,
                comment_count=len(review_comments),
                url=review_url
            )

        except GitHubAPIError as e:
            # If review creation fails (e.g., line not in diff), try posting comments individually
            logger.warning(f"Failed to create review, trying individual comments: {e}")

            successful_comments = 0
            for comment in review_comments:
                try:
                    github_client.create_pr_comment(
                        owner=request.repo_owner,
                        repo=request.repo_name,
                        pr_number=request.pr_number,
                        body=comment['body'],
                        path=comment['path'],
                        line=comment['line'],
                        commit_id=commit_id,
                        side=comment.get('side', 'RIGHT'),
                        start_line=comment.get('start_line'),
                        start_side=comment.get('start_side')
                    )
                    successful_comments += 1
                except GitHubAPIError as ce:
                    logger.warning(f"Failed to create comment on {comment['path']}:{comment['line']}: {ce}")

            return PostCommentResponse(
                success=successful_comments > 0,
                comment_count=successful_comments,
                error=f"Partial success: {successful_comments}/{len(review_comments)} comments posted" if successful_comments < len(review_comments) else None
            )

    except Exception as e:
        logger.exception(f"Error posting review comments: {e}")
        return PostCommentResponse(
            success=False,
            error=f"Failed to post comments: {str(e)}"
        )
