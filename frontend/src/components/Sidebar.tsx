import React, { useState } from 'react';
import { SquarePen, Search, XCircle, MoreHorizontal, Pencil, Trash, MessageSquare, Shield } from 'lucide-react';
import type { Conversation } from '../types';
import { formatDistanceToNow } from 'date-fns';
import clsx from 'clsx';

interface SidebarProps {
  conversations: Conversation[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onNewChat: () => void;
  onDelete: (id: string) => void;
  onRename: (id: string, newTitle: string) => void;
  onOpenSemgrepRules?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  conversations,
  selectedId,
  onSelect,
  onNewChat,
  onDelete,
  onRename,
  onOpenSemgrepRules,
}) => {
  const [searchText, setSearchText] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [contextMenuId, setContextMenuId] = useState<string | null>(null);

  const filteredConversations = searchText
    ? conversations.filter(c => c.title.toLowerCase().includes(searchText.toLowerCase()))
    : conversations;

  const handleStartRename = (conv: Conversation, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(conv.id);
    setEditTitle(conv.title);
    setContextMenuId(null);
  };

  const handleFinishRename = () => {
    if (editingId && editTitle.trim()) {
      onRename(editingId, editTitle.trim());
    }
    setEditingId(null);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleFinishRename();
    } else if (e.key === 'Escape') {
      setEditingId(null);
    }
  };

  return (
    <div 
      className="flex flex-col h-full w-[260px] border-r"
      style={{ 
        backgroundColor: 'var(--color-bg-sidebar)',
        borderColor: 'var(--color-divider)',
        color: 'var(--color-text-primary)'
      }}
    >
      {/* New Repo Button */}
      <div className="px-3 pt-8 pb-2">
        <button
          onClick={onNewChat}
          className="flex items-center w-full px-3 py-2.5 text-sm font-medium rounded-lg transition-colors"
          style={{
            backgroundColor: 'var(--color-bg-assistant-bubble)',
          }}
          onMouseEnter={(e) => e.currentTarget.style.opacity = '0.8'}
          onMouseLeave={(e) => e.currentTarget.style.opacity = '1'}
        >
          <SquarePen className="w-4 h-4 mr-3" style={{ color: 'var(--color-text-secondary)' }} />
          New Repo
        </button>
      </div>

      {/* Search Bar */}
      <div className="px-3 pb-2">
        <div 
          className="flex items-center px-2 py-1.5 rounded-lg"
          style={{ backgroundColor: 'var(--color-bg-input)' }}
        >
          <Search className="w-4 h-4 mr-2" style={{ color: 'var(--color-text-secondary)' }} />
          <input
            type="text"
            placeholder="Search repositories..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            className="flex-1 bg-transparent text-sm outline-none placeholder-opacity-50"
            style={{ color: 'var(--color-text-primary)' }}
          />
          {searchText && (
            <button onClick={() => setSearchText('')} className="p-0.5">
              <XCircle className="w-4 h-4" style={{ color: 'var(--color-text-secondary)' }} />
            </button>
          )}
        </div>
      </div>

      {/* Conversation List */}
      <div className="flex-1 overflow-y-auto custom-scrollbar px-2">
        {filteredConversations.map((conv) => (
          <div
            key={conv.id}
            className={clsx(
              'group relative flex items-center px-3 py-2.5 rounded-lg cursor-pointer select-none transition-colors mb-1'
            )}
            style={{
              backgroundColor: selectedId === conv.id ? 'var(--color-selected)' : 'transparent',
            }}
            onClick={() => onSelect(conv.id)}
            onContextMenu={(e) => {
              e.preventDefault();
              setContextMenuId(conv.id);
            }}
            onMouseEnter={(e) => {
              if (selectedId !== conv.id) {
                e.currentTarget.style.backgroundColor = 'var(--color-hover)';
              }
            }}
            onMouseLeave={(e) => {
              if (selectedId !== conv.id) {
                e.currentTarget.style.backgroundColor = 'transparent';
              }
            }}
          >
            <MessageSquare 
              className="w-4 h-4 mr-3 flex-shrink-0" 
              style={{ color: 'var(--color-text-secondary)' }}
            />
            
            {editingId === conv.id ? (
              <input
                autoFocus
                type="text"
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                onBlur={handleFinishRename}
                onKeyDown={handleKeyDown}
                onClick={(e) => e.stopPropagation()}
                className="flex-1 px-2 py-0.5 rounded text-sm outline-none"
                style={{ 
                  backgroundColor: 'var(--color-bg-input)',
                  color: 'var(--color-text-primary)',
                  border: '1px solid var(--color-divider)'
                }}
              />
            ) : (
              <div className="flex-1 min-w-0">
                <div className="text-sm truncate" style={{ color: 'var(--color-text-primary)' }}>
                  {conv.title}
                </div>
                <div className="text-xs mt-0.5" style={{ color: 'var(--color-text-secondary)' }}>
                  {formatDistanceToNow(conv.updatedAt, { addSuffix: true })}
                </div>
              </div>
            )}

            {/* Context Menu Trigger */}
            {selectedId === conv.id && !editingId && (
               <div className="relative ml-2">
                 <button
                   onClick={(e) => {
                     e.stopPropagation();
                     setContextMenuId(contextMenuId === conv.id ? null : conv.id);
                   }}
                   className="p-1 rounded transition-colors"
                   style={{ color: 'var(--color-text-secondary)' }}
                   onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--color-hover)'}
                   onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                 >
                   <MoreHorizontal className="w-4 h-4" />
                 </button>
                 
                 {contextMenuId === conv.id && (
                   <div 
                     className="absolute right-0 top-full mt-1 w-36 rounded-lg shadow-xl z-50 py-1"
                     style={{ 
                       backgroundColor: 'var(--color-bg-window)',
                       border: '1px solid var(--color-divider)'
                     }}
                   >
                     <button
                       onClick={(e) => handleStartRename(conv, e)}
                       className="flex items-center w-full px-3 py-2 text-sm transition-colors"
                       style={{ color: 'var(--color-text-primary)' }}
                       onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--color-hover)'}
                       onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                     >
                       <Pencil className="w-4 h-4 mr-2" />
                       Rename
                     </button>
                     <div className="h-px mx-2 my-1" style={{ backgroundColor: 'var(--color-divider)' }} />
                     <button
                       onClick={(e) => {
                         e.stopPropagation();
                         onDelete(conv.id);
                         setContextMenuId(null);
                       }}
                       className="flex items-center w-full px-3 py-2 text-sm text-red-500 transition-colors"
                       onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--color-hover)'}
                       onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                     >
                       <Trash className="w-4 h-4 mr-2" />
                       Delete
                     </button>
                   </div>
                 )}
               </div>
            )}
          </div>
        ))}
      </div>

      {/* Bottom section - Semgrep Rules button */}
      <div className="px-3 py-3 border-t" style={{ borderColor: 'var(--color-divider)' }}>
        <button
          onClick={onOpenSemgrepRules}
          className="flex items-center w-full px-3 py-2 text-sm rounded-lg transition-colors"
          style={{ color: 'var(--color-text-secondary)' }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = 'var(--color-hover)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'transparent';
          }}
        >
          <Shield className="w-4 h-4 mr-3" />
          Semgrep Rules
        </button>
      </div>

      {/* Click outside to close context menu */}
      {contextMenuId && (
        <div 
          className="fixed inset-0 z-40" 
          onClick={() => setContextMenuId(null)}
        />
      )}
    </div>
  );
};
