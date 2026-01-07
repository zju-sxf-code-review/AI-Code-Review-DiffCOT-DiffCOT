import React from 'react';
import logoImage from '../assets/logo.png';

interface WelcomeProps {
  onNewChat: () => void;
  onOpenSettings: () => void;
}

export const Welcome: React.FC<WelcomeProps> = ({ onNewChat }) => {
  return (
    <div
      className="flex flex-col items-center justify-center h-full"
      style={{ backgroundColor: 'var(--color-bg-window)' }}
    >
      {/* Logo */}
      <div className="mb-6 w-32 h-32 rounded-full overflow-hidden flex items-center justify-center bg-white/10">
        <img
          src={logoImage}
          alt="DiffCOT Logo"
          className="w-36 h-36 object-contain"
        />
      </div>

      {/* Title */}
      <h1
        className="text-2xl font-medium mb-3"
        style={{ color: 'var(--color-text-secondary)' }}
      >
        DiffCOT - AI Code Review
      </h1>

      {/* Subtitle */}
      <p
        className="text-base mb-6"
        style={{ color: 'var(--color-text-secondary)', opacity: 0.7 }}
      >
        Select a repository to start code review
      </p>

      {/* New Repo Button */}
      <button
        onClick={onNewChat}
        className="px-6 py-2.5 rounded-lg font-medium transition-colors"
        style={{
          backgroundColor: 'var(--color-accent)',
          color: 'white'
        }}
        onMouseEnter={(e) => e.currentTarget.style.opacity = '0.9'}
        onMouseLeave={(e) => e.currentTarget.style.opacity = '1'}
      >
        New Repo
      </button>
    </div>
  );
};
