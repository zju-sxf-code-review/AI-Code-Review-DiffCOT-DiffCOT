/**
 * API Service for connecting to the Daily Agent backend
 */

import type { Message } from '../types';

const API_BASE_URL = 'http://127.0.0.1:8765/api';

// Request/Response types matching backend schemas
export interface AttachmentInfo {
  file_name: string;
  file_type: string;
  file_size?: number;
  document_id?: string;
}

interface ChatRequest {
  user_id: string;
  conversation_id: string;
  query: string;
  history: MessageRequest[];
  attachments: AttachmentInfo[];  // Current message attachments
  provider: string;
  model_name: string;
  temperature: number;
  max_tokens?: number;
  enable_rag: boolean;
  system_prompt?: string;
}

interface MessageRequest {
  role: 'user' | 'assistant' | 'system';
  content: string;
  attachments?: AttachmentRequest[];
}

interface AttachmentRequest {
  file_name: string;
  file_type: string;
  data?: string;
}

interface ChatResponse {
  conversation_id: string;
  message: string;
  role: string;
  model_used: string;
  provider_used: string;
  tokens_used?: number;
  tools_used: string[];
  rag_sources: Record<string, unknown>[];
  created_at: string;
  response_time_ms?: number;
}

interface StreamChunk {
  content: string;
  is_final: boolean;
  metadata?: Record<string, unknown>;
}

export interface ModelInfo {
  provider: string;
  model_name: string;
  display_name: string;
  is_available: boolean;
  supports_streaming: boolean;
  supports_vision: boolean;
}

export interface ProviderStatus {
  provider: string;
  is_configured: boolean;
  is_available: boolean;
  models: ModelInfo[];
  error?: string;
}

interface ModelsResponse {
  providers: ProviderStatus[];
}

// Convert frontend Message to API MessageRequest
function messageToRequest(msg: Message): MessageRequest {
  return {
    role: msg.role,
    content: msg.content,
    attachments: msg.attachments?.map(att => ({
      file_name: att.fileName || att.name,
      file_type: att.fileType || att.type,
      data: att.data,
    })),
  };
}

/**
 * Send a chat message (non-streaming)
 */
export async function sendMessage(
  query: string,
  conversationId: string,
  history: Message[],
  provider: string = 'qwen',
  modelName: string = 'qwen-max',
  currentAttachments: AttachmentInfo[] = []
): Promise<ChatResponse> {
  const request: ChatRequest = {
    user_id: 'default',
    conversation_id: conversationId,
    query,
    history: history.map(messageToRequest),
    attachments: currentAttachments,
    provider,
    model_name: modelName,
    temperature: 0.7,
    enable_rag: false,
  };

  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

/**
 * Send a chat message with streaming response
 */
export async function* streamMessage(
  query: string,
  conversationId: string,
  history: Message[],
  provider: string = 'qwen',
  modelName: string = 'qwen-max',
  currentAttachments: AttachmentInfo[] = []
): AsyncGenerator<StreamChunk, void, unknown> {
  console.log(`[API] Sending stream request with ${currentAttachments.length} attachments`);
  
  const request: ChatRequest = {
    user_id: 'default',
    conversation_id: conversationId,
    query,
    history: history.map(messageToRequest),
    attachments: currentAttachments,  // Include current message attachments
    provider,
    model_name: modelName,
    temperature: 0.7,
    enable_rag: false,
  };

  const response = await fetch(`${API_BASE_URL}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('No response body');
  }

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const chunk: StreamChunk = JSON.parse(line.slice(6));
          yield chunk;
        } catch {
          // Skip invalid JSON
        }
      }
    }
  }
}

/**
 * Fetch available models from all providers
 */
export async function fetchModels(): Promise<ProviderStatus[]> {
  const response = await fetch(`${API_BASE_URL}/models`);
  
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }

  const data: ModelsResponse = await response.json();
  return data.providers;
}

/**
 * Check if backend is healthy
 */
export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL.replace('/api', '')}/health`, {
      method: 'GET',
      signal: AbortSignal.timeout(10000), // Increased timeout to 10s to handle slow responses during heavy operations
    });
    return response.ok;
  } catch {
    return false;
  }
}

// ============ Conversation API ============

