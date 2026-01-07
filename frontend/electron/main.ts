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
 */
function getBackendPath(): string | null {
  const isPackaged = app.isPackaged;

  if (isPackaged) {
    // 打包后的路径
    const resourcesPath = process.resourcesPath;
    const platform = process.platform;

    let backendName = 'diffcot-backend';
    if (platform === 'win32') {
      backendName += '.exe';
    }

    const backendPath = path.join(resourcesPath, 'backend', backendName);

    if (existsSync(backendPath)) {
      return backendPath;
    }

    // 尝试其他可能的路径
    const altPath = path.join(resourcesPath, 'backend', 'diffcot-backend', backendName);
    if (existsSync(altPath)) {
      return altPath;
    }

    console.error('Backend executable not found at:', backendPath);
    return null;
  } else {
    // 开发模式：不自动启动后端，需要手动运行
    return null;
  }
}

/**
 * 启动后端服务
 */
function startBackend(): Promise<void> {
  return new Promise((resolve, reject) => {
    const backendPath = getBackendPath();

    if (!backendPath) {
      console.log('Development mode: Backend should be started manually');
      resolve();
      return;
    }

    console.log('Starting backend from:', backendPath);
    console.log('Backend exists:', existsSync(backendPath));

    // 获取后端所在目录（用于设置 cwd）
    const backendDir = path.dirname(backendPath);
    console.log('Backend directory:', backendDir);

    // 设置环境变量
    const env = {
      ...process.env,
      DIFFCOT_DATA_DIR: path.join(app.getPath('userData'), 'data'),
    };

    // 启动后端进程
    // 设置 cwd 为后端目录，确保能找到 _internal 中的依赖
    backendProcess = spawn(backendPath, [], {
      env,
      cwd: backendDir,
      stdio: ['ignore', 'pipe', 'pipe'],
      detached: false,
    });

    // 监听输出
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
      console.log(`Backend process exited with code ${code}`);
      backendProcess = null;
    });

    // 等待后端启动
    setTimeout(() => {
      resolve();
    }, 2000);
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
