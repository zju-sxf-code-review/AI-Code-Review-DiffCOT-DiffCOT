import React, { useState, useRef, useEffect } from 'react';
import { Plus, User, Settings, Wifi, WifiOff, X, ExternalLink, GitBranch, GitPullRequest, Play, Loader2, Check, MessageSquare } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import type { Conversation, Attachment, PullRequest, GitHubRepo, Message } from '../types';
import { addGitHubRepo, listPullRequests, startCodeReview, postCommentToGitHub, addMessage, updateMessageContent, type CodeReviewResult } from '../services/api';
import clsx from 'clsx';
import { format } from 'date-fns';
import { v4 as uuidv4 } from 'uuid';
import logoImage from '../assets/logo.png';

// Extend Window interface for Electron API
declare global {
  interface Window {
    electronAPI?: {
      openPath: (path: string) => Promise<string>;
      openExternal: (url: string) => Promise<void>;
    };
  }
}

// Format file size
const formatFileSize = (bytes?: number): string => {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

// File type icon mapping
const getFileIcon = (fileName: string, fileType: string): string => {
  const ext = fileName.split('.').pop()?.toLowerCase() || '';
  if (['pdf'].includes(ext)) return '📄';
  if (['doc', 'docx'].includes(ext)) return '📝';
  if (['xls', 'xlsx', 'csv'].includes(ext)) return '📊';
  if (['ppt', 'pptx'].includes(ext)) return '📽️';
  if (['md', 'markdown', 'txt'].includes(ext)) return '📋';
  if (['json', 'xml', 'yaml', 'yml'].includes(ext)) return '⚙️';
  if (['html', 'htm'].includes(ext)) return '🌐';
  if (fileType.startsWith('image/')) return '🖼️';
  if (fileType.startsWith('video/')) return '🎬';
  if (fileType.startsWith('audio/')) return '🎵';
  return '📁';
};

// Attachment display component
const AttachmentCard: React.FC<{ attachment: Attachment; isUserMessage: boolean }> = ({ attachment, isUserMessage }) => {
  const fileName = attachment.fileName || attachment.name;
  const fileType = attachment.fileType || attachment.type;
  const icon = getFileIcon(fileName, fileType);
  const fileSize = formatFileSize(attachment.fileSize);

  const handleClick = () => {
    if (attachment.url) {
      if (window.electronAPI?.openPath) {
        window.electronAPI.openPath(attachment.url);
      } else {
        window.open(attachment.url, '_blank');
      }
    }
  };

  return (
    <button
      onClick={handleClick}
      className="flex items-center gap-2 px-3 py-2 rounded-lg transition-all hover:scale-[1.02] cursor-pointer group"
      style={{
        backgroundColor: isUserMessage
          ? 'rgba(255,255,255,0.15)'
          : 'var(--color-bg-secondary)',
        border: `1px solid ${isUserMessage ? 'rgba(255,255,255,0.2)' : 'var(--color-divider)'}`
      }}
      title={`Click to open ${fileName}`}
    >
      <span className="text-xl">{icon}</span>
      <div className="flex flex-col items-start min-w-0">
        <span
          className="text-sm font-medium truncate max-w-[180px]"
          style={{ color: isUserMessage ? 'var(--color-text-user)' : 'var(--color-text-primary)' }}
        >
          {fileName}
        </span>
        <span
          className="text-xs"
          style={{ color: isUserMessage ? 'rgba(255,255,255,0.7)' : 'var(--color-text-secondary)' }}
        >
          {fileType.split('/').pop()?.toUpperCase() || 'FILE'}
          {fileSize && ` · ${fileSize}`}
        </span>
      </div>
      <ExternalLink
        className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity ml-1"
        style={{ color: isUserMessage ? 'var(--color-text-user)' : 'var(--color-text-secondary)' }}
      />
    </button>
  );
};

// Parse GitHub URL to extract owner and repo
const parseGitHubUrl = (url: string): GitHubRepo | null => {
  try {
    const patterns = [
      /github\.com\/([^\/]+)\/([^\/]+)/,
      /github\.com:([^\/]+)\/([^\/]+)/,
    ];

    for (const pattern of patterns) {
      const match = url.match(pattern);
      if (match) {
        const owner = match[1];
        const name = match[2].replace(/\.git$/, '');
        return {
          url: `https://github.com/${owner}/${name}`,
          owner,
          name,
          full_name: `${owner}/${name}`,
        };
      }
    }
    return null;
  } catch {
    return null;
  }
};

interface ChatProps {
  conversation: Conversation;
  onSendMessage: (text: string, files: File[]) => void;
  onOpenSettings?: () => void;
  selectedProvider: string;
  selectedModel: string;
  onModelChange: (provider: string, model: string) => void;
  isBackendConnected: boolean;
  settingsVersion: number;
  onUpdateConversation?: (updates: Partial<Conversation>) => void;
  onAddMessages?: (conversationId: string, messages: Message[]) => void;
  onUpdateMessageContent?: (conversationId: string, messageId: string, content: string) => void;
}

export const Chat: React.FC<ChatProps> = ({
  conversation,
  onSendMessage: _onSendMessage,
  onOpenSettings,
  selectedProvider,
  selectedModel,
  onModelChange: _onModelChange,
  isBackendConnected,
  settingsVersion: _settingsVersion,
  onUpdateConversation,
  onAddMessages,
  onUpdateMessageContent,
}) => {
  // State for GitHub repo input
  const [showRepoInput, setShowRepoInput] = useState(false);
  const [repoUrl, setRepoUrl] = useState('');
  const [isLoadingPRs, setIsLoadingPRs] = useState(false);
  const [selectedPRId, setSelectedPRId] = useState<number | null>(null);
  const [isPostingComment, setIsPostingComment] = useState(false);
  const [lastReviewResult, setLastReviewResult] = useState<CodeReviewResult | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const repoInputRef = useRef<HTMLInputElement>(null);

  // Use conversation-level isAnalyzing state for parallel analysis support
  const isAnalyzing = conversation.isAnalyzing ?? false;
  const setIsAnalyzing = (value: boolean) => {
    if (onUpdateConversation) {
      onUpdateConversation({ isAnalyzing: value });
    }
  };

  // Check if last message is still being generated
  const isGenerating = conversation.messages.length > 0 &&
    conversation.messages[conversation.messages.length - 1].role === 'assistant' &&
    conversation.messages[conversation.messages.length - 1].content === '';

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [conversation.messages]);

  // Focus repo input when shown
  useEffect(() => {
    if (showRepoInput && repoInputRef.current) {
      repoInputRef.current.focus();
    }
  }, [showRepoInput]);

  // Handle adding GitHub repo
  const handleAddRepo = async () => {
    if (!repoUrl.trim()) return;

    const parsedRepo = parseGitHubUrl(repoUrl);
    if (!parsedRepo) {
      alert('Invalid GitHub URL. Please enter a valid GitHub repository URL.');
      return;
    }

    setIsLoadingPRs(true);

    try {
      // Call backend API to get repository info
      console.log('[Chat] Fetching repository info...');
      const repoInfo = await addGitHubRepo(repoUrl);
      console.log('[Chat] Repository info received:', repoInfo);

      // Fetch pull requests from the repository
      console.log('[Chat] Fetching pull requests...');
      const prs = await listPullRequests(repoInfo.owner, repoInfo.name, 'open', 30);
      console.log('[Chat] Pull requests received:', prs.length, 'PRs');

      // Convert API response to our PullRequest type
      const pullRequests: PullRequest[] = prs.map(pr => ({
        id: pr.id,
        number: pr.number,
        title: pr.title,
        state: pr.state as 'open' | 'closed' | 'merged',
        author: pr.author,
        created_at: pr.created_at,
        updated_at: pr.updated_at,
        html_url: pr.html_url,
        head_branch: pr.head_branch,
        base_branch: pr.base_branch,
        additions: pr.additions,
        deletions: pr.deletions,
        changed_files: pr.changed_files,
      }));

      // Build GitHubRepo object
      const githubRepo: GitHubRepo = {
        url: repoInfo.url,
        owner: repoInfo.owner,
        name: repoInfo.name,
        full_name: repoInfo.full_name,
        default_branch: repoInfo.default_branch,
      };

      // Update conversation with repo info and PRs
      if (onUpdateConversation) {
        console.log('[Chat] Updating conversation with', pullRequests.length, 'PRs');
        onUpdateConversation({
          github_repo: githubRepo,
          pull_requests: pullRequests,
          title: repoInfo.full_name,
        });
      }

      setShowRepoInput(false);
      setRepoUrl('');
    } catch (error) {
      console.error('[Chat] Failed to fetch repository:', error);
      alert(`Failed to fetch repository: ${error instanceof Error ? error.message : 'Unknown error'}. Please check your GitHub token in settings.`);
    } finally {
      setIsLoadingPRs(false);
    }
  };

  // Handle starting analysis
  const handleStartAnalysis = async () => {
    if (!selectedPRId || !conversation.github_repo) return;

    const selectedPR = conversation.pull_requests?.find(pr => pr.id === selectedPRId);
    if (!selectedPR) return;

    setIsAnalyzing(true);

    // Update conversation with selected PR
    if (onUpdateConversation) {
      onUpdateConversation({ selected_pr: selectedPR });
    }

    // Create user message content
    const userContent = `Please review PR #${selectedPR.number}: "${selectedPR.title}"\n\nRepository: ${conversation.github_repo.full_name}\nBranch: ${selectedPR.head_branch} → ${selectedPR.base_branch}${selectedPR.additions != null ? `\nChanges: +${selectedPR.additions} -${selectedPR.deletions} in ${selectedPR.changed_files} files` : ''}`;

    // Determine provider and model to use (with defaults)
    const provider = selectedProvider || 'glm';
    const model = selectedModel || (provider === 'glm' ? 'glm-4.6' : 'claude-opus-4-5-20251101');

    // Save messages to backend first, then update local state
    let userMsgId = uuidv4();
    let assistantMsgId = uuidv4();

    try {
      // Save user message to backend
      const savedUserMsg = await addMessage(conversation.id, 'user', userContent);
      userMsgId = savedUserMsg.id;
      console.log('[Chat] User message saved to backend:', userMsgId);

      // Save placeholder assistant message to backend
      const savedAssistantMsg = await addMessage(conversation.id, 'assistant', '', {
        provider_used: provider,
        model_used: model,
      });
      assistantMsgId = savedAssistantMsg.id;
      console.log('[Chat] Assistant placeholder saved to backend:', assistantMsgId);
    } catch (error) {
      console.error('[Chat] Failed to save messages to backend:', error);
      // Continue with local IDs if backend save fails
    }

    // Create message objects for local state
    const userMessage: Message = {
      id: userMsgId,
      role: 'user',
      content: userContent,
      timestamp: new Date(),
      attachments: [],
    };

    const assistantMessage: Message = {
      id: assistantMsgId,
      role: 'assistant',
      content: '', // Empty content triggers loading animation
      timestamp: new Date(),
      attachments: [],
      provider_used: provider,
      model_used: model,
    };

    // Add messages to local state immediately using the new function to avoid closure issues
    if (onAddMessages) {
      onAddMessages(conversation.id, [userMessage, assistantMessage]);
    } else if (onUpdateConversation) {
      // Fallback to old method
      onUpdateConversation({
        messages: [...conversation.messages, userMessage, assistantMessage],
      });
    }

    try {
      console.log('[Chat] Starting code review with provider:', provider, 'model:', model);

      // Call the backend review API
      const reviewResponse = await startCodeReview(
        conversation.github_repo.owner,
        conversation.github_repo.name,
        selectedPR.number,
        provider as 'glm' | 'anthropic',
        model
      );

      console.log('[Chat] Review response:', reviewResponse);

      // Format the review result as structured markdown
      let reviewContent = '';

      if (reviewResponse.success && reviewResponse.review) {
        const review = reviewResponse.review;

        // Header with PR info
        reviewContent = `# 📋 Code Review Report\n\n`;
        reviewContent += `> **Repository:** ${conversation.github_repo.full_name}  \n`;
        reviewContent += `> **PR #${selectedPR.number}:** ${selectedPR.title}  \n`;
        reviewContent += `> **Branch:** \`${selectedPR.head_branch}\` → \`${selectedPR.base_branch}\`\n\n`;
        reviewContent += `---\n\n`;

        // SAST Analysis Section (if available)
        if (reviewResponse.sast_result) {
          const sast = reviewResponse.sast_result;
          reviewContent += `## 🔬 Static Analysis (SAST)\n\n`;

          if (sast.success) {
            if (sast.languages_detected && sast.languages_detected.length > 0) {
              reviewContent += `**Languages:** ${sast.languages_detected.join(', ')}\n\n`;
            }

            if (sast.findings && sast.findings.length > 0) {
              const highCount = sast.findings.filter(f => f.severity === 'HIGH').length;
              const mediumCount = sast.findings.filter(f => f.severity === 'MEDIUM').length;
              const lowCount = sast.findings.filter(f => f.severity === 'LOW').length;

              reviewContent += `| Severity | Count |\n`;
              reviewContent += `|:---------|:------|\n`;
              reviewContent += `| 🔴 High | ${highCount} |\n`;
              reviewContent += `| 🟡 Medium | ${mediumCount} |\n`;
              reviewContent += `| 🟢 Low | ${lowCount} |\n\n`;

              // Show top SAST findings (limit to 5)
              const topFindings = sast.findings.slice(0, 5);
              for (const finding of topFindings) {
                const severityEmoji = finding.severity === 'HIGH' ? '🔴' : finding.severity === 'MEDIUM' ? '🟡' : '🟢';
                reviewContent += `#### ${severityEmoji} ${finding.rule_id}\n\n`;
                reviewContent += `**File:** \`${finding.file}:${finding.line}\`\n\n`;
                reviewContent += `> ${finding.message}\n\n`;
                if (finding.cwe) {
                  reviewContent += `**CWE:** ${finding.cwe}\n\n`;
                }
              }

              if (sast.findings.length > 5) {
                reviewContent += `*... and ${sast.findings.length - 5} more SAST findings*\n\n`;
              }
            } else {
              reviewContent += `✅ No SAST issues detected.\n\n`;
            }

            if (sast.duration_ms) {
              reviewContent += `*SAST completed in ${(sast.duration_ms / 1000).toFixed(1)}s using ${sast.tool}*\n\n`;
            }
          } else {
            reviewContent += `⚠️ SAST analysis failed: ${sast.error || 'Unknown error'}\n\n`;
          }

          reviewContent += `---\n\n`;
        }

        // Intent Analysis Section (if available)
        if (reviewResponse.intent_analysis) {
          const intent = reviewResponse.intent_analysis;
          reviewContent += `## 🎯 Intent Analysis\n\n`;

          if (intent.success) {
            if (intent.purpose) {
              reviewContent += `### Purpose\n${intent.purpose}\n\n`;
            }

            if (intent.implementation_approach) {
              reviewContent += `### Implementation Approach\n${intent.implementation_approach}\n\n`;
            }

            if (intent.key_changes && intent.key_changes.length > 0) {
              reviewContent += `### Key Changes\n`;
              for (const change of intent.key_changes) {
                reviewContent += `- ${change}\n`;
              }
              reviewContent += `\n`;
            }

            if (intent.potential_issues && intent.potential_issues.length > 0) {
              reviewContent += `### Potential Issues\n`;
              for (const issue of intent.potential_issues) {
                reviewContent += `- ⚠️ ${issue}\n`;
              }
              reviewContent += `\n`;
            }

            if (intent.missing_considerations && intent.missing_considerations.length > 0) {
              reviewContent += `### Missing Considerations\n`;
              for (const consideration of intent.missing_considerations) {
                reviewContent += `- 💡 ${consideration}\n`;
              }
              reviewContent += `\n`;
            }

            if (intent.architectural_impact) {
              reviewContent += `### Architectural Impact\n${intent.architectural_impact}\n\n`;
            }

            if (intent.duration_ms) {
              reviewContent += `*Intent analysis completed in ${(intent.duration_ms / 1000).toFixed(1)}s (confidence: ${(intent.confidence * 100).toFixed(0)}%)*\n\n`;
            }
          } else {
            reviewContent += `⚠️ Intent analysis failed: ${intent.error || 'Unknown error'}\n\n`;
          }

          reviewContent += `---\n\n`;
        }

        // Context Extraction Info (if available)
        if (reviewResponse.context_extraction && reviewResponse.context_extraction.success) {
          const ctx = reviewResponse.context_extraction;
          reviewContent += `## 📁 Context Extraction\n\n`;
          reviewContent += `| Metric | Value |\n`;
          reviewContent += `|:-------|:------|\n`;
          reviewContent += `| Changed Files | ${ctx.changed_files_count} |\n`;
          reviewContent += `| Related Files | ${ctx.related_files_count} |\n`;
          if (ctx.languages_detected && ctx.languages_detected.length > 0) {
            reviewContent += `| Languages | ${ctx.languages_detected.join(', ')} |\n`;
          }
          reviewContent += `\n---\n\n`;
        }

        // Summary section
        reviewContent += `## 📝 Summary\n\n`;
        reviewContent += `${review.summary || 'Review completed'}\n\n`;

        // Assessment badge
        const assessmentEmoji = review.overall_assessment === 'APPROVE' ? '✅' :
                               review.overall_assessment === 'REQUEST_CHANGES' ? '⚠️' : '💬';
        reviewContent += `| Assessment | Score |\n`;
        reviewContent += `|:-----------|:------|\n`;
        reviewContent += `| ${assessmentEmoji} **${review.overall_assessment || 'COMMENT'}** | **${review.score || 'N/A'}**/10 |\n\n`;

        // Issues section
        if (review.issues && review.issues.length > 0) {
          reviewContent += `---\n\n`;
          reviewContent += `## 🔍 Issues Found (${review.issues.length})\n\n`;

          // Helper function to format a single issue
          const formatIssue = (issue: typeof review.issues[0]) => {
            let content = '';
            const lineInfo = issue.end_line
              ? ` (lines ${issue.line}-${issue.end_line})`
              : issue.line ? ` (line ${issue.line})` : '';
            content += `#### \`${issue.file}\`${lineInfo}\n\n`;
            content += `**Type:** ${issue.type}\n\n`;
            content += `> ${issue.description}\n\n`;
            if (issue.suggestion) {
              content += `💡 **Suggestion:** ${issue.suggestion}\n\n`;
            }
            if (issue.suggested_change) {
              content += `**Suggested Change:**\n\n\`\`\`\n${issue.suggested_change}\n\`\`\`\n\n`;
            }
            return content;
          };

          // Group issues by severity
          const highIssues = review.issues.filter(i => i.severity === 'HIGH');
          const mediumIssues = review.issues.filter(i => i.severity === 'MEDIUM');
          const lowIssues = review.issues.filter(i => i.severity === 'LOW');

          if (highIssues.length > 0) {
            reviewContent += `### 🔴 High Severity (${highIssues.length})\n\n`;
            for (const issue of highIssues) {
              reviewContent += formatIssue(issue);
            }
          }

          if (mediumIssues.length > 0) {
            reviewContent += `### 🟡 Medium Severity (${mediumIssues.length})\n\n`;
            for (const issue of mediumIssues) {
              reviewContent += formatIssue(issue);
            }
          }

          if (lowIssues.length > 0) {
            reviewContent += `### 🟢 Low Severity (${lowIssues.length})\n\n`;
            for (const issue of lowIssues) {
              reviewContent += formatIssue(issue);
            }
          }
        } else {
          reviewContent += `---\n\n`;
          reviewContent += `## 🔍 Issues Found\n\n`;
          reviewContent += `✨ No issues found!\n\n`;
        }

        // Positive feedback section
        if (review.positive_feedback && review.positive_feedback.length > 0) {
          reviewContent += `---\n\n`;
          reviewContent += `## ✅ Positive Aspects\n\n`;
          for (const feedback of review.positive_feedback) {
            reviewContent += `- ${feedback}\n`;
          }
          reviewContent += '\n';
        }

        // Suggestions section
        if (review.suggestions && review.suggestions.length > 0) {
          reviewContent += `---\n\n`;
          reviewContent += `## 💡 Suggestions for Improvement\n\n`;
          for (const suggestion of review.suggestions) {
            reviewContent += `- ${suggestion}\n`;
          }
          reviewContent += '\n';
        }

        // Footer with metadata
        if (reviewResponse.duration_ms) {
          reviewContent += `---\n\n`;
          reviewContent += `*⏱️ Review completed in ${(reviewResponse.duration_ms / 1000).toFixed(1)}s using ${provider}/${model}*\n`;
        }

        // Raw review if available and no structured data
        if (review.raw_review && !review.summary) {
          reviewContent = review.raw_review;
        }

        // Save review result for "Comment on GitHub" button
        setLastReviewResult(review);

      } else {
        reviewContent = `# ❌ Review Failed\n\n`;
        reviewContent += `**Error:** ${reviewResponse.error || 'Unknown error occurred during code review.'}\n\n`;
        reviewContent += `Please check your API keys and try again.`;
        setLastReviewResult(null);
      }

      // Save the review content to backend
      try {
        await updateMessageContent(conversation.id, assistantMsgId, reviewContent);
        console.log('[Chat] Review content saved to backend');
      } catch (saveError) {
        console.error('[Chat] Failed to save review content to backend:', saveError);
      }

      // Update the assistant message with the review content in local state
      // Use the dedicated function to avoid stale closure issues
      if (onUpdateMessageContent) {
        onUpdateMessageContent(conversation.id, assistantMsgId, reviewContent);
      }

    } catch (error) {
      console.error('[Chat] Code review failed:', error);

      // Update assistant message with error
      const errorContent = `❌ **Review Failed**\n\n${error instanceof Error ? error.message : 'Unknown error occurred'}`;

      // Save error content to backend
      try {
        await updateMessageContent(conversation.id, assistantMsgId, errorContent);
      } catch (saveError) {
        console.error('[Chat] Failed to save error content to backend:', saveError);
      }

      // Update local state with error message using dedicated function
      if (onUpdateMessageContent) {
        onUpdateMessageContent(conversation.id, assistantMsgId, errorContent);
      }
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Handle repo input key press
  const handleRepoKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddRepo();
    } else if (e.key === 'Escape') {
      setShowRepoInput(false);
      setRepoUrl('');
    }
  };

  // Handle reloading PRs for current repo
  const handleReloadPRs = async () => {
    if (!conversation.github_repo) return;

    setIsLoadingPRs(true);
    try {
      const { owner, name } = conversation.github_repo;
      console.log('[Chat] Reloading PRs for', owner, name);
      const prs = await listPullRequests(owner, name, 'open', 30);
      console.log('[Chat] Reloaded', prs.length, 'PRs');

      const pullRequests: PullRequest[] = prs.map(pr => ({
        id: pr.id,
        number: pr.number,
        title: pr.title,
        state: pr.state as 'open' | 'closed' | 'merged',
        author: pr.author,
        created_at: pr.created_at,
        updated_at: pr.updated_at,
        html_url: pr.html_url,
        head_branch: pr.head_branch,
        base_branch: pr.base_branch,
        additions: pr.additions,
        deletions: pr.deletions,
        changed_files: pr.changed_files,
      }));

      if (onUpdateConversation) {
        onUpdateConversation({ pull_requests: pullRequests });
      }
    } catch (error) {
      console.error('[Chat] Failed to reload PRs:', error);
      alert(`Failed to reload pull requests: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsLoadingPRs(false);
    }
  };

  // Handle posting comment to GitHub
  const handlePostComment = async () => {
    if (!conversation.github_repo || !conversation.selected_pr || !lastReviewResult) {
      alert('No review result available to post.');
      return;
    }

    setIsPostingComment(true);

    try {
      console.log('[Chat] Posting comment to GitHub...');
      const result = await postCommentToGitHub(
        conversation.github_repo.owner,
        conversation.github_repo.name,
        conversation.selected_pr.number,
        lastReviewResult
      );

      if (result.success) {
        const message = result.url
          ? `Successfully posted ${result.comment_count} comments to GitHub!`
          : `Posted ${result.comment_count} comments to GitHub.`;
        alert(message);

        // Open the PR in browser if URL is available
        if (result.url && window.electronAPI?.openExternal) {
          window.electronAPI.openExternal(result.url);
        }
      } else {
        alert(`Failed to post comments: ${result.error}`);
      }
    } catch (error) {
      console.error('[Chat] Failed to post comment:', error);
      alert(`Failed to post comment: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsPostingComment(false);
    }
  };

  // Check if repo is configured
  const hasRepo = !!conversation.github_repo;
  const hasPRs = (conversation.pull_requests?.length || 0) > 0;

  return (
    <div
      className="flex flex-col h-full"
      style={{ backgroundColor: 'var(--color-bg-window)' }}
    >
      {/* Chat Header */}
      <div
        className="flex items-center justify-between px-4 py-3 border-b"
        style={{ borderColor: 'var(--color-divider)' }}
      >
        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            {hasRepo && <GitBranch className="w-4 h-4" style={{ color: 'var(--color-accent)' }} />}
            <span className="font-semibold" style={{ color: 'var(--color-text-primary)' }}>
              {conversation.title}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
              {conversation.messages.length} messages
            </span>
            {/* Connection Status */}
            <div className="flex items-center gap-1">
              {isBackendConnected ? (
                <Wifi className="w-3 h-3 text-green-500" />
              ) : (
                <WifiOff className="w-3 h-3 text-red-500" />
              )}
              <span className="text-xs" style={{ color: isBackendConnected ? '#22c55e' : '#ef4444' }}>
                {isBackendConnected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {/* Settings Button */}
          {onOpenSettings && (
            <button
              onClick={onOpenSettings}
              className="p-2 rounded-md transition-colors"
              style={{ color: 'var(--color-text-secondary)' }}
              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--color-hover)'}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
            >
              <Settings className="w-5 h-5" />
            </button>
          )}
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
        {conversation.messages.length === 0 ? (
          <EmptyState hasRepo={hasRepo} />
        ) : (
          <div className="space-y-4 max-w-4xl mx-auto">
            {conversation.messages.map((msg) => (
              <div
                key={msg.id}
                className={clsx(
                  "flex w-full",
                  msg.role === 'user' ? "justify-end" : "justify-start"
                )}
              >
                <div className={clsx(
                  "flex max-w-[80%] items-start gap-3",
                  msg.role === 'user' ? "flex-row-reverse" : "flex-row"
                )}>
                  {/* Avatar */}
                  <div
                    className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center overflow-hidden"
                    style={{
                      backgroundColor: msg.role === 'user'
                        ? '#22c55e'
                        : 'transparent'
                    }}
                  >
                    {msg.role === 'user' ? (
                      <User className="w-4 h-4 text-white" />
                    ) : (
                      <img src={logoImage} alt="DiffCOT" className="w-8 h-8 object-contain" />
                    )}
                  </div>

                  {/* Content */}
                  <div className="flex flex-col">
                    <div
                      className={clsx(
                        "px-4 py-2.5 rounded-2xl",
                        msg.role === 'user' ? "rounded-tr-sm" : "rounded-tl-sm"
                      )}
                      style={{
                        backgroundColor: msg.role === 'user'
                          ? 'var(--color-bg-user-bubble)'
                          : 'var(--color-bg-assistant-bubble)',
                        color: msg.role === 'user'
                          ? 'var(--color-text-user)'
                          : 'var(--color-text-primary)'
                      }}
                    >
                      {/* Attachments Display */}
                      {msg.attachments && msg.attachments.length > 0 && (
                        <div className={clsx(
                          "flex flex-wrap gap-2 mb-2",
                          msg.role === 'user' ? "justify-end" : "justify-start"
                        )}>
                          {msg.attachments.map((att) => (
                            <AttachmentCard
                              key={att.id}
                              attachment={att}
                              isUserMessage={msg.role === 'user'}
                            />
                          ))}
                        </div>
                      )}

                      {/* Message Content */}
                      {msg.role === 'user' ? (
                        msg.content ? (
                          <p className="text-[15px] leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                        ) : null
                      ) : msg.content === '' ? (
                        <ThinkingAnimation />
                      ) : (
                        <div className="prose max-w-none text-[15px]">
                          <ReactMarkdown>{msg.content}</ReactMarkdown>
                        </div>
                      )}
                    </div>
                    {(msg.content !== '' || (msg.attachments && msg.attachments.length > 0)) && (
                      <span
                        className={clsx(
                          "text-xs mt-1",
                          msg.role === 'user' ? "text-right" : "text-left"
                        )}
                        style={{ color: 'var(--color-text-secondary)' }}
                      >
                        {format(new Date(msg.timestamp), 'HH:mm')}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Divider */}
      <div className="h-px" style={{ backgroundColor: 'var(--color-divider)' }} />

      {/* Input Area - Different modes based on state */}
      <div
        className="px-4 py-3"
        style={{ backgroundColor: 'var(--color-bg-sidebar)' }}
      >
        <div className="flex flex-col gap-3 max-w-4xl mx-auto">
          {/* GitHub Repo URL Input Modal */}
          {showRepoInput && (
            <div
              className="flex items-center gap-2 p-3 rounded-lg"
              style={{ backgroundColor: 'var(--color-bg-input)' }}
            >
              <GitBranch className="w-5 h-5 flex-shrink-0" style={{ color: 'var(--color-text-secondary)' }} />
              <input
                ref={repoInputRef}
                type="text"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                onKeyDown={handleRepoKeyDown}
                placeholder="Enter GitHub repository URL (e.g., https://github.com/owner/repo)"
                className="flex-1 bg-transparent text-sm outline-none"
                style={{ color: 'var(--color-text-primary)' }}
              />
              <button
                onClick={() => {
                  setShowRepoInput(false);
                  setRepoUrl('');
                }}
                className="p-1 rounded-full transition-colors"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                <X className="w-4 h-4" />
              </button>
              <button
                onClick={handleAddRepo}
                disabled={!repoUrl.trim() || isLoadingPRs}
                className="px-3 py-1.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                style={{
                  backgroundColor: 'var(--color-accent)',
                  color: 'white',
                }}
              >
                {isLoadingPRs ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  'Add'
                )}
              </button>
            </div>
          )}

          {/* Main Input Area */}
          {!hasRepo ? (
            /* No repo configured - show add repo button */
            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowRepoInput(true)}
                className="flex items-center gap-2 px-4 py-2.5 rounded-lg transition-colors"
                style={{
                  backgroundColor: 'var(--color-bg-input)',
                  color: 'var(--color-text-secondary)',
                }}
                onMouseEnter={(e) => e.currentTarget.style.color = 'var(--color-text-primary)'}
                onMouseLeave={(e) => e.currentTarget.style.color = 'var(--color-text-secondary)'}
              >
                <Plus className="w-5 h-5" />
                <span className="text-sm">Add GitHub Repository</span>
              </button>
            </div>
          ) : !hasPRs ? (
            /* Repo configured but no PRs loaded - offer to reload */
            <div className="flex flex-col items-center justify-center py-4 gap-3">
              {isLoadingPRs ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" style={{ color: 'var(--color-text-secondary)' }} />
                  <span className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                    Loading pull requests...
                  </span>
                </>
              ) : (
                <>
                  <span className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                    No pull requests found or failed to load
                  </span>
                  <button
                    onClick={handleReloadPRs}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                    style={{
                      backgroundColor: 'var(--color-accent)',
                      color: 'white',
                    }}
                  >
                    <GitPullRequest className="w-4 h-4" />
                    Reload Pull Requests
                  </button>
                </>
              )}
            </div>
          ) : (
            /* PRs loaded - show PR selection and start analysis button */
            <div className="space-y-3">
              {/* PR Selection */}
              <div className="space-y-2">
                <label className="text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>
                  Select Pull Request to Review
                </label>
                <div className="space-y-1 max-h-48 overflow-y-auto custom-scrollbar">
                  {conversation.pull_requests?.map((pr) => (
                    <button
                      key={pr.id}
                      onClick={() => setSelectedPRId(pr.id)}
                      className={clsx(
                        "w-full flex items-start gap-3 p-3 rounded-lg transition-colors text-left",
                        selectedPRId === pr.id && "ring-2 ring-[var(--color-accent)]"
                      )}
                      style={{
                        backgroundColor: selectedPRId === pr.id
                          ? 'var(--color-selected)'
                          : 'var(--color-bg-input)',
                      }}
                    >
                      <GitPullRequest
                        className="w-5 h-5 flex-shrink-0 mt-0.5"
                        style={{ color: pr.state === 'open' ? '#22c55e' : 'var(--color-text-secondary)' }}
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium truncate" style={{ color: 'var(--color-text-primary)' }}>
                            #{pr.number} {pr.title}
                          </span>
                          {selectedPRId === pr.id && (
                            <Check className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--color-accent)' }} />
                          )}
                        </div>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                            {pr.head_branch} → {pr.base_branch}
                          </span>
                          {(pr.additions != null || pr.deletions != null || pr.changed_files != null) && (
                            <>
                              <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                                •
                              </span>
                              <span className="text-xs text-green-500">+{pr.additions ?? '—'}</span>
                              <span className="text-xs text-red-500">-{pr.deletions ?? '—'}</span>
                              <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                                ({pr.changed_files ?? '—'} files)
                              </span>
                            </>
                          )}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Start Analysis Button */}
              <button
                onClick={handleStartAnalysis}
                disabled={!selectedPRId || isAnalyzing || isGenerating}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium transition-colors disabled:opacity-50"
                style={{
                  backgroundColor: selectedPRId ? 'var(--color-accent)' : 'var(--color-bg-input)',
                  color: selectedPRId ? 'white' : 'var(--color-text-secondary)',
                }}
              >
                {isAnalyzing || isGenerating ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>Analyzing...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-5 h-5" />
                    <span>Start Analysis</span>
                  </>
                )}
              </button>

              {/* Comment on GitHub Button - shows after review is complete */}
              {lastReviewResult && conversation.selected_pr && (
                <button
                  onClick={handlePostComment}
                  disabled={isPostingComment}
                  className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium transition-colors disabled:opacity-50 mt-2"
                  style={{
                    backgroundColor: 'var(--color-bg-input)',
                    color: 'var(--color-text-primary)',
                    border: '1px solid var(--color-divider)',
                  }}
                >
                  {isPostingComment ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      <span>Posting to GitHub...</span>
                    </>
                  ) : (
                    <>
                      <MessageSquare className="w-5 h-5" />
                      <span>Comment on GitHub</span>
                    </>
                  )}
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// Empty State Component
const EmptyState: React.FC<{ hasRepo: boolean }> = ({ hasRepo }) => (
  <div className="flex flex-col items-center justify-center h-full pt-20">
    <div
      className="w-20 h-20 rounded-full flex items-center justify-center mb-5 overflow-hidden"
      style={{ backgroundColor: hasRepo ? 'var(--color-text-secondary)' : 'transparent', opacity: hasRepo ? 0.3 : 1 }}
    >
      {hasRepo ? (
        <GitPullRequest className="w-10 h-10" style={{ color: 'var(--color-text-secondary)' }} />
      ) : (
        <img src={logoImage} alt="DiffCOT" className="w-24 h-24 object-contain" />
      )}
    </div>
    <h2
      className="text-xl font-medium mb-2"
      style={{ color: 'var(--color-text-secondary)' }}
    >
      {hasRepo ? 'Select a Pull Request' : 'Add a GitHub Repository'}
    </h2>
    <p
      className="text-sm"
      style={{ color: 'var(--color-text-secondary)', opacity: 0.7 }}
    >
      {hasRepo
        ? 'Choose a PR from the list below to start code review'
        : 'Click the + button below to add a repository'}
    </p>
  </div>
);

// Thinking Animation
const ThinkingAnimation: React.FC = () => {
  const [dotCount, setDotCount] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setDotCount(prev => (prev + 1) % 3);
    }, 500);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex items-center gap-1">
      <span className="text-[15px]" style={{ color: 'var(--color-text-secondary)' }}>Analyzing</span>
      <span className="text-[15px]" style={{ color: 'var(--color-text-secondary)' }}>{'.'.repeat(dotCount + 1)}</span>
    </div>
  );
};