export interface ConversationListItem {
  id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  provider: string;
  model_name: string;
  message_count: number;
}

export interface MessageResponse {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  model_used?: string;
  provider_used?: string;
  tokens_used?: number;
}

export interface ConversationResponse {
  id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  provider: string;
  model_name: string;
  system_prompt?: string;
  metadata?: string;  // JSON string for github_repo, pull_requests, etc.
  messages: MessageResponse[];
}

/**
 * List all conversations
 */
export async function listConversations(userId: string = 'default'): Promise<ConversationListItem[]> {
  const response = await fetch(`${API_BASE_URL}/conversations?user_id=${userId}`);
  
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Create a new conversation
 */
export async function createConversation(
  title: string = 'New Chat',
  provider: string = 'ollama',
  modelName: string = 'qwen3:14b',
  userId: string = 'default'
): Promise<ConversationResponse> {
  const response = await fetch(`${API_BASE_URL}/conversations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title,
      user_id: userId,
      provider,
      model_name: modelName,
    }),
  });
  
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Get a conversation with all messages
 */
export async function getConversation(conversationId: string): Promise<ConversationResponse> {
  const response = await fetch(`${API_BASE_URL}/conversations/${conversationId}`);
  
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Update a conversation
 */
export async function updateConversation(
  conversationId: string,
  updates: { title?: string; provider?: string; model_name?: string; system_prompt?: string; metadata?: string }
): Promise<ConversationResponse> {
  const response = await fetch(`${API_BASE_URL}/conversations/${conversationId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  });
  
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Delete a conversation
 */
export async function deleteConversation(conversationId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/conversations/${conversationId}`, {
    method: 'DELETE',
  });
  
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
}

/**
 * Add a message to a conversation
 */
export async function addMessage(
  conversationId: string,
  role: 'user' | 'assistant',
  content: string,
  metadata?: { model_used?: string; provider_used?: string; tokens_used?: number }
): Promise<MessageResponse> {
  const response = await fetch(`${API_BASE_URL}/conversations/${conversationId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      role,
      content,
      ...metadata,
    }),
  });
  
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Update a message's content
 */
export async function updateMessageContent(
  conversationId: string,
  messageId: string,
  content: string
): Promise<MessageResponse> {
  const response = await fetch(`${API_BASE_URL}/conversations/${conversationId}/messages/${messageId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  });
  
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
  
  return response.json();
}


// ========== Document Upload API ==========

export interface DocumentUploadResponse {
  id: string;
  filename: string;
  document_type: string;
  status: string;
  message: string;
}

export interface DocumentStatusResponse {
  id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  chunks_count: number;
  error_message?: string;
  progress_percentage?: number;
}

/**
 * Upload a document for RAG processing
 */
export async function uploadDocument(
  file: File,
  userId: string = 'default',
  conversationId?: string
): Promise<DocumentUploadResponse> {
  console.log(`[API] Uploading document: ${file.name} (${file.size} bytes)`);
  
  const formData = new FormData();
  formData.append('file', file);
  formData.append('user_id', userId);
  if (conversationId) {
    formData.append('conversation_id', conversationId);
  }

  const response = await fetch(`${API_BASE_URL}/documents/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Upload failed: ${response.status} - ${errorText}`);
  }

  const result = await response.json();
  console.log(`[API] Document uploaded successfully:`, result);
  return result;
}

/**
 * Get document processing status
 */
export async function getDocumentStatus(documentId: string): Promise<DocumentStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/documents/${documentId}/status`);
  
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Wait for document processing to complete
 * Polls the status endpoint until the document is processed or failed
 */
export async function waitForDocumentProcessing(
  documentId: string,
  onProgress?: (status: DocumentStatusResponse) => void,
  maxAttempts: number = 60,
  intervalMs: number = 1000
): Promise<DocumentStatusResponse> {
  console.log(`[API] Waiting for document processing: ${documentId}`);
  
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const status = await getDocumentStatus(documentId);
    
    if (onProgress) {
      onProgress(status);
    }
    
    if (status.status === 'completed') {
      console.log(`[API] Document processed successfully: ${documentId}`);
      return status;
    }
    
    if (status.status === 'failed') {
      throw new Error(`Document processing failed: ${status.error_message || 'Unknown error'}`);
    }
    
    // Wait before next poll
    await new Promise(resolve => setTimeout(resolve, intervalMs));
  }
  
  throw new Error('Document processing timeout');
}

