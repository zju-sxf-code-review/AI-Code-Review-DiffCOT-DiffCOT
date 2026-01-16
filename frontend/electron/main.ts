import { app, BrowserWindow } from 'electron';
import path from 'path';
import { fileURLToPath } from 'url';
import { spawn, ChildProcess } from 'child_process';
import { existsSync } from 'fs';

// __dirname for ESM modules (used in development)
const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Handle creating/removing shortcuts on Windows when installing/uninstalling.
// Only needed on Windows, wrapped in try-catch for other platforms
if (process.platform === 'win32') {
  try {
    const { createRequire } = await import('module');
    const require = createRequire(import.meta.url);
    if (require('electron-squirrel-startup')) {
      app.quit();
    }
  } catch {
    // Module not available, ignore
  }
}

/**
 * 获取前端 HTML 文件路径
 */
function getIndexHtmlPath(): string {
  if (app.isPackaged) {
    // 打包后: app.asar/dist/index.html
    return path.join(app.getAppPath(), 'dist', 'index.html');
  } else {
    // 开发模式: dist-electron/../dist/index.html
    return path.join(__dirname, '../dist/index.html');
  }
}

// 后端进程引用
let backendProcess: ChildProcess | null = null;

/**
 * 获取后端可执行文件路径
 * 统一处理 Windows (.exe) 和 macOS/Linux 的路径查找
 */
function getBackendPath(): string | null {
  const isPackaged = app.isPackaged;

  if (!isPackaged) {
    console.log('Development mode: Backend should be started manually');
    return null;
  }

  const resourcesPath = process.resourcesPath;
  console.log('Looking for backend in resourcesPath:', resourcesPath);

  // 统一查找：同时尝试有无 .exe 扩展名
  const backendNames = ['diffcot-backend.exe', 'diffcot-backend'];
  const basePaths = [
    path.join(resourcesPath, 'backend'),
    path.join(resourcesPath, 'backend-dist'),
    path.join(resourcesPath, 'backend', 'diffcot-backend'),
    path.join(resourcesPath, 'backend-dist', 'diffcot-backend'),
    resourcesPath,
  ];

  // 先列出 resources 目录内容
  try {
    const { readdirSync } = require('fs');
    console.log('Contents of resources:', readdirSync(resourcesPath));
    for (const bp of basePaths) {
      if (existsSync(bp)) {
        console.log(`Contents of ${bp}:`, readdirSync(bp));
      }
    }
  } catch (e) {
    console.error('Error listing directories:', e);
  }

  for (const basePath of basePaths) {
    for (const name of backendNames) {
      const fullPath = path.join(basePath, name);
      if (existsSync(fullPath)) {
        console.log('Found backend at:', fullPath);
        return fullPath;
      }
    }
  }

  console.error('Backend not found. Searched in:', basePaths);
  return null;
}

/**
 * 启动后端服务
 */
function startBackend(): Promise<void> {
  return new Promise((resolve, reject) => {
    const backendPath = getBackendPath();

    if (!backendPath) {
      resolve();
      return;
    }

    console.log('Starting backend:', backendPath);

    const backendDir = path.dirname(backendPath);
    const env = {
      ...process.env,
      DIFFCOT_DATA_DIR: path.join(app.getPath('userData'), 'data'),
    };

    const spawnOptions: any = {
      env,
      cwd: backendDir,
      stdio: ['ignore', 'pipe', 'pipe'],
      detached: false,
    };

    // Windows 特定配置
    if (process.platform === 'win32') {
      spawnOptions.shell = true;
      spawnOptions.windowsHide = true;
    }

    backendProcess = spawn(backendPath, [], spawnOptions);

    backendProcess.stdout?.on('data', (data) => {
      console.log(`[Backend] ${data.toString().trim()}`);
    });

    backendProcess.stderr?.on('data', (data) => {
      console.error(`[Backend Error] ${data.toString().trim()}`);
    });

    backendProcess.on('error', (error) => {
      console.error('Failed to start backend:', error);
      reject(error);
    });

    backendProcess.on('close', (code) => {
      console.log(`Backend exited with code ${code}`);
      backendProcess = null;
    });

    // 等待后端启动
    setTimeout(resolve, 2000);
  });
}

/**
 * 停止后端服务
 */
function stopBackend(): void {
  if (backendProcess) {
    console.log('Stopping backend process...');

    if (process.platform === 'win32') {
      spawn('taskkill', ['/pid', backendProcess.pid!.toString(), '/f', '/t']);
    } else {
      backendProcess.kill('SIGTERM');
    }

    backendProcess = null;
  }
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1000,
    height: 700,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: true,
      contextIsolation: false,
      webSecurity: false
    },
    titleBarStyle: 'hiddenInset',
    backgroundColor: '#1e1e1e',
  });

  if (process.env.VITE_DEV_SERVER_URL) {
    win.loadURL(process.env.VITE_DEV_SERVER_URL);
  } else {
    if (!app.isPackaged) {
      // 开发模式
      win.loadURL('http://localhost:5173');
    } else {
      // 生产模式 - 使用 app.getAppPath() 获取正确路径
      const indexPath = getIndexHtmlPath();
      console.log('Loading index.html from:', indexPath);
      win.loadFile(indexPath);
    }
  }

}

app.whenReady().then(async () => {
  // 启动后端服务
  try {
    await startBackend();
  } catch (error) {
    console.error('Failed to start backend:', error);
  }

  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    stopBackend();
    app.quit();
  }
});

app.on('before-quit', () => {
  stopBackend();
});

app.on('will-quit', () => {
  stopBackend();
});
