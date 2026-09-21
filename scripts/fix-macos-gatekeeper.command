#!/bin/bash
# ========================================================
#          VideoCut macOS 极速安全拦截与自签名修复工具
# ========================================================
# 解决 macOS 提示：“已损坏，无法打开。你应该将它移到废纸篓”
# 以及：“打不开 VideoCut，因为 Apple 无法检查其是否包含恶意软件”

set -e

echo "========================================================"
echo "          VideoCut macOS 极速安全拦截解除工具"
echo "========================================================"
echo ""
echo "正在为您一键解除 macOS Gatekeeper 安全隔离与签名拦截..."
echo ""

APP_PATH="/Applications/VideoCut.app"

# 1. 自动定位 VideoCut.app 路径
if [ ! -d "$APP_PATH" ]; then
    DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    if [ -d "$DIR/VideoCut.app" ]; then
        APP_PATH="$DIR/VideoCut.app"
    elif [ -d "$DIR/../VideoCut.app" ]; then
        APP_PATH="$DIR/../VideoCut.app"
    fi
fi

if [ -d "$APP_PATH" ]; then
    echo "📍 发现应用路径: $APP_PATH"
    echo ""
    echo "正在执行安全策略修复 (如提示 Password 请输入您的 Mac 开机密码):"
    
    # 步骤 1: 移除下载隔离属性 (Quarantine)
    echo "  [1/3] 正在清除 Gatekeeper Quarantine 隔离属性..."
    sudo xattr -cr "$APP_PATH" 2>/dev/null || xattr -cr "$APP_PATH" 2>/dev/null || true
    sudo xattr -r -d com.apple.quarantine "$APP_PATH" 2>/dev/null || true

    # 步骤 2: 恢复内部二进制执行权限
    echo "  [2/3] 正在校验并修复二进制运行权限..."
    if [ -d "$APP_PATH/Contents/MacOS" ]; then
        sudo chmod -R +x "$APP_PATH/Contents/MacOS" 2>/dev/null || chmod -R +x "$APP_PATH/Contents/MacOS" 2>/dev/null || true
    fi

    # 步骤 3: 本地 Ad-Hoc 深度重签名（彻底解决 macOS 14/15 报“已损坏”问题）
    echo "  [3/3] 正在注入本地 Ad-Hoc 代码签名凭据..."
    sudo codesign --force --deep --sign - "$APP_PATH" 2>/dev/null || codesign --force --deep --sign - "$APP_PATH" 2>/dev/null || true

    echo ""
    echo "========================================================"
    echo "  ✅ 恭喜！VideoCut 安全拦截与签名已全部成功修复！"
    echo "========================================================"
    echo "您现在可以直接在访达中双击打开 VideoCut 正常使用了！"
    echo ""
    echo "提示：如果系统仍提示受阻，请前往："
    echo "「系统设置 (System Settings)」->「隐私与安全性 (Privacy & Security)」"
    echo "滑动到最下方，点击「仍要打开 (Open Anyway)」即可。"
else
    echo "⚠️ 未在常用路径自动检索到 VideoCut.app"
    echo ""
    echo "使用建议："
    echo "1. 请先将 VideoCut.app 拖入 /Applications (应用程序) 目录；"
    echo "2. 然后再次双击运行本脚本即可！"
    echo ""
    echo "或者您可直接在终端中手动执行如下两条命令："
    echo "  sudo xattr -cr /Applications/VideoCut.app"
    echo "  sudo codesign --force --deep --sign - /Applications/VideoCut.app"
fi

echo ""
read -p "按回车键退出..."