/**
 * Submit a URL for RAG processing
 */
export async function submitUrl(
  url: string,
  userId: string = 'default',
  conversationId?: string
): Promise<DocumentUploadResponse> {
  console.log(`[API] Submitting URL for RAG processing: ${url}`);
  
  const response = await fetch(`${API_BASE_URL}/documents/submit-url`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      url,
      user_id: userId,
      conversation_id: conversationId,
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`URL submission failed: ${response.status} - ${errorText}`);
  }

  const result = await response.json();
  console.log(`[API] URL submitted successfully:`, result);
  return result;
}

/**
 * Check if a string is a valid URL
 */
export function isValidUrl(text: string): boolean {
  try {
    const url = new URL(text);
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch {
    return false;
  }
}


// ========== GitHub API ==========

export interface GitHubRepo {
  id: number;
  name: string;
  full_name: string;
  owner: string;
  description?: string;
  url: string;
  default_branch: string;
  private: boolean;
  language?: string;
  stargazers_count: number;
  forks_count: number;
}

export interface PullRequest {
  id: number;
  number: number;
  title: string;
  state: string;
  author: string;
  created_at: string;
  updated_at: string;
  html_url: string;
  head_branch: string;
  base_branch: string;
  draft?: boolean;
  additions?: number;
  deletions?: number;
  changed_files?: number;
}

export interface PullRequestDetail extends PullRequest {
  body?: string;
  merged: boolean;
  merged_at?: string;
  head_sha: string;
  base_sha: string;
  commits: number;
  mergeable?: boolean;
}

export interface PRFile {
  filename: string;
  status: string;
  additions: number;
  deletions: number;
  changes: number;
  patch: string;
  previous_filename?: string;
}

export interface ReviewIssue {
  severity: string;  // HIGH, MEDIUM, LOW
  type: string;
  file: string;
  line?: number | string;  // Can be number or range like "42-50"
  end_line?: number | string;  // End line for multi-line suggestions
  description: string;
  suggestion?: string;
  suggested_change?: string;  // Exact replacement code for GitHub suggestions
}

export interface CodeReviewResult {
  summary: string;
  overall_assessment: string;  // APPROVE, REQUEST_CHANGES, COMMENT
  score: number;
  issues: ReviewIssue[];
  positive_feedback: string[];
  suggestions: string[];
  raw_review?: string;
}

// SAST Analysis Models
export interface SastFinding {
  rule_id: string;
  severity: string;  // HIGH, MEDIUM, LOW
  message: string;
  file: string;
  line: number;
  end_line?: number;
  column?: number;
  end_column?: number;
  category: string;  // security, correctness, performance, style
  cwe?: string;
  owasp?: string;
  fix?: string;
  code_snippet?: string;
}

export interface SastResult {
  success: boolean;
  findings: SastFinding[];
  error?: string;
  tool: string;
  duration_ms?: number;
  languages_detected: string[];
}

// Intent Analysis Models
export interface IntentAnalysisResult {
  success: boolean;
  purpose: string;
  implementation_approach: string;
  key_changes: string[];
  potential_issues: string[];
  missing_considerations: string[];
  architectural_impact: string;
  confidence: number;
  error?: string;
  duration_ms?: number;
}

// Context Extraction Models
export interface ContextExtractionResult {
  success: boolean;
  changed_files_count: number;
  related_files_count: number;
  repo_structure_depth: number;
  languages_detected: string[];
  error?: string;
}

export interface ReviewResponse {
  success: boolean;
  review?: CodeReviewResult;
  error?: string;
  pr_info?: PullRequestDetail;
  duration_ms?: number;
  sast_result?: SastResult;  // SAST analysis result
  intent_analysis?: IntentAnalysisResult;  // Intent analysis result
  context_extraction?: ContextExtractionResult;  // Context extraction info
}

/**
 * Set GitHub token for API access
 */
export async function setGitHubToken(token: string): Promise<{ success: boolean; message: string }> {
  const response = await fetch(`${API_BASE_URL}/github/token?token=${encodeURIComponent(token)}`, {
    method: 'POST',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to set GitHub token');
  }

  return response.json();
}

/**
 * Parse a GitHub repository URL
 */
export async function parseRepoUrl(url: string): Promise<{ owner: string; repo: string; full_name: string }> {
  const response = await fetch(`${API_BASE_URL}/github/repos/parse`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Invalid repository URL');
  }

  return response.json();
}

/**
 * Add a GitHub repository by URL
 */
export async function addGitHubRepo(url: string): Promise<GitHubRepo> {
  const response = await fetch(`${API_BASE_URL}/github/repos`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to add repository');
  }

  return response.json();
}

/**
 * Get repository information
 */
export async function getRepository(owner: string, repo: string): Promise<GitHubRepo> {
  const response = await fetch(`${API_BASE_URL}/github/repos/${owner}/${repo}`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to get repository');
  }

  return response.json();
}

/**
 * List pull requests for a repository
 */
export async function listPullRequests(
  owner: string,
  repo: string,
  state: 'open' | 'closed' | 'all' = 'open',
  perPage: number = 30
): Promise<PullRequest[]> {
  const response = await fetch(
    `${API_BASE_URL}/github/repos/${owner}/${repo}/pulls?state=${state}&per_page=${perPage}`
  );

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to list pull requests');
  }

  return response.json();
}

/**
 * Get detailed pull request information
 */
export async function getPullRequest(owner: string, repo: string, prNumber: number): Promise<PullRequestDetail> {
  const response = await fetch(`${API_BASE_URL}/github/repos/${owner}/${repo}/pulls/${prNumber}`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to get pull request');
  }

  return response.json();
}

/**
 * Get files changed in a pull request
 */
export async function getPullRequestFiles(owner: string, repo: string, prNumber: number): Promise<PRFile[]> {
  const response = await fetch(`${API_BASE_URL}/github/repos/${owner}/${repo}/pulls/${prNumber}/files`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to get PR files');
  }

  return response.json();
}

/**
 * Get pull request diff
 */
export async function getPullRequestDiff(owner: string, repo: string, prNumber: number): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/github/repos/${owner}/${repo}/pulls/${prNumber}/diff`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to get PR diff');
  }

  const data = await response.json();
  return data.diff;
}

/**
 * Start a code review for a pull request
 */
export async function startCodeReview(
  repoOwner: string,
  repoName: string,
  prNumber: number,
  provider: 'glm' | 'anthropic' = 'glm',
  model?: string,
  enableSast: boolean = true
): Promise<ReviewResponse> {
  const response = await fetch(`${API_BASE_URL}/review/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      repo_owner: repoOwner,
      repo_name: repoName,
      pr_number: prNumber,
      provider,
      model,
      enable_sast: enableSast,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to start code review');
  }

  return response.json();
}

