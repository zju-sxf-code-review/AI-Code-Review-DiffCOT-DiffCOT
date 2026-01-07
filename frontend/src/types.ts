export interface Attachment {
  id: string;
  name: string;
  type: string;
  url?: string;
  fileName?: string;
  fileType?: string;
  fileSize?: number;
  data?: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  attachments: Attachment[];
  model_used?: string;
  provider_used?: string;
  tokens_used?: number;
}

// GitHub Pull Request interface
export interface PullRequest {
  id: number;
  number: number;
  title: string;
  state: 'open' | 'closed' | 'merged';
  author: string;
  created_at: string;
  updated_at: string;
  html_url: string;
  head_branch: string;
  base_branch: string;
  additions?: number;
  deletions?: number;
  changed_files?: number;
}

// GitHub Repository interface
export interface GitHubRepo {
  url: string;
  owner: string;
  name: string;
  full_name: string;
  default_branch?: string;
}

// Review Issue (for code review results)
export interface ReviewIssue {
  severity: string;
  type: string;
  file: string;
  line?: number | string;
  end_line?: number | string;
  description: string;
  suggestion?: string;
  suggested_change?: string;
}

// Code Review Result (for Comment on GitHub button)
export interface CodeReviewResultType {
  summary: string;
  overall_assessment: string;
  score: number;
  issues: ReviewIssue[];
  positive_feedback: string[];
  suggestions: string[];
  raw_review?: string;
}

export interface Conversation {
  id: string;
  title: string;
  createdAt: Date;
  updatedAt: Date;
  messages: Message[];
  provider?: string;
  model_name?: string;
  system_prompt?: string;
  // New fields for code review
  github_repo?: GitHubRepo;
  pull_requests?: PullRequest[];
  selected_pr?: PullRequest;
  // Analysis state (persisted across component re-renders)
  isAnalyzing?: boolean;
  // Last review result for "Comment on GitHub" button (persisted)
  lastReviewResult?: CodeReviewResultType;
}
