import { useState, useEffect, useCallback } from 'react';
import { Sidebar } from './components/Sidebar';
import { Chat } from './components/Chat';
import { Welcome } from './components/Welcome';
import { Settings } from './components/Settings';
import { SemgrepRules } from './components/SemgrepRules';
import type { Conversation, Message, Attachment } from './types';
import { v4 as uuidv4 } from 'uuid';
import {
  streamMessage,
  checkHealth,
  listConversations,
  createConversation,
  getConversation,
  updateConversation as updateConversationApi,
  deleteConversation as deleteConversationApi,
  addMessage,
  updateMessageContent,
  uploadDocument,
  waitForDocumentProcessing,
  submitUrl,
  isValidUrl,
} from './services/api';
import type { AttachmentInfo, DocumentUploadResponse } from './services/api';

function App() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [showSemgrepRules, setShowSemgrepRules] = useState(false);
  const [isBackendConnected, setIsBackendConnected] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState('');
  const [selectedModel, setSelectedModel] = useState('');
  const [settingsVersion, setSettingsVersion] = useState(0);
  const [isLoading, setIsLoading] = useState(true);

  // Load conversations from backend
  const loadConversations = useCallback(async () => {
    try {
      const convList = await listConversations();
      const loadedConversations: Conversation[] = convList.map(conv => ({
        id: conv.id,
        title: conv.title,
        createdAt: new Date(conv.created_at),
        updatedAt: new Date(conv.updated_at),
        messages: [],
        provider: conv.provider,
        model_name: conv.model_name,
      }));
      setConversations(loadedConversations);
    } catch (error) {
      console.error('Failed to load conversations:', error);
    }
  }, []);

  // Check backend connection and load conversations on mount
  useEffect(() => {
    const init = async () => {
      const connected = await checkHealth();
      setIsBackendConnected(connected);

      if (connected) {
        await loadConversations();

        // Load settings to get default provider
        try {
          const response = await fetch('http://127.0.0.1:8765/api/settings');
          if (response.ok) {
            const settings = await response.json();
            // Find first enabled provider
            const enabledProvider = settings.providers?.find((p: { isEnabled: boolean }) => p.isEnabled);
            if (enabledProvider) {
              setSelectedProvider(enabledProvider.provider);
              setSelectedModel(enabledProvider.selectedChatModel || '');
            } else if (settings.providers?.length > 0) {
              // If no provider is enabled, use the first one
              const firstProvider = settings.providers[0];
              setSelectedProvider(firstProvider.provider);
              setSelectedModel(firstProvider.selectedChatModel || '');
            }
          }
        } catch (error) {
          console.error('Failed to load settings for provider:', error);
        }
      }
      setIsLoading(false);
    };
    init();
    
    // Check connection every 10 seconds
    const interval = setInterval(async () => {
      const connected = await checkHealth();
      setIsBackendConnected(connected);
    }, 10000);
    
    return () => clearInterval(interval);
  }, [loadConversations]);

  // Load full conversation when selected
  const loadFullConversation = async (conversationId: string) => {
    try {
      const conv = await getConversation(conversationId);

      // Parse metadata if present
      let metadata: {
        github_repo?: Conversation['github_repo'];
        pull_requests?: Conversation['pull_requests'];
        selected_pr?: Conversation['selected_pr'];
        isAnalyzing?: boolean;
      } = {};
      if (conv.metadata) {
        try {
          metadata = JSON.parse(conv.metadata);
        } catch (e) {
          console.error('Failed to parse conversation metadata:', e);
        }
      }

      const isCurrentlyAnalyzing = metadata.isAnalyzing ?? false;

      setConversations(prev => prev.map(c => {
        if (c.id === conversationId) {
          // Convert messages from backend
          const messages = conv.messages.map(msg => ({
            id: msg.id,
            role: msg.role as 'user' | 'assistant',
            content: msg.content,
            timestamp: new Date(msg.timestamp),
            attachments: [],
            model_used: msg.model_used,
            provider_used: msg.provider_used,
            tokens_used: msg.tokens_used,
          }));

          // Only filter out empty messages if NOT currently analyzing
          // When analyzing, we need to keep the empty assistant message for the loading animation
          const filteredMessages = isCurrentlyAnalyzing
            ? messages  // Keep all messages including empty ones
            : messages.filter(msg => msg.content !== '');

          return {
            ...c,
            messages: filteredMessages,
            // Restore metadata
            github_repo: metadata.github_repo,
            pull_requests: metadata.pull_requests,
            selected_pr: metadata.selected_pr,
            isAnalyzing: isCurrentlyAnalyzing,
          };
        }
        return c;
      }));
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  };

  // Handle conversation selection
  const handleSelectConversation = async (id: string) => {
    setSelectedId(id);
    await loadFullConversation(id);
  };

  const selectedConversation = conversations.find(c => c.id === selectedId);

  const handleNewChat = async () => {
    if (!isBackendConnected) {
      const newConv: Conversation = {
        id: uuidv4(),
        title: 'New Repo',
        createdAt: new Date(),
        updatedAt: new Date(),
        messages: [],
        provider: selectedProvider,
        model_name: selectedModel,
      };
      setConversations(prev => [newConv, ...prev]);
      setSelectedId(newConv.id);
      return;
    }

    try {
      const conv = await createConversation('New Repo', selectedProvider, selectedModel);
      const newConv: Conversation = {
        id: conv.id,
        title: conv.title,
        createdAt: new Date(conv.created_at),
        updatedAt: new Date(conv.updated_at),
        messages: [],
        provider: conv.provider,
        model_name: conv.model_name,
      };
      setConversations(prev => [newConv, ...prev]);
      setSelectedId(newConv.id);
    } catch (error) {
      console.error('Failed to create conversation:', error);
    }
  };

  const handleDeleteChat = async (id: string) => {
    if (isBackendConnected) {
      try {
        await deleteConversationApi(id);
      } catch (error) {
        console.error('Failed to delete conversation:', error);
      }
    }
    setConversations(prev => prev.filter(c => c.id !== id));
    if (selectedId === id) {
      setSelectedId(null);
    }
  };

  const handleRenameChat = async (id: string, newTitle: string) => {
    if (isBackendConnected) {
      try {
        await updateConversationApi(id, { title: newTitle });
      } catch (error) {
        console.error('Failed to rename conversation:', error);
      }
    }
    setConversations(prev => prev.map(c =>
      c.id === id ? { ...c, title: newTitle } : c
    ));
  };

  // Update conversation with partial data (for GitHub repo, PRs, etc.)
  const handleUpdateConversation = useCallback((updates: Partial<Conversation>) => {
    if (!selectedId) return;

    // Use functional update to access the latest state
    setConversations(prev => {
      const updatedConversations = prev.map(c => {
        if (c.id === selectedId) {
          return { ...c, ...updates, updatedAt: new Date() };
        }
        return c;
      });

      // Sync to backend if connected (inside the functional update to access merged state)
      if (isBackendConnected) {
        const backendUpdates: { title?: string; metadata?: string } = {};
        const currentConv = prev.find(c => c.id === selectedId);
        const mergedConv = { ...currentConv, ...updates };

        // Update title if changed
        if (updates.title) {
          backendUpdates.title = updates.title;
        }

        // Serialize metadata (github_repo, pull_requests, selected_pr, isAnalyzing) if any changed
        if (updates.github_repo !== undefined || updates.pull_requests !== undefined ||
            updates.selected_pr !== undefined || updates.isAnalyzing !== undefined) {
          const metadata = {
            github_repo: mergedConv.github_repo,
            pull_requests: mergedConv.pull_requests,
            selected_pr: mergedConv.selected_pr,
            isAnalyzing: mergedConv.isAnalyzing,
          };
          backendUpdates.metadata = JSON.stringify(metadata);
        }

        if (Object.keys(backendUpdates).length > 0) {
          updateConversationApi(selectedId, backendUpdates).catch(console.error);
        }
      }

      return updatedConversations;
    });
  }, [selectedId, isBackendConnected]);

  // Update a message in local state (used for streaming updates)
  const updateMessageLocal = useCallback((conversationId: string, messageId: string, content: string) => {
    setConversations(prev => prev.map(c => {
      if (c.id === conversationId) {
        return {
          ...c,
          messages: c.messages.map(m =>
            m.id === messageId ? { ...m, content } : m
          ),
          updatedAt: new Date()
        };
      }
      return c;
    }));
  }, []);

  // Add messages to a conversation (for review workflow)
  const addMessagesToConversation = useCallback((conversationId: string, newMessages: Message[]) => {
    setConversations(prev => prev.map(c => {
      if (c.id === conversationId) {
        // Filter out any existing messages with the same IDs (to avoid duplicates)
        const existingIds = new Set(newMessages.map(m => m.id));
        const filteredExisting = c.messages.filter(m => !existingIds.has(m.id));
        return {
          ...c,
          messages: [...filteredExisting, ...newMessages],
          updatedAt: new Date()
        };
      }
      return c;
    }));
  }, []);

  const handleSendMessage = async (text: string, files: File[]) => {
    if (!selectedId) return;

    console.log(`[App] Sending message with ${files.length} file(s):`, files.map(f => f.name));

    // Upload files first and get document IDs (RAG mode)
    const uploadedDocs: DocumentUploadResponse[] = [];
    const attachments: Attachment[] = [];
    const attachmentInfos: AttachmentInfo[] = [];

    // Check if text contains URLs and process them for RAG
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    const urls = text.match(urlRegex) || [];
    
    for (const url of urls) {
      if (isValidUrl(url)) {
        try {
          console.log(`[App] Submitting URL for RAG processing: ${url}`);
          
          const uploadResult = await submitUrl(url, 'default', selectedId);
          uploadedDocs.push(uploadResult);
          
          // Wait for URL processing to complete
          console.log(`[App] Waiting for URL processing: ${uploadResult.id}`);
          try {
            await waitForDocumentProcessing(
              uploadResult.id,
              (status) => {
                console.log(`[App] URL ${url} processing status: ${status.status}`);
              },
              120,  // max 120 attempts (2 minutes)
              1000  // 1 second interval
            );
            console.log(`[App] URL processing completed: ${url}`);
          } catch (processingError) {
            console.warn(`[App] URL processing incomplete: ${url}`, processingError);
          }
          
          // Create attachment info with document ID for chat API
          attachmentInfos.push({
            file_name: url,
            file_type: 'url',
            file_size: 0,
            document_id: uploadResult.id,
          });
          
          console.log(`[App] URL submitted successfully: ${url} -> document_id: ${uploadResult.id}`);
        } catch (error) {
          console.error(`[App] Failed to submit URL ${url}:`, error);
        }
      }
    }

    for (const file of files) {
      try {
        console.log(`[App] Uploading file for RAG processing: ${file.name}`);
        
        // Upload to backend for RAG processing
        // Use 'default' user_id to match the provider settings stored in database
        const uploadResult = await uploadDocument(file, 'default', selectedId);
        uploadedDocs.push(uploadResult);
        
        // Wait for document processing to complete before sending to LLM
        console.log(`[App] Waiting for document processing: ${uploadResult.id}`);
        try {
          await waitForDocumentProcessing(
            uploadResult.id,
            (status) => {
              console.log(`[App] Document ${file.name} processing status: ${status.status}`);
            },
            120,  // max 120 attempts (2 minutes)
            1000  // 1 second interval
          );
          console.log(`[App] Document processing completed: ${file.name}`);
        } catch (processingError) {
          console.warn(`[App] Document processing incomplete: ${file.name}`, processingError);
          // Continue anyway - the document may still be usable
        }
        
        // Create attachment with document ID
        attachments.push({
          id: uploadResult.id,
          name: file.name,
          type: file.type,
          url: URL.createObjectURL(file), // Local preview URL
          fileSize: file.size,
        });
        
        // Create attachment info with document ID for chat API
        attachmentInfos.push({
          file_name: file.name,
          file_type: file.type,
          file_size: file.size,
          document_id: uploadResult.id,
        });
        
        console.log(`[App] File uploaded successfully: ${file.name} -> document_id: ${uploadResult.id}`);
      } catch (error) {
        console.error(`[App] Failed to upload file ${file.name}:`, error);
        // Continue with other files, but add without document_id
        attachments.push({
          id: uuidv4(),
          name: file.name,
          type: file.type,
          url: URL.createObjectURL(file),
          fileSize: file.size,
        });
        attachmentInfos.push({
          file_name: file.name,
          file_type: file.type,
          file_size: file.size,
        });
      }
    }

    // Add user message to backend
    let userMsgId = uuidv4();
    if (isBackendConnected) {
      try {
        const userMsgResponse = await addMessage(selectedId, 'user', text);
        userMsgId = userMsgResponse.id;
      } catch (error) {
        console.error('Failed to save user message:', error);
      }
    }

    const userMsg: Message = {
      id: userMsgId,
      role: 'user',
      content: text,
      timestamp: new Date(),
      attachments
    };

    // Create placeholder for AI response in backend
    let aiMsgId = uuidv4();
    if (isBackendConnected) {
      try {
        const aiMsgResponse = await addMessage(selectedId, 'assistant', '');
        aiMsgId = aiMsgResponse.id;
      } catch (error) {
        console.error('Failed to create assistant message placeholder:', error);
      }
    }

    const aiMsg: Message = {
      id: aiMsgId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      attachments: []
    };

    // Add messages to local state
    setConversations(prev => prev.map(c => {
      if (c.id === selectedId) {
        const newTitle = c.messages.length === 0 ? (text.slice(0, 30) || files[0]?.name.slice(0, 30) || 'New Repo') : c.title;
        if (c.messages.length === 0 && isBackendConnected) {
          updateConversationApi(selectedId, { title: newTitle }).catch(console.error);
        }
        return {
          ...c,
          messages: [...c.messages, userMsg, aiMsg],
          updatedAt: new Date(),
          title: newTitle
        };
      }
      return c;
    }));

    // Get current conversation history
    const currentConv = conversations.find(c => c.id === selectedId);
    const history = currentConv?.messages || [];

    try {
      // Use streaming API with attachments
      let streamedContent = '';
      const stream = streamMessage(
        text,
        selectedId,
        history,
        selectedProvider,
        selectedModel,
        attachmentInfos  // Pass attachment info to API
      );

      for await (const chunk of stream) {
        if (!chunk.is_final) {
          streamedContent += chunk.content;
          updateMessageLocal(selectedId, aiMsgId, streamedContent);
        }
      }

      // Save final content to backend
      if (isBackendConnected && streamedContent) {
        try {
          await updateMessageContent(selectedId, aiMsgId, streamedContent);
        } catch (error) {
          console.error('Failed to save assistant message:', error);
        }
      }
    } catch (error) {
      console.error('API Error:', error);
      const errorContent = `⚠️ Error: ${error instanceof Error ? error.message : 'Unknown error'}\n\nPlease make sure the backend server is running at http://127.0.0.1:8765`;
      updateMessageLocal(selectedId, aiMsgId, errorContent);
      
      if (isBackendConnected) {
        try {
          await updateMessageContent(selectedId, aiMsgId, errorContent);
        } catch (e) {
          console.error('Failed to save error message:', e);
        }
      }
    }
  };

  const handleModelChange = (provider: string, model: string) => {
    setSelectedProvider(provider);
    setSelectedModel(model);
  };

  if (isLoading) {
    return (
      <div 
        className="flex h-screen w-screen items-center justify-center"
        style={{ backgroundColor: 'var(--color-bg-window)' }}
      >
        <div className="text-center">
          <div className="animate-spin w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full mx-auto mb-4" />
          <p style={{ color: 'var(--color-text-secondary)' }}>Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div 
      className="flex h-screen w-screen overflow-hidden"
      style={{ backgroundColor: 'var(--color-bg-window)' }}
    >
      {/* Sidebar */}
      <Sidebar
        conversations={conversations}
        selectedId={selectedId}
        onSelect={handleSelectConversation}
        onNewChat={handleNewChat}
        onDelete={handleDeleteChat}
        onRename={handleRenameChat}
        onOpenSemgrepRules={() => setShowSemgrepRules(true)}
      />

      {/* Main Content */}
      <div
        className="flex-1 flex flex-col h-full overflow-hidden"
        style={{ backgroundColor: 'var(--color-bg-window)' }}
      >
        {showSemgrepRules ? (
          <SemgrepRules onBack={() => setShowSemgrepRules(false)} />
        ) : selectedConversation ? (
          <Chat
            key={selectedConversation.id}
            conversation={selectedConversation}
            onSendMessage={handleSendMessage}
            onOpenSettings={() => setShowSettings(true)}
            selectedProvider={selectedProvider}
            selectedModel={selectedModel}
            onModelChange={handleModelChange}
            isBackendConnected={isBackendConnected}
            settingsVersion={settingsVersion}
            onUpdateConversation={handleUpdateConversation}
            onAddMessages={addMessagesToConversation}
            onUpdateMessageContent={updateMessageLocal}
          />
        ) : (
          <Welcome
            onNewChat={handleNewChat}
            onOpenSettings={() => setShowSettings(true)}
          />
        )}
      </div>

      {/* Settings Modal */}
      <Settings
        isOpen={showSettings}
        onClose={() => {
          setShowSettings(false);
          setSettingsVersion(v => v + 1); // Trigger model list refresh
        }}
      />
    </div>
  );
}

export default App;
