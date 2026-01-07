import React, { useState, useEffect } from 'react';
import { X, Eye, EyeOff, ChevronDown, ChevronUp } from 'lucide-react';
import clsx from 'clsx';

interface ProviderConfig {
  provider: string;
  displayName: string;
  isEnabled: boolean;
  apiKey: string;
  baseURL: string;
  defaultBaseURL: string;
  requiresAPIKey: boolean;
  iconName: string;
  selectedChatModel?: string;
  chatModels?: string[];
}

interface SettingsData {
  providers: ProviderConfig[];
  githubToken?: string;
}

interface SettingsProps {
  isOpen: boolean;
  onClose: () => void;
}

// Default provider configurations - Only GLM and Claude for code review
const defaultProviders: ProviderConfig[] = [
  {
    provider: 'glm',
    displayName: 'GLM (智谱AI)',
    isEnabled: false,
    apiKey: '',
    baseURL: 'https://open.bigmodel.cn/api/paas/v4/',
    defaultBaseURL: 'https://open.bigmodel.cn/api/paas/v4/',
    requiresAPIKey: true,
    iconName: '🌟',
    chatModels: ['glm-4.6'],
  },
  {
    provider: 'anthropic',
    displayName: 'Claude',
    isEnabled: false,
    apiKey: '',
    baseURL: 'https://api.anthropic.com',
    defaultBaseURL: 'https://api.anthropic.com',
    requiresAPIKey: true,
    iconName: '🧠',
    chatModels: ['claude-opus-4-5-20251101'],
  },
];

const API_BASE_URL = 'http://127.0.0.1:8765/api';

export const Settings: React.FC<SettingsProps> = ({ isOpen, onClose }) => {
  const [settings, setSettings] = useState<SettingsData>(getDefaultSettings());
  const [isLoading, setIsLoading] = useState(true);
  const [saveTimeout, setSaveTimeout] = useState<ReturnType<typeof setTimeout> | null>(null);

  function getDefaultSettings(): SettingsData {
    return {
      providers: defaultProviders,
      githubToken: '',
    };
  }

  // Load settings from backend on mount
  useEffect(() => {
    const loadSettings = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/settings`);
        if (response.ok) {
          const data = await response.json();
          // Merge with defaults to get model arrays and icons
          const mergedProviders = data.providers.map((backendProvider: ProviderConfig) => {
            const defaultProvider = defaultProviders.find(d => d.provider === backendProvider.provider);
            if (defaultProvider) {
              return {
                ...defaultProvider,
                isEnabled: backendProvider.isEnabled,
                apiKey: backendProvider.apiKey || '',
                baseURL: backendProvider.baseURL || defaultProvider.baseURL || '',
                selectedChatModel: backendProvider.selectedChatModel,
              };
            }
            return backendProvider;
          });

          // Add any missing providers from defaults
          for (const defaultProvider of defaultProviders) {
            if (!mergedProviders.find((p: ProviderConfig) => p.provider === defaultProvider.provider)) {
              mergedProviders.push(defaultProvider);
            }
          }

          setSettings({
            providers: mergedProviders,
            githubToken: data.github_token || '',
          });
        }
      } catch (error) {
        console.error('Failed to load settings from backend:', error);
      } finally {
        setIsLoading(false);
      }
    };

    if (isOpen) {
      loadSettings();
    }
  }, [isOpen]);

  // Debounced save to backend
  const saveToBackend = async (newSettings: SettingsData) => {
    try {
      const payload = {
        providers: newSettings.providers.map(p => ({
          provider: p.provider,
          displayName: p.displayName,
          isEnabled: p.isEnabled,
          apiKey: p.apiKey,
          baseURL: p.baseURL,
          selectedChatModel: p.selectedChatModel,
        })),
        github_token: newSettings.githubToken,
      };

      await fetch(`${API_BASE_URL}/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } catch (error) {
      console.error('Failed to save settings:', error);
    }
  };

  // Save settings with debounce
  useEffect(() => {
    if (isLoading) return;

    if (saveTimeout) {
      clearTimeout(saveTimeout);
    }

    const timeout = setTimeout(() => {
      saveToBackend(settings);
    }, 500);

    setSaveTimeout(timeout);

    return () => {
      if (saveTimeout) {
        clearTimeout(saveTimeout);
      }
    };
  }, [settings, isLoading]);

  const updateProvider = (index: number, updates: Partial<ProviderConfig>) => {
    setSettings(prev => ({
      ...prev,
      providers: prev.providers.map((p, i) =>
        i === index ? { ...p, ...updates } : p
      ),
    }));
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div
        className="w-[500px] h-[550px] rounded-xl shadow-2xl overflow-hidden flex flex-col"
        style={{
          backgroundColor: 'var(--color-bg-window)',
          border: '1px solid var(--color-divider)',
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3">
          <h2
            className="text-lg font-semibold"
            style={{ color: 'var(--color-text-primary)' }}
          >
            Model Provider Settings
          </h2>
          <button
            onClick={onClose}
            className="p-1 rounded-full transition-colors"
            style={{ color: 'var(--color-text-secondary)' }}
            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--color-hover)'}
            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Divider */}
        <div className="h-px" style={{ backgroundColor: 'var(--color-divider)' }} />

        {/* Content - GitHub Token and Providers Settings */}
        <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
          {/* GitHub Token Section */}
          <GitHubTokenSection
            token={settings.githubToken || ''}
            onUpdate={(token) => setSettings(prev => ({ ...prev, githubToken: token }))}
          />

          {/* Divider */}
          <div className="h-px my-4" style={{ backgroundColor: 'var(--color-divider)' }} />

          {/* Providers Section */}
          <ProvidersSettings
            providers={settings.providers}
            onUpdate={updateProvider}
          />
        </div>
      </div>
    </div>
  );
};

