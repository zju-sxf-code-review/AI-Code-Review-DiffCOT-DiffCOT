import { shell } from 'electron';

// Expose electronAPI to the window object
declare global {
  interface Window {
    electronAPI: {
      openPath: (path: string) => Promise<string>;
      openExternal: (url: string) => Promise<void>;
    };
  }
}

window.electronAPI = {
  openPath: async (filePath: string) => {
    return shell.openPath(filePath);
  },
  openExternal: async (url: string) => {
    return shell.openExternal(url);
  }
};

window.addEventListener('DOMContentLoaded', () => {
  console.log('Electron preload script loaded');
});
