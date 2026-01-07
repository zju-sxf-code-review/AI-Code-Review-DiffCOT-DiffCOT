"""Settings API routes."""

from fastapi import APIRouter
from typing import Optional
import os

from api.models.schemas import SettingsData, ProviderConfig
from api.config_manager import get_config_manager
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/settings", tags=["Settings"])


def get_default_settings() -> SettingsData:
    """Get default settings configuration."""
    config = get_config_manager()
    glm_creds = config.get_provider_credentials("glm")
    anthropic_creds = config.get_provider_credentials("anthropic")

    return SettingsData(
        providers=[
            ProviderConfig(
                provider="glm",
                displayName="GLM (智谱AI)",
                isEnabled=glm_creds.is_enabled if glm_creds else False,
                apiKey=glm_creds.api_key if glm_creds else "",
                baseURL=glm_creds.base_url if glm_creds else "https://open.bigmodel.cn/api/paas/v4/",
                selectedChatModel=glm_creds.model if glm_creds else "glm-4.6",
            ),
            ProviderConfig(
                provider="anthropic",
                displayName="Claude",
                isEnabled=anthropic_creds.is_enabled if anthropic_creds else False,
                apiKey=anthropic_creds.api_key if anthropic_creds else "",
                baseURL=anthropic_creds.base_url if anthropic_creds else "https://api.anthropic.com",
                selectedChatModel=anthropic_creds.model if anthropic_creds else "claude-opus-4-5-20251101",
            ),
        ],
        github_token=config.get_github_token()
    )


@router.get("", response_model=SettingsData)
async def get_settings() -> SettingsData:
    """Get current settings."""
    return get_default_settings()


@router.put("")
async def update_settings(settings: SettingsData) -> SettingsData:
    """Update settings."""
    config = get_config_manager()

    # Update GitHub token
    if settings.github_token:
        config.set_github_token(settings.github_token)

    # Update provider credentials
    for provider in settings.providers:
        if provider.apiKey:
            config.set_provider_credentials(
                provider=provider.provider,
                api_key=provider.apiKey,
                base_url=provider.baseURL,
                model=provider.selectedChatModel
            )

    logger.info("Settings updated successfully")
    return get_default_settings()