// GitHub Token Section Component
interface GitHubTokenSectionProps {
  token: string;
  onUpdate: (token: string) => void;
}

const GitHubTokenSection: React.FC<GitHubTokenSectionProps> = ({ token, onUpdate }) => {
  const [showToken, setShowToken] = useState(false);

  return (
    <div className="space-y-4">
      <div>
        <h3
          className="font-semibold"
          style={{ color: 'var(--color-text-primary)' }}
        >
          GitHub Configuration
        </h3>
        <p
          className="text-sm mt-1"
          style={{ color: 'var(--color-text-secondary)' }}
        >
          Configure GitHub access token for fetching repository and PR data
        </p>
      </div>

      <div
        className="p-4 rounded-xl space-y-3"
        style={{ backgroundColor: 'var(--color-bg-input)' }}
      >
        <div className="flex items-center gap-3">
          <span className="text-xl">🔗</span>
          <span
            className="text-sm font-medium"
            style={{ color: 'var(--color-text-primary)' }}
          >
            GitHub Personal Access Token
          </span>
        </div>

        <div className="space-y-1">
          <div className="flex gap-2">
            <input
              type={showToken ? 'text' : 'password'}
              value={token}
              onChange={(e) => onUpdate(e.target.value)}
              placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
              className="flex-1 px-3 py-2 rounded-lg text-sm outline-none"
              style={{
                backgroundColor: 'var(--color-bg-window)',
                border: '1px solid var(--color-divider)',
                color: 'var(--color-text-primary)',
              }}
            />
            <button
              onClick={() => setShowToken(!showToken)}
              className="p-2 rounded-lg transition-colors"
              style={{
                backgroundColor: 'var(--color-bg-window)',
                color: 'var(--color-text-secondary)',
              }}
            >
              {showToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
          <p
            className="text-xs"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            Create a token at GitHub → Settings → Developer settings → Personal access tokens
          </p>
        </div>
      </div>
    </div>
  );
};

// Providers Settings Component
interface ProvidersSettingsProps {
  providers: ProviderConfig[];
  onUpdate: (index: number, updates: Partial<ProviderConfig>) => void;
}

const ProvidersSettings: React.FC<ProvidersSettingsProps> = ({ providers, onUpdate }) => {
  const [expandedProvider, setExpandedProvider] = useState<string | null>(null);

  return (
    <div className="space-y-4">
      <div>
        <h3
          className="font-semibold"
          style={{ color: 'var(--color-text-primary)' }}
        >
          Model Providers for Code Review
        </h3>
        <p
          className="text-sm mt-1"
          style={{ color: 'var(--color-text-secondary)' }}
        >
          Configure API keys and base URLs for AI code review providers
        </p>
      </div>

      <div className="space-y-2">
        {providers.map((config, index) => (
          <ProviderConfigRow
            key={config.provider}
            config={config}
            isExpanded={expandedProvider === config.provider}
            onToggleExpand={() =>
              setExpandedProvider(expandedProvider === config.provider ? null : config.provider)
            }
            onUpdate={(updates) => onUpdate(index, updates)}
          />
        ))}
      </div>
    </div>
  );
};

// Provider Config Row Component
interface ProviderConfigRowProps {
  config: ProviderConfig;
  isExpanded: boolean;
  onToggleExpand: () => void;
  onUpdate: (updates: Partial<ProviderConfig>) => void;
}

const ProviderConfigRow: React.FC<ProviderConfigRowProps> = ({
  config,
  isExpanded,
  onToggleExpand,
  onUpdate,
}) => {
  const [showAPIKey, setShowAPIKey] = useState(false);

  return (
    <div className="overflow-hidden rounded-xl">
      {/* Header Row */}
      <div
        className="flex items-center gap-3 p-3"
        style={{ backgroundColor: 'var(--color-bg-input)' }}
      >
        <span className="text-xl w-8 text-center">{config.iconName}</span>
        <span
          className="flex-1 text-sm"
          style={{ color: 'var(--color-text-primary)' }}
        >
          {config.displayName}
        </span>

        {/* Toggle Switch */}
        <label className="relative inline-flex items-center cursor-pointer">
          <input
            type="checkbox"
            checked={config.isEnabled}
            onChange={(e) => onUpdate({ isEnabled: e.target.checked })}
            className="sr-only peer"
          />
          <div
            className="w-9 h-5 rounded-full peer-checked:bg-[var(--color-accent)] transition-colors"
            style={{ backgroundColor: config.isEnabled ? 'var(--color-accent)' : 'var(--color-text-secondary)' }}
          >
            <div
              className={clsx(
                "absolute top-0.5 w-4 h-4 bg-white rounded-full transition-transform",
                config.isEnabled ? "translate-x-4" : "translate-x-0.5"
              )}
            />
          </div>
        </label>

        {/* Expand Button */}
        <button
          onClick={onToggleExpand}
          className="p-1 rounded transition-colors"
          style={{ color: 'var(--color-text-secondary)' }}
        >
          {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>

      {/* Expanded Content */}
      {isExpanded && (
        <div
          className="p-4 space-y-4"
          style={{ backgroundColor: 'var(--color-bg-input)', opacity: 0.7 }}
        >
          {/* API Key */}
          {config.requiresAPIKey && (
            <div className="space-y-1">
              <label
                className="text-xs"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                API Key
              </label>
              <div className="flex gap-2">
                <input
                  type={showAPIKey ? 'text' : 'password'}
                  value={config.apiKey}
                  onChange={(e) => onUpdate({ apiKey: e.target.value })}
                  placeholder="Enter API key"
                  className="flex-1 px-3 py-2 rounded-lg text-sm outline-none"
                  style={{
                    backgroundColor: 'var(--color-bg-window)',
                    border: '1px solid var(--color-divider)',
                    color: 'var(--color-text-primary)',
                  }}
                />
                <button
                  onClick={() => setShowAPIKey(!showAPIKey)}
                  className="p-2 rounded-lg transition-colors"
                  style={{
                    backgroundColor: 'var(--color-bg-window)',
                    color: 'var(--color-text-secondary)',
                  }}
                >
                  {showAPIKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
          )}

          {/* Base URL */}
          <div className="space-y-1">
            <label
              className="text-xs"
              style={{ color: 'var(--color-text-secondary)' }}
            >
              Base URL
            </label>
            <input
              type="text"
              value={config.baseURL}
              onChange={(e) => onUpdate({ baseURL: e.target.value })}
              placeholder="API endpoint"
              className="w-full px-3 py-2 rounded-lg text-sm outline-none"
              style={{
                backgroundColor: 'var(--color-bg-window)',
                border: '1px solid var(--color-divider)',
                color: 'var(--color-text-primary)',
              }}
            />
            {config.defaultBaseURL && (
              <p
                className="text-xs"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                Default: {config.defaultBaseURL}
              </p>
            )}
          </div>

          {/* Model Selection */}
          <div className="space-y-1">
            <label
              className="text-xs"
              style={{ color: 'var(--color-text-secondary)' }}
            >
              Code Review Model
            </label>
            <select
              value={config.selectedChatModel || ''}
              onChange={(e) => onUpdate({ selectedChatModel: e.target.value })}
              className="w-full px-3 py-2 rounded-lg text-sm outline-none cursor-pointer"
              style={{
                backgroundColor: 'var(--color-bg-window)',
                border: '1px solid var(--color-divider)',
                color: 'var(--color-text-primary)',
              }}
            >
              <option value="">Select model</option>
              {config.chatModels?.map((model) => (
                <option key={model} value={model}>{model}</option>
              ))}
            </select>
          </div>
        </div>
      )}
    </div>
  );
};