/**
 * Configure review API keys
 */
export async function configureReview(
  githubToken?: string,
  glmApiKey?: string,
  claudeApiKey?: string
): Promise<{ success: boolean; configured: string[]; message: string }> {
  const params = new URLSearchParams();
  if (githubToken) params.append('github_token', githubToken);
  if (glmApiKey) params.append('glm_api_key', glmApiKey);
  if (claudeApiKey) params.append('claude_api_key', claudeApiKey);

  const response = await fetch(`${API_BASE_URL}/review/configure?${params.toString()}`, {
    method: 'POST',
  });

  if (!response.ok) {
    throw new Error('Failed to configure review settings');
  }

  return response.json();
}

// ============ GitHub Comment API ============

export interface PostCommentRequest {
  repo_owner: string;
  repo_name: string;
  pr_number: number;
  summary: string;
  overall_assessment: string;
  score: number;
  issues: ReviewIssue[];
  positive_feedback: string[];
  suggestions: string[];
}

export interface PostCommentResponse {
  success: boolean;
  error?: string;
  review_id?: number;
  comment_count: number;
  url?: string;
}

/**
 * Post review comments to GitHub PR
 */
export async function postCommentToGitHub(
  repoOwner: string,
  repoName: string,
  prNumber: number,
  review: CodeReviewResult
): Promise<PostCommentResponse> {
  const response = await fetch(`${API_BASE_URL}/review/comment`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      repo_owner: repoOwner,
      repo_name: repoName,
      pr_number: prNumber,
      summary: review.summary,
      overall_assessment: review.overall_assessment,
      score: review.score,
      issues: review.issues,
      positive_feedback: review.positive_feedback,
      suggestions: review.suggestions,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to post comment to GitHub');
  }

  return response.json();
}

