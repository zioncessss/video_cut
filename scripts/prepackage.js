#!/usr/bin/env node
/**
 * scripts/prepackage.js
 * 桌面端打包前置校验与资源准备自愈脚本。
 * 确保在执行 electron-builder 打包前：
 * 1. resources/engine/bin/ 存在有效的 ffmpeg 与 ffprobe（支持自动探测系统安装与静默拉取）
 * 2. resources/engine/videocut-engine/ 存在有效的原生可执行文件
 * 3. resources/default_storage/ 存在词库与违禁词字典
 * 4. macOS 脚本与二进制权限健全
 */
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const rootDir = path.resolve(__dirname, '..');
const isWin = process.platform === 'win32';
const isMac = process.platform === 'darwin';

let targetArch = 'x64';
const archArg = process.argv.find((a) => a.startsWith('--arch='));
if (archArg) {
  targetArch = archArg.split('=')[1].trim();
} else if (process.env.TARGET_ARCH) {
  targetArch = process.env.TARGET_ARCH.trim();
} else if (process.env.npm_config_arch) {
  targetArch = process.env.npm_config_arch.trim();
} else {
  targetArch = process.arch === 'arm64' ? 'arm64' : 'x64';
}

console.log('--------------------------------------------------');
console.log(` [PrePackage] 正在校验桌面端打包所需关键依赖资源 (目标架构: ${targetArch})...`);
console.log('--------------------------------------------------');

// 1. 确保 resources/engine/bin 及其可执行程序
const binDir = path.resolve(rootDir, 'resources', 'engine', 'bin');
if (!fs.existsSync(binDir)) {
  fs.mkdirSync(binDir, { recursive: true });
}

const ffmpegName = isWin ? 'ffmpeg.exe' : 'ffmpeg';
const ffprobeName = isWin ? 'ffprobe.exe' : 'ffprobe';
const ffmpegDest = path.resolve(binDir, ffmpegName);
const ffprobeDest = path.resolve(binDir, ffprobeName);

function checkBinaryArchMatch(filePath, expectedArch) {
  if (!isMac || !fs.existsSync(filePath)) return true;
  try {
    const fileOut = execSync(`file "${filePath}"`, { stdio: 'pipe' }).toString();
    if (expectedArch === 'x64' || expectedArch === 'x86_64') {
      return fileOut.includes('x86_64') || fileOut.includes('universal');
    } else if (expectedArch === 'arm64') {
      return fileOut.includes('arm64') || fileOut.includes('universal');
    }
  } catch (_) {}
  return true;
}

function findOrDownload(binName, destPath, downloadUrl) {
  if (fs.existsSync(destPath) && fs.statSync(destPath).size > 1024) {
    if (checkBinaryArchMatch(destPath, targetArch)) {
      console.log(` [PrePackage] ✓ 已就绪 (架构匹配 ${targetArch}): ${path.relative(rootDir, destPath)}`);
      return true;
    }
    console.warn(` [PrePackage] ⚠️ 发现现存 ${binName} 架构与目标架构 ${targetArch} 不匹配，正在清理重新拉取...`);
    try {
      fs.unlinkSync(destPath);
    } catch (_) {}
  }

  // 1. 尝试从系统探测并复制
  let found = null;
  if (isWin) {
    const userHome = process.env.USERPROFILE || '';
    const candidates = [
      path.resolve(userHome, 'AppData', 'Local', 'Microsoft', 'WinGet', 'Links', binName),
      path.resolve('C:\\ProgramData\\chocolatey\\bin', binName),
      path.resolve(userHome, 'scoop', 'shims', binName),
      path.resolve('C:\\ffmpeg\\bin', binName)
    ];
    try {
      const whichOut = execSync(`where ${binName}`, { stdio: 'pipe' }).toString().split('\n')[0].trim();
      if (whichOut && fs.existsSync(whichOut)) candidates.unshift(whichOut);
    } catch (_) {}

    for (const c of candidates) {
      if (fs.existsSync(c)) {
        found = c;
        break;
      }
    }
  } else if (isMac) {
    const candidates = [
      path.resolve('/opt/homebrew/bin', binName),
      path.resolve('/usr/local/bin', binName),
      path.resolve('/usr/bin', binName)
    ];
    try {
      const whichOut = execSync(`which ${binName}`, { stdio: 'pipe' }).toString().trim();
      if (whichOut && fs.existsSync(whichOut)) candidates.unshift(whichOut);
    } catch (_) {}

    for (const c of candidates) {
      if (fs.existsSync(c) && checkBinaryArchMatch(c, targetArch)) {
        found = c;
        break;
      }
    }
  }

  if (found) {
    fs.copyFileSync(found, destPath);
    console.log(` [PrePackage] ✓ 已从本机复制 ${binName}: ${found} -> ${path.relative(rootDir, destPath)}`);
    return true;
  }

  // 2. 尝试使用 curl 下载静态独立包
  if (downloadUrl) {
    console.log(` [PrePackage] 正在从 GitHub 极速拉取静态独立版 ${binName} (${targetArch})...`);
    try {
      execSync(`curl -fSL "${downloadUrl}" -o "${destPath}"`, { stdio: 'inherit' });
      if (fs.existsSync(destPath) && fs.statSync(destPath).size > 1024) {
        if (!isWin) fs.chmodSync(destPath, 0o755);
        console.log(` [PrePackage] ✓ 成功下载: ${path.relative(rootDir, destPath)}`);
        return true;
      }
    } catch (e) {
      console.warn(` [PrePackage] 下载 ${binName} 失败:`, e.message);
    }
  }

  return false;
}

