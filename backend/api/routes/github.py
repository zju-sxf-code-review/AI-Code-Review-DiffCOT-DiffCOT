"""GitHub API routes for repository and PR management."""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional

from api.models.schemas import (
    GitHubRepoRequest,
    GitHubRepo,
    PullRequest,
    PullRequestDetail,
    PRFile,
    PRReviewData,
    PRState,
)
from client.github_client import GitHubClient, GitHubAPIError, get_github_client
from api.config_manager import get_config_manager
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/github", tags=["GitHub"])


def get_client() -> GitHubClient:
    """Get GitHub client with current token (thread-safe)."""
    config = get_config_manager()
    github_token = config.get_github_token()
    try:
        return get_github_client(token=github_token)
    except ValueError as e:
        raise HTTPException(
            status_code=401,
            detail="GitHub token not configured. Please set your GitHub token in settings."
        )


@router.post("/token")
async def set_github_token(token: str) -> dict:
    """Set GitHub token for API access."""
    # Validate token
    try:
        client = GitHubClient(token=token)
        success, error = client.validate_token()
        if not success:
            raise HTTPException(status_code=401, detail=f"Invalid token: {error}")

        # Store token in thread-safe config manager
        config = get_config_manager()
        config.set_github_token(token)
        return {"success": True, "message": "GitHub token configured successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/repos/parse")
async def parse_repo_url(request: GitHubRepoRequest) -> dict:
    """Parse a GitHub repository URL and return owner/repo info."""
    client = get_client()
    owner, repo = client.parse_repo_url(request.url)

    if not owner or not repo:
        raise HTTPException(
            status_code=400,
            detail="Invalid GitHub repository URL"
        )

    return {
        "owner": owner,
        "repo": repo,
        "full_name": f"{owner}/{repo}"
    }


@router.post("/repos", response_model=GitHubRepo)
async def add_repository(request: GitHubRepoRequest) -> GitHubRepo:
    """Add a GitHub repository by URL and fetch its info."""
    logger.info(f"Adding repository: {request.url}")
    client = get_client()

    # Parse URL
    owner, repo = client.parse_repo_url(request.url)
    if not owner or not repo:
        raise HTTPException(
            status_code=400,
            detail="Invalid GitHub repository URL"
        )

    logger.info(f"Parsed repository: {owner}/{repo}")

    try:
        repo_data = client.get_repository(owner, repo)
        logger.info(f"Repository data fetched successfully: {repo_data.get('full_name')}")
        return GitHubRepo(**repo_data)
    except GitHubAPIError as e:
        logger.error(f"GitHub API error: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Error fetching repository: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/repos/{owner}/{repo}", response_model=GitHubRepo)
async def get_repository(owner: str, repo: str) -> GitHubRepo:
    """Get repository information."""
    client = get_client()

    try:
        repo_data = client.get_repository(owner, repo)
        return GitHubRepo(**repo_data)
    except GitHubAPIError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Error fetching repository: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/repos/{owner}/{repo}/pulls", response_model=List[PullRequest])
async def list_pull_requests(
    owner: str,
    repo: str,
    state: PRState = PRState.OPEN,
    per_page: int = 30,
    include_stats: bool = True
) -> List[PullRequest]:
    """List pull requests for a repository."""
    logger.info(f"Listing PRs for {owner}/{repo}, state={state.value}, per_page={per_page}, include_stats={include_stats}")
    client = get_client()

    try:
        prs = client.list_pull_requests(owner, repo, state=state.value, per_page=per_page, include_stats=include_stats)
        logger.info(f"Found {len(prs)} pull requests")
        return [PullRequest(**pr) for pr in prs]
    except GitHubAPIError as e:
        logger.error(f"GitHub API error listing PRs: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Error listing PRs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/repos/{owner}/{repo}/pulls/{pr_number}", response_model=PullRequestDetail)
async def get_pull_request(owner: str, repo: str, pr_number: int) -> PullRequestDetail:
    """Get detailed pull request information."""
    client = get_client()

    try:
        pr_data = client.get_pull_request(owner, repo, pr_number)
        return PullRequestDetail(**pr_data)
    except GitHubAPIError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Error fetching PR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/repos/{owner}/{repo}/pulls/{pr_number}/files", response_model=List[PRFile])
async def get_pull_request_files(owner: str, repo: str, pr_number: int) -> List[PRFile]:
    """Get list of files changed in a pull request."""
    client = get_client()

    try:
        files = client.get_pull_request_files(owner, repo, pr_number)
        return [PRFile(**f) for f in files]
    except GitHubAPIError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Error fetching PR files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/repos/{owner}/{repo}/pulls/{pr_number}/diff")
async def get_pull_request_diff(owner: str, repo: str, pr_number: int) -> dict:
    """Get complete PR diff in unified format."""
    client = get_client()

    try:
        diff = client.get_pull_request_diff(owner, repo, pr_number)
        return {"diff": diff}
    except GitHubAPIError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Error fetching PR diff: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/repos/{owner}/{repo}/pulls/{pr_number}/review-data", response_model=PRReviewData)
async def get_pr_review_data(owner: str, repo: str, pr_number: int) -> PRReviewData:
    """Get comprehensive PR data for code review."""
    client = get_client()

    try:
        review_data = client.get_pr_review_data(owner, repo, pr_number)
        return PRReviewData(
            pr=PullRequestDetail(**review_data['pr']),
            files=[PRFile(**f) for f in review_data['files']],
            diff=review_data['diff'],
            context=review_data['context']
        )
    except GitHubAPIError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Error fetching review data: {e}")
        raise HTTPException(status_code=500, detail=str(e))
