/**
 * electron-builder 配置文件
 * 用于打包 DiffCOT 桌面应用
 */

module.exports = {
  appId: "com.diffcot.app",
  productName: "DiffCOT",
  copyright: "Copyright © 2025 DiffCOT",

  // 输出目录
  directories: {
    output: "release",
    buildResources: "build-resources"
  },

  // 需要打包的文件
  files: [
    "dist/**/*",
    "dist-electron/**/*",
    "!node_modules/**/*"
  ],

  // 额外资源 (后端可执行文件)
  extraResources: [
    {
      from: "backend-dist/",
      to: "backend",
      filter: ["**/*"]
    }
  ],

  // macOS 配置
  mac: {
    category: "public.app-category.developer-tools",
    icon: "build-resources/icon.png",
    target: [
      {
        target: "dmg",
        arch: ["arm64"]  // 仅打包当前架构，加快速度
      }
    ],
    darkModeSupport: true,
    // 开发阶段禁用代码签名
    identity: null,
    hardenedRuntime: false,
    gatekeeperAssess: false
  },

  // DMG 配置
  dmg: {
    sign: false,  // 禁用 DMG 签名
    contents: [
      {
        x: 130,
        y: 220
      },
      {
        x: 410,
        y: 220,
        type: "link",
        path: "/Applications"
      }
    ],
    window: {
      width: 540,
      height: 380
    }
  },

  // Windows 配置
  win: {
    icon: "build-resources/icon.png",
    target: [
      {
        target: "nsis",
        arch: ["x64"]
      }
    ]
  },

  // NSIS 安装程序配置 (Windows)
  nsis: {
    oneClick: false,
    allowToChangeInstallationDirectory: true,
    createDesktopShortcut: true,
    createStartMenuShortcut: true,
    shortcutName: "DiffCOT"
  },

  // Linux 配置
  linux: {
    icon: "build-resources/icons",
    target: ["AppImage", "deb"],
    category: "Development"
  },

  // 发布配置 (可选)
  publish: null
};