const ffmpegUrl = isWin
  ? 'https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1/ffmpeg-win32-x64'
  : `https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1/ffmpeg-darwin-${targetArch}`;
const ffprobeUrl = isWin
  ? 'https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1/ffprobe-win32-x64'
  : `https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1/ffprobe-darwin-${targetArch}`;

const hasFFmpeg = findOrDownload(ffmpegName, ffmpegDest, ffmpegUrl);
const hasFFprobe = findOrDownload(ffprobeName, ffprobeDest, ffprobeUrl);

if (!hasFFmpeg || !hasFFprobe) {
  console.error('\n❌【致命错误】未能就绪 FFmpeg / FFprobe 组件！');
  console.error(`请手动将 ${ffmpegName} 和 ${ffprobeName} 放置在 resources/engine/bin/ 目录中后再打包。\n`);
  process.exit(1);
}

// 2. 检查 Python 算力引擎可执行文件
const sidecarDir = path.resolve(rootDir, 'resources', 'engine', 'videocut-engine');
const sidecarExe = isWin
  ? path.resolve(sidecarDir, 'videocut-engine.exe')
  : path.resolve(sidecarDir, 'videocut-engine');

if (!fs.existsSync(sidecarExe)) {
  console.error('\n❌【致命错误】未找到 Python 算力引擎 sidecar 产物:');
  console.error(`  期望路径: ${path.relative(rootDir, sidecarExe)}`);
  console.error('请先执行打包脚本构建算力引擎:');
  if (isWin) {
    console.error('  powershell -ExecutionPolicy Bypass -File scripts/build-engine.ps1\n');
  } else {
    console.error(`  bash scripts/build-engine.sh --arch=${targetArch}\n`);
  }
  process.exit(1);
} else {
  if (isMac && !checkBinaryArchMatch(sidecarExe, targetArch)) {
    console.error(`\n❌【致命错误】Python 算力引擎架构不匹配！`);
    console.error(`  当前打包目标架构为: ${targetArch}`);
    try {
      const actArch = execSync(`file "${sidecarExe}"`, { stdio: 'pipe' }).toString().trim();
      console.error(`  但现有 videocut-engine 二进制实际架构为: ${actArch}`);
    } catch (_) {}
    console.error(`请针对 ${targetArch} 架构重新构建算力引擎后再打包：`);
    console.error(`  bash scripts/build-engine.sh --arch=${targetArch}\n`);
    process.exit(1);
  }

  console.log(` [PrePackage] ✓ 已就绪 (架构匹配 ${targetArch}): ${path.relative(rootDir, sidecarExe)}`);
  if (!isWin) {
    try {
      fs.chmodSync(sidecarExe, 0o755);
    } catch (_) {}
  }
}

// 3. 校验并同步默认词库与字典资源
const defStorageDir = path.resolve(rootDir, 'resources', 'default_storage');
if (!fs.existsSync(defStorageDir)) {
  fs.mkdirSync(defStorageDir, { recursive: true });
}

const glossarySrc = path.resolve(rootDir, 'storage', 'glossary.json');
const glossaryDst = path.resolve(defStorageDir, 'glossary.json');
if (fs.existsSync(glossarySrc)) {
  fs.copyFileSync(glossarySrc, glossaryDst);
}

const bannedSrc = path.resolve(rootDir, 'storage', 'banned_words.json');
const bannedDst = path.resolve(defStorageDir, 'banned_words.json');
if (fs.existsSync(bannedSrc)) {
  fs.copyFileSync(bannedSrc, bannedDst);
}

console.log(' [PrePackage] ✓ 默认存储种子已就绪 (glossary.json, banned_words.json)');

// 4. macOS 脚本执行权限防御
if (isMac) {
  const scriptsToChmod = [
    path.resolve(rootDir, 'resources', '一键解除Mac拦截.command'),
    path.resolve(rootDir, 'scripts', 'fix-macos-gatekeeper.command'),
    path.resolve(rootDir, 'scripts', 'fix-macos-gatekeeper.sh')
  ];
  for (const s of scriptsToChmod) {
    if (fs.existsSync(s)) {
      try {
        fs.chmodSync(s, 0o755);
      } catch (_) {}
    }
  }
}

console.log(' [PrePackage] ✅ 所有打包前置依赖校验通过！开始执行主打包构建流程...\n');
