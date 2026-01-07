"""Thread-safe configuration manager for API credentials and settings.

This module provides a centralized, thread-safe way to manage API tokens and settings
across the application, enabling concurrent request handling without race conditions.
Credentials are persisted to SQLite database for persistence across restarts.
"""

import asyncio
import os
import threading
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from copy import deepcopy

from utils.logger import get_logger

logger = get_logger(__name__)

# Credential keys for database storage
CRED_KEY_GITHUB_TOKEN = "github_token"
CRED_KEY_GLM_API_KEY = "glm_api_key"
CRED_KEY_GLM_BASE_URL = "glm_base_url"
CRED_KEY_GLM_MODEL = "glm_model"
CRED_KEY_CLAUDE_API_KEY = "claude_api_key"
CRED_KEY_CLAUDE_BASE_URL = "claude_base_url"
CRED_KEY_CLAUDE_MODEL = "claude_model"


@dataclass
class ProviderCredentials:
    """Credentials for an API provider."""
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    is_enabled: bool = False


@dataclass
class ConfigState:
    """Immutable snapshot of configuration state."""
    github_token: Optional[str] = None
    providers: Dict[str, ProviderCredentials] = field(default_factory=dict)

    def get_provider(self, provider_name: str) -> Optional[ProviderCredentials]:
        """Get credentials for a specific provider."""
        return self.providers.get(provider_name.lower())

    def get_api_key(self, provider_name: str) -> Optional[str]:
        """Get API key for a specific provider."""
        creds = self.get_provider(provider_name)
        return creds.api_key if creds and creds.api_key else None


