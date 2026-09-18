#!/bin/bash
echo "========================================================"
echo "          VideoCut macOS 极速安全拦截解除工具"
echo "========================================================"
echo ""
echo "正在为您一键解除 macOS Gatekeeper 隔离隔离属性 (Quarantine)..."

APP_PATH="/Applications/VideoCut.app"

if [ ! -d "$APP_PATH" ]; then
    # 尝试在当前脚本所在目录或上级目录探测
    DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    if [ -d "$DIR/VideoCut.app" ]; then
        APP_PATH="$DIR/VideoCut.app"
    elif [ -d "$DIR/../VideoCut.app" ]; then
        APP_PATH="$DIR/../VideoCut.app"
    fi
fi

if [ -d "$APP_PATH" ]; then
    echo "发现应用路径: $APP_PATH"
    echo "正在执行 xattr 解除命令 (如提示 Password 请输入您的 Mac 开机密码):"
    sudo xattr -r -d com.apple.quarantine "$APP_PATH" 2>/dev/null || xattr -r -d com.apple.quarantine "$APP_PATH" 2>/dev/null
    echo ""
    echo "✅ 恭喜！隔离拦截属性已全部解除！"
    echo "您现在可以直接在访达中双击打开 VideoCut 正常使用了。"
else
    echo "⚠️ 未在常用路径自动检索到 VideoCut.app"
    echo "请将 VideoCut.app 拖入 /Applications (应用程序) 目录后再双击本脚本。"
    echo "或者在终端中手动执行："
    echo "sudo xattr -r -d com.apple.quarantine /Applications/VideoCut.app"
fi

echo ""
read -p "按回车键退出..."