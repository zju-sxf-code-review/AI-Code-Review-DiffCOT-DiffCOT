"""
Constants and configuration values for DiffCOT Code Review.
"""

import os

# API Configuration - Claude
DEFAULT_CLAUDE_MODEL = os.environ.get('CLAUDE_MODEL') or 'claude-opus-4-20250514'
DEFAULT_TIMEOUT_SECONDS = 180  # 3 minutes
DEFAULT_MAX_RETRIES = 3
RATE_LIMIT_BACKOFF_MAX = 30  # Maximum backoff time for rate limits

# API Configuration - GLM
DEFAULT_GLM_MODEL = os.environ.get('GLM_MODEL') or 'glm-4.6'
GLM_API_BASE_URL = os.environ.get('GLM_API_BASE_URL') or 'https://open.bigmodel.cn/api/paas/v4/'

# Token Limits
PROMPT_TOKEN_LIMIT = 16384  # 16k tokens max

# Exit Codes
EXIT_SUCCESS = 0
EXIT_GENERAL_ERROR = 1
EXIT_CONFIGURATION_ERROR = 2

# Subprocess Configuration
SUBPROCESS_TIMEOUT = 1200  # 20 minutes for Code execution

# GitHub API Configuration
GITHUB_API_BASE_URL = 'https://api.github.com'
GITHUB_API_VERSION = '2022-11-28'