class ConfigManager:
    """Thread-safe configuration manager.

    Provides atomic read/write access to configuration using locks.
    All public methods are thread-safe and can be called concurrently.
    """

    _instance: Optional['ConfigManager'] = None
    _instance_lock = threading.Lock()

    def __new__(cls) -> 'ConfigManager':
        """Singleton pattern with thread-safe initialization."""
        if cls._instance is None:
            with cls._instance_lock:
                # Double-checked locking
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def __init__(self):
        """Initialize the config manager."""
        if self._initialized:
            return

        self._lock = threading.RLock()  # Reentrant lock for nested calls
        self._async_lock = asyncio.Lock()
        self._state = ConfigState()
        self._db = None  # Lazy initialization to avoid circular imports
        self._load_credentials()
        self._initialized = True
        logger.info("ConfigManager initialized")

    def _get_db(self):
        """Get database instance (lazy initialization)."""
        if self._db is None:
            from api.database import get_database
            self._db = get_database()
        return self._db

    def _load_credentials(self):
        """Load credentials from database first, then fall back to environment variables."""
        try:
            db = self._get_db()
            stored_creds = db.get_all_credentials()
        except Exception as e:
            logger.warning(f"Failed to load credentials from database: {e}")
            stored_creds = {}

        # GitHub token: prefer database, fall back to environment
        github_token = stored_creds.get(CRED_KEY_GITHUB_TOKEN) or os.environ.get("GITHUB_TOKEN")

        # Provider configurations
        providers = {}

        # GLM: prefer database, fall back to environment
        glm_key = stored_creds.get(CRED_KEY_GLM_API_KEY) or os.environ.get("GLM_API_KEY", "")
        glm_base_url = stored_creds.get(CRED_KEY_GLM_BASE_URL) or "https://open.bigmodel.cn/api/paas/v4/"
        glm_model = stored_creds.get(CRED_KEY_GLM_MODEL) or "glm-4.6"
        providers["glm"] = ProviderCredentials(
            api_key=glm_key,
            base_url=glm_base_url,
            model=glm_model,
            is_enabled=bool(glm_key)
        )

        # Claude/Anthropic: prefer database, fall back to environment
        claude_key = stored_creds.get(CRED_KEY_CLAUDE_API_KEY) or os.environ.get("ANTHROPIC_API_KEY", "")
        claude_base_url = stored_creds.get(CRED_KEY_CLAUDE_BASE_URL) or "https://api.anthropic.com"
        claude_model = stored_creds.get(CRED_KEY_CLAUDE_MODEL) or "claude-opus-4-5-20251101"
        providers["anthropic"] = ProviderCredentials(
            api_key=claude_key,
            base_url=claude_base_url,
            model=claude_model,
            is_enabled=bool(claude_key)
        )
        providers["claude"] = providers["anthropic"]  # Alias

        self._state = ConfigState(
            github_token=github_token,
            providers=providers
        )

        # Also update environment variables for clients that read from env
        if github_token:
            os.environ["GITHUB_TOKEN"] = github_token
        if glm_key:
            os.environ["GLM_API_KEY"] = glm_key
        if claude_key:
            os.environ["ANTHROPIC_API_KEY"] = claude_key

        logger.debug(f"Loaded config: github_token={'set' if github_token else 'not set'}, "
                    f"glm={'enabled' if providers['glm'].is_enabled else 'disabled'}, "
                    f"claude={'enabled' if providers['anthropic'].is_enabled else 'disabled'}")

    def get_config(self) -> ConfigState:
        """Get a snapshot of current configuration (thread-safe).

        Returns a deep copy to prevent external modification.
        """
        with self._lock:
            return deepcopy(self._state)

    def get_github_token(self) -> Optional[str]:
        """Get GitHub token (thread-safe)."""
        with self._lock:
            return self._state.github_token

    def get_api_key(self, provider: str) -> Optional[str]:
        """Get API key for a provider (thread-safe)."""
        with self._lock:
            return self._state.get_api_key(provider)

    def get_provider_credentials(self, provider: str) -> Optional[ProviderCredentials]:
        """Get full credentials for a provider (thread-safe)."""
        with self._lock:
            creds = self._state.get_provider(provider)
            return deepcopy(creds) if creds else None

    def set_github_token(self, token: str):
        """Set GitHub token (thread-safe, persisted to database)."""
        with self._lock:
            self._state.github_token = token
            os.environ["GITHUB_TOKEN"] = token
            # Persist to database
            try:
                self._get_db().save_credential(CRED_KEY_GITHUB_TOKEN, token)
            except Exception as e:
                logger.error(f"Failed to persist GitHub token to database: {e}")
            logger.info("GitHub token updated")

    def set_provider_credentials(self, provider: str, api_key: str,
                                  base_url: Optional[str] = None,
                                  model: Optional[str] = None):
        """Set credentials for a provider (thread-safe, persisted to database)."""
        provider_lower = provider.lower()
        with self._lock:
            if provider_lower not in self._state.providers:
                self._state.providers[provider_lower] = ProviderCredentials()

            creds = self._state.providers[provider_lower]
            creds.api_key = api_key
            creds.is_enabled = bool(api_key)

            if base_url:
                creds.base_url = base_url
            if model:
                creds.model = model

            # Update environment variable and persist to database
            try:
                db = self._get_db()
                if provider_lower == "glm":
                    os.environ["GLM_API_KEY"] = api_key
                    db.save_credential(CRED_KEY_GLM_API_KEY, api_key)
                    if base_url:
                        db.save_credential(CRED_KEY_GLM_BASE_URL, base_url)
                    if model:
                        db.save_credential(CRED_KEY_GLM_MODEL, model)
                elif provider_lower in ("anthropic", "claude"):
                    os.environ["ANTHROPIC_API_KEY"] = api_key
                    db.save_credential(CRED_KEY_CLAUDE_API_KEY, api_key)
                    if base_url:
                        db.save_credential(CRED_KEY_CLAUDE_BASE_URL, base_url)
                    if model:
                        db.save_credential(CRED_KEY_CLAUDE_MODEL, model)
                    # Keep both aliases in sync
                    self._state.providers["anthropic"] = creds
                    self._state.providers["claude"] = creds
            except Exception as e:
                logger.error(f"Failed to persist provider credentials to database: {e}")

            logger.info(f"Provider {provider} credentials updated")

    def update_from_settings(self, settings_data: Dict[str, Any]):
        """Update configuration from settings data (thread-safe, persisted to database).

        Args:
            settings_data: Dictionary containing settings with 'providers' list
                           and optional 'github_token'
        """
        with self._lock:
            db = self._get_db()

            # Update GitHub token
            if settings_data.get("github_token"):
                self._state.github_token = settings_data["github_token"]
                os.environ["GITHUB_TOKEN"] = settings_data["github_token"]
                try:
                    db.save_credential(CRED_KEY_GITHUB_TOKEN, settings_data["github_token"])
                except Exception as e:
                    logger.error(f"Failed to persist GitHub token: {e}")

            # Update providers
            for provider in settings_data.get("providers", []):
                provider_name = provider.get("provider", "").lower()
                api_key = provider.get("apiKey", "")

                if provider_name and api_key:
                    if provider_name not in self._state.providers:
                        self._state.providers[provider_name] = ProviderCredentials()

                    creds = self._state.providers[provider_name]
                    creds.api_key = api_key
                    creds.is_enabled = True

                    base_url = provider.get("baseURL")
                    model = provider.get("selectedChatModel")

                    if base_url:
                        creds.base_url = base_url
                    if model:
                        creds.model = model

                    # Update environment and persist to database
                    try:
                        if provider_name == "glm":
                            os.environ["GLM_API_KEY"] = api_key
                            db.save_credential(CRED_KEY_GLM_API_KEY, api_key)
                            if base_url:
                                db.save_credential(CRED_KEY_GLM_BASE_URL, base_url)
                            if model:
                                db.save_credential(CRED_KEY_GLM_MODEL, model)
                        elif provider_name in ("anthropic", "claude"):
                            os.environ["ANTHROPIC_API_KEY"] = api_key
                            db.save_credential(CRED_KEY_CLAUDE_API_KEY, api_key)
                            if base_url:
                                db.save_credential(CRED_KEY_CLAUDE_BASE_URL, base_url)
                            if model:
                                db.save_credential(CRED_KEY_CLAUDE_MODEL, model)
                            self._state.providers["anthropic"] = creds
                            self._state.providers["claude"] = creds
                    except Exception as e:
                        logger.error(f"Failed to persist {provider_name} credentials: {e}")

            logger.info("Configuration updated from settings")

    async def async_get_config(self) -> ConfigState:
        """Async version of get_config for use in async contexts."""
        async with self._async_lock:
            return deepcopy(self._state)

    async def async_update_from_settings(self, settings_data: Dict[str, Any]):
        """Async version of update_from_settings."""
        async with self._async_lock:
            self.update_from_settings(settings_data)


# Global singleton instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get the global ConfigManager instance.

    This is the recommended way to access configuration throughout the application.
    Thread-safe and returns a singleton instance.
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


# Convenience functions for common operations
def get_github_token() -> Optional[str]:
    """Get GitHub token from config manager."""
    return get_config_manager().get_github_token()


def get_api_key(provider: str) -> Optional[str]:
    """Get API key for a provider from config manager."""
    return get_config_manager().get_api_key(provider)