// ============ Semgrep Rules API ============

export interface SemgrepRuleListItem {
  id: string;
  languages: string[];
  severity: string;
}

export interface SemgrepRule {
  id: string;
  languages: string[];
  severity: string;
  message: string;
  pattern?: string;
  patterns?: unknown[];
  'pattern-regex'?: string;
  'pattern-either'?: unknown[];
  metadata?: Record<string, unknown>;
  [key: string]: unknown;
}

/**
 * List all Semgrep rules (id, languages, severity only)
 */
export async function listSemgrepRules(): Promise<SemgrepRuleListItem[]> {
  const response = await fetch(`${API_BASE_URL}/semgrep-rules/list`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to list Semgrep rules');
  }

  return response.json();
}

/**
 * Get a single Semgrep rule by ID
 */
export async function getSemgrepRule(ruleId: string): Promise<SemgrepRule> {
  const response = await fetch(`${API_BASE_URL}/semgrep-rules/${encodeURIComponent(ruleId)}`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to get Semgrep rule');
  }

  return response.json();
}

/**
 * Get a single Semgrep rule as YAML string
 */
export async function getSemgrepRuleYaml(ruleId: string): Promise<{ yaml: string; rule: SemgrepRule }> {
  const response = await fetch(`${API_BASE_URL}/semgrep-rules/${encodeURIComponent(ruleId)}/yaml`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to get Semgrep rule YAML');
  }

  return response.json();
}

/**
 * Update a Semgrep rule from YAML string
 */
export async function updateSemgrepRuleYaml(ruleId: string, yaml: string): Promise<{ success: boolean; rule: SemgrepRule }> {
  const response = await fetch(`${API_BASE_URL}/semgrep-rules/${encodeURIComponent(ruleId)}/yaml`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ yaml }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to update Semgrep rule');
  }

  return response.json();
}

/**
 * Create a new Semgrep rule from YAML string
 */
export async function createSemgrepRuleYaml(yaml: string): Promise<{ success: boolean; rule: SemgrepRule }> {
  // First validate
  const validateResponse = await fetch(`${API_BASE_URL}/semgrep-rules/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ yaml }),
  });

  const validateResult = await validateResponse.json();
  if (!validateResult.valid) {
    throw new Error(validateResult.error || 'Invalid rule YAML');
  }

  // Extract the rule ID from validated rule
  const ruleId = validateResult.rule.id;

  // Use the update endpoint with a new ID (will fail if exists, so we use create logic)
  const response = await fetch(`${API_BASE_URL}/semgrep-rules/create`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      id: ruleId,
      languages: validateResult.rule.languages,
      severity: validateResult.rule.severity,
      message: validateResult.rule.message,
      pattern_type: validateResult.rule.pattern ? 'pattern' :
                    validateResult.rule.patterns ? 'patterns' :
                    validateResult.rule['pattern-regex'] ? 'pattern-regex' :
                    validateResult.rule['pattern-either'] ? 'pattern-either' : 'pattern',
      pattern_content: yaml,
      metadata: validateResult.rule.metadata,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to create Semgrep rule');
  }

  return response.json();
}

/**
 * Delete a Semgrep rule by ID
 */
export async function deleteSemgrepRule(ruleId: string): Promise<{ success: boolean; message: string }> {
  const response = await fetch(`${API_BASE_URL}/semgrep-rules/${encodeURIComponent(ruleId)}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to delete Semgrep rule');
  }

  return response.json();
}

/**
 * Validate a Semgrep rule YAML without saving
 */
export async function validateSemgrepRuleYaml(yaml: string): Promise<{ valid: boolean; error?: string; rule?: SemgrepRule }> {
  const response = await fetch(`${API_BASE_URL}/semgrep-rules/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ yaml }),
  });

  return response.json();
}
