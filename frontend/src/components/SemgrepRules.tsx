import React, { useState, useEffect, useCallback } from 'react';
import { Search, Plus, Trash2, Save, X, AlertCircle, CheckCircle, ChevronLeft } from 'lucide-react';
import {
  listSemgrepRules,
  getSemgrepRuleYaml,
  updateSemgrepRuleYaml,
  deleteSemgrepRule,
  validateSemgrepRuleYaml,
  type SemgrepRuleListItem,
} from '../services/api';

interface SemgrepRulesProps {
  onBack: () => void;
}

// Default template for new rules
const NEW_RULE_TEMPLATE = `id: my-new-rule
languages: [python]
severity: WARNING
message: |
  Description of what this rule detects.

  Explain why this is a problem and how to fix it.
patterns:
  - pattern: |
      # Your pattern here
metadata:
  category: correctness
  technology: [python]
`;

export const SemgrepRules: React.FC<SemgrepRulesProps> = ({ onBack }) => {
  const [rules, setRules] = useState<SemgrepRuleListItem[]>([]);
  const [filteredRules, setFilteredRules] = useState<SemgrepRuleListItem[]>([]);
  const [searchText, setSearchText] = useState('');
  const [selectedRuleId, setSelectedRuleId] = useState<string | null>(null);
  const [isCreatingNew, setIsCreatingNew] = useState(false);
  const [yamlContent, setYamlContent] = useState('');
  const [originalYaml, setOriginalYaml] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [hasChanges, setHasChanges] = useState(false);

  // Load rules list
  const loadRules = useCallback(async () => {
    try {
      setIsLoading(true);
      const rulesList = await listSemgrepRules();
      setRules(rulesList);
      setFilteredRules(rulesList);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load rules');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRules();
  }, [loadRules]);

  // Filter rules based on search
  useEffect(() => {
    if (!searchText) {
      setFilteredRules(rules);
    } else {
      const lower = searchText.toLowerCase();
      setFilteredRules(rules.filter(r => r.id.toLowerCase().includes(lower)));
    }
  }, [searchText, rules]);

  // Load selected rule
  const handleSelectRule = async (ruleId: string) => {
    if (hasChanges && !window.confirm('You have unsaved changes. Discard them?')) {
      return;
    }

    setIsCreatingNew(false);
    setSelectedRuleId(ruleId);
    setError(null);
    setSuccessMessage(null);
    setValidationError(null);

    try {
      const result = await getSemgrepRuleYaml(ruleId);
      setYamlContent(result.yaml);
      setOriginalYaml(result.yaml);
      setHasChanges(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load rule');
    }
  };

  // Handle creating new rule
  const handleNewRule = () => {
    if (hasChanges && !window.confirm('You have unsaved changes. Discard them?')) {
      return;
    }

    setIsCreatingNew(true);
    setSelectedRuleId(null);
    setYamlContent(NEW_RULE_TEMPLATE);
    setOriginalYaml('');
    setHasChanges(true);
    setError(null);
    setSuccessMessage(null);
    setValidationError(null);
  };

  // Handle delete rule
  const handleDeleteRule = async () => {
    if (!selectedRuleId) return;

    if (!window.confirm(`Are you sure you want to delete rule "${selectedRuleId}"?`)) {
      return;
    }

    try {
      await deleteSemgrepRule(selectedRuleId);
      setSuccessMessage('Rule deleted successfully');
      setSelectedRuleId(null);
      setYamlContent('');
      setOriginalYaml('');
      setHasChanges(false);
      await loadRules();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete rule');
    }
  };

  // Handle YAML content change
  const handleYamlChange = (value: string) => {
    setYamlContent(value);
    setHasChanges(value !== originalYaml);
    setValidationError(null);
  };

  // Validate YAML
  const handleValidate = async () => {
    try {
      const result = await validateSemgrepRuleYaml(yamlContent);
      if (result.valid) {
        setValidationError(null);
        setSuccessMessage('YAML is valid');
        setTimeout(() => setSuccessMessage(null), 3000);
      } else {
        setValidationError(result.error || 'Invalid YAML');
      }
    } catch (err) {
      setValidationError(err instanceof Error ? err.message : 'Validation failed');
    }
  };

  // Save rule
  const handleSave = async () => {
    setIsSaving(true);
    setError(null);
    setSuccessMessage(null);

    try {
      // First validate
      const validateResult = await validateSemgrepRuleYaml(yamlContent);
      if (!validateResult.valid) {
        setValidationError(validateResult.error || 'Invalid YAML');
        setIsSaving(false);
        return;
      }

      if (isCreatingNew) {
        // For new rules, we need to handle creation differently
        // The backend create endpoint expects structured data, so we use the yaml update approach
        const newRuleId = validateResult.rule?.id;
        if (!newRuleId) {
          setError('Rule must have an id field');
          setIsSaving(false);
          return;
        }

        // Check if rule with this ID already exists
        const existingRule = rules.find(r => r.id === newRuleId);
        if (existingRule) {
          setError(`Rule with ID "${newRuleId}" already exists`);
          setIsSaving(false);
          return;
        }

        // For creation, we'll use a workaround: directly call the backend
        const response = await fetch(`http://127.0.0.1:8765/api/semgrep-rules/create`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            id: newRuleId,
            languages: validateResult.rule?.languages || ['python'],
            severity: validateResult.rule?.severity || 'WARNING',
            message: validateResult.rule?.message || '',
            pattern_type: 'patterns',
            pattern_content: yamlContent,
            metadata: validateResult.rule?.metadata,
          }),
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || 'Failed to create rule');
        }

        setSuccessMessage('Rule created successfully');
        setIsCreatingNew(false);
        setSelectedRuleId(newRuleId);
        setOriginalYaml(yamlContent);
        setHasChanges(false);
        await loadRules();
      } else if (selectedRuleId) {
        // Update existing rule
        await updateSemgrepRuleYaml(selectedRuleId, yamlContent);

        // If ID changed, update selection
        const newRuleId = validateResult.rule?.id;
        if (newRuleId && newRuleId !== selectedRuleId) {
          setSelectedRuleId(newRuleId);
        }

        setSuccessMessage('Rule saved successfully');
        setOriginalYaml(yamlContent);
        setHasChanges(false);
        await loadRules();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save rule');
    } finally {
      setIsSaving(false);
    }
  };

  // Cancel editing
  const handleCancel = () => {
    if (hasChanges && !window.confirm('You have unsaved changes. Discard them?')) {
      return;
    }

    if (isCreatingNew) {
      setIsCreatingNew(false);
      setYamlContent('');
      setOriginalYaml('');
    } else if (selectedRuleId) {
      setYamlContent(originalYaml);
    }
    setHasChanges(false);
    setValidationError(null);
  };

  // Get severity badge color
  const getSeverityColor = (severity: string) => {
    switch (severity.toUpperCase()) {
      case 'ERROR':
      case 'HIGH':
        return 'bg-red-500/20 text-red-400';
      case 'WARNING':
      case 'MEDIUM':
        return 'bg-yellow-500/20 text-yellow-400';
      case 'INFO':
      case 'LOW':
        return 'bg-blue-500/20 text-blue-400';
      default:
        return 'bg-gray-500/20 text-gray-400';
    }
  };

  return (
    <div className="flex flex-col h-full" style={{ backgroundColor: 'var(--color-bg-window)' }}>
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3 border-b"
        style={{ borderColor: 'var(--color-divider)' }}
      >
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-1.5 rounded-lg transition-colors hover:bg-gray-700/50"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
          <h1 className="text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>
            Semgrep Rules Manager
          </h1>
        </div>
        <div className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
          {rules.length} rules
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Left sidebar - Rules list */}
        <div
          className="w-72 flex flex-col border-r"
          style={{
            backgroundColor: 'var(--color-bg-sidebar)',
            borderColor: 'var(--color-divider)'
          }}
        >
          {/* Search */}
          <div className="p-3">
            <div
              className="flex items-center px-3 py-2 rounded-lg"
              style={{ backgroundColor: 'var(--color-bg-input)' }}
            >
              <Search className="w-4 h-4 mr-2" style={{ color: 'var(--color-text-secondary)' }} />
              <input
                type="text"
                placeholder="Search rules by ID..."
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                className="flex-1 bg-transparent text-sm outline-none"
                style={{ color: 'var(--color-text-primary)' }}
              />
            </div>
          </div>

          {/* Action buttons */}
          <div className="px-3 pb-3 flex gap-2">
            <button
              onClick={handleNewRule}
              className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors"
              style={{
                backgroundColor: 'var(--color-accent)',
                color: 'white'
              }}
            >
              <Plus className="w-4 h-4" />
              Add Rule
            </button>
            <button
              onClick={handleDeleteRule}
              disabled={!selectedRuleId || isCreatingNew}
              className="flex items-center justify-center px-3 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              style={{
                backgroundColor: 'var(--color-bg-input)',
                color: selectedRuleId && !isCreatingNew ? '#ef4444' : 'var(--color-text-secondary)'
              }}
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>

          {/* Rules list */}
          <div className="flex-1 overflow-y-auto px-2">
            {isLoading ? (
              <div className="p-4 text-center" style={{ color: 'var(--color-text-secondary)' }}>
                Loading rules...
              </div>
            ) : filteredRules.length === 0 ? (
              <div className="p-4 text-center" style={{ color: 'var(--color-text-secondary)' }}>
                {searchText ? 'No matching rules' : 'No rules found'}
              </div>
            ) : (
              filteredRules.map((rule) => (
                <div
                  key={rule.id}
                  onClick={() => handleSelectRule(rule.id)}
                  className="p-3 mb-1 rounded-lg cursor-pointer transition-colors"
                  style={{
                    backgroundColor: selectedRuleId === rule.id ? 'var(--color-selected)' : 'transparent',
                  }}
                  onMouseEnter={(e) => {
                    if (selectedRuleId !== rule.id) {
                      e.currentTarget.style.backgroundColor = 'var(--color-hover)';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (selectedRuleId !== rule.id) {
                      e.currentTarget.style.backgroundColor = 'transparent';
                    }
                  }}
                >
                  <div className="text-sm font-medium truncate" style={{ color: 'var(--color-text-primary)' }}>
                    {rule.id}
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`text-xs px-1.5 py-0.5 rounded ${getSeverityColor(rule.severity)}`}>
                      {rule.severity}
                    </span>
                    <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                      {rule.languages.join(', ')}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Right content - Editor */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Editor header */}
          {(selectedRuleId || isCreatingNew) && (
            <div
              className="flex items-center justify-between px-4 py-2 border-b"
              style={{ borderColor: 'var(--color-divider)' }}
            >
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
                  {isCreatingNew ? 'New Rule' : selectedRuleId}
                </span>
                {hasChanges && (
                  <span className="text-xs px-2 py-0.5 rounded bg-yellow-500/20 text-yellow-400">
                    Unsaved changes
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleValidate}
                  className="px-3 py-1.5 rounded text-sm transition-colors"
                  style={{
                    backgroundColor: 'var(--color-bg-input)',
                    color: 'var(--color-text-primary)'
                  }}
                >
                  Validate
                </button>
                <button
                  onClick={handleCancel}
                  disabled={!hasChanges}
                  className="p-1.5 rounded transition-colors disabled:opacity-50"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  <X className="w-4 h-4" />
                </button>
                <button
                  onClick={handleSave}
                  disabled={!hasChanges || isSaving}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded text-sm font-medium transition-colors disabled:opacity-50"
                  style={{
                    backgroundColor: hasChanges ? 'var(--color-accent)' : 'var(--color-bg-input)',
                    color: hasChanges ? 'white' : 'var(--color-text-secondary)'
                  }}
                >
                  <Save className="w-4 h-4" />
                  {isSaving ? 'Saving...' : 'Save'}
                </button>
              </div>
            </div>
          )}

          {/* Messages */}
          {(error || successMessage || validationError) && (
            <div className="px-4 py-2">
              {error && (
                <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 text-red-400 text-sm">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  {error}
                </div>
              )}
              {validationError && (
                <div className="flex items-center gap-2 p-3 rounded-lg bg-yellow-500/10 text-yellow-400 text-sm">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  {validationError}
                </div>
              )}
              {successMessage && (
                <div className="flex items-center gap-2 p-3 rounded-lg bg-green-500/10 text-green-400 text-sm">
                  <CheckCircle className="w-4 h-4 flex-shrink-0" />
                  {successMessage}
                </div>
              )}
            </div>
          )}

          {/* Editor content */}
          {(selectedRuleId || isCreatingNew) ? (
            <div className="flex-1 overflow-hidden p-4">
              <textarea
                value={yamlContent}
                onChange={(e) => handleYamlChange(e.target.value)}
                className="w-full h-full p-4 rounded-lg font-mono text-sm resize-none outline-none"
                style={{
                  backgroundColor: 'var(--color-bg-input)',
                  color: 'var(--color-text-primary)',
                  border: '1px solid var(--color-divider)'
                }}
                placeholder="Enter YAML content..."
                spellCheck={false}
              />
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center" style={{ color: 'var(--color-text-secondary)' }}>
                <p className="text-lg mb-2">Select a rule to edit</p>
                <p className="text-sm">or click "Add Rule" to create a new one</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
