import React, { useState, useRef, useEffect } from 'react';
import {
  MessageSquare,
  X,
  Send,
  Sparkles,
  Bot,
  User,
  Wand2,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  BrainCircuit,
  Film,
  RefreshCw,
  Sliders,
  Scissors
} from 'lucide-react';
import { streamChatSSE, ChatMessageItem } from '../services/api';

interface HarnessChatDrawerProps {
  currentProjectId?: string | null;
  onApplyStrategyToProject?: (plan: {
    explanation: string;
    updated_subtitles?: any[];
    updated_brolls?: any[];
  }) => void;
  isOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  showFloatingTrigger?: boolean;
}

export const HarnessChatDrawer: React.FC<HarnessChatDrawerProps> = ({
  currentProjectId,
  onApplyStrategyToProject,
  isOpen: controlledIsOpen,
  onOpenChange,
  showFloatingTrigger = false,
}) => {
  const [internalIsOpen, setInternalIsOpen] = useState(false);
  const isOpen = controlledIsOpen !== undefined ? controlledIsOpen : internalIsOpen;

  const handleSetOpen = (open: boolean) => {
    if (onOpenChange) {
      onOpenChange(open);
    }
    if (controlledIsOpen === undefined) {
      setInternalIsOpen(open);
    }
  };
  const [messages, setMessages] = useState<ChatMessageItem[]>([
    {
      role: 'assistant',
      content:
        '你好！我是 VideoCut 智能副驾驶。我可以为你解答各种短视频剪辑与运营疑问、创作吸睛剧本台词，并能通过对话**直接微调你的剪辑策略与工程**。有什么我可以协助你的？',
    },
  ]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [showReasoning, setShowReasoning] = useState<{ [idx: number]: boolean }>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isStreaming]);

  // 快捷 Prompt 推荐胶囊
  const quickPrompts = [
    { label: '🎯 诊断剪辑节奏', prompt: '请根据我当前的视频字幕与空镜，分析整体叙事节奏是否拖沓，给出改进建议。' },
    { label: '✨ 润色口播文案', prompt: '请帮我把当前视频的第1句开场白润色得更加有网感、更抓人眼球。' },
    { label: '🎬 重新调度空镜', prompt: '请将视频中提到考场和练车的句子，重新匹配关联更加合适的空镜素材。' },
    { label: '🔥 15秒爆款脚本', prompt: '帮我针对驾校科目二倒车入库，写一段15秒的高完播率口播台词。' },
  ];

  const handleSend = (textToSend?: string) => {
    const query = (textToSend || input).trim();
    if (!query || isStreaming) return;

    const newMessages: ChatMessageItem[] = [
      ...messages,
      { role: 'user', content: query },
    ];
    setMessages(newMessages);
    setInput('');
    setIsStreaming(true);

    // 预添加一个空的助手消息用于流式拼接
    const assistantIndex = newMessages.length;
    let accumulatedContent = '';
    let accumulatedReasoning = '';

    setMessages((prev) => [
      ...prev,
      { role: 'assistant', content: '', reasoning: '' },
    ]);

    const historyForApi = newMessages.slice(-6).map((m) => ({
      role: m.role,
      content: m.content,
    }));

    streamChatSSE(
      {
        message: query,
        project_id: currentProjectId || undefined,
        history: historyForApi,
      },
      (chunk) => {
        if (chunk.type === 'content' && chunk.delta) {
          accumulatedContent += chunk.delta;
        } else if (chunk.type === 'reasoning' && chunk.delta) {
          accumulatedReasoning += chunk.delta;
        }

        // 解析动作块 <<<ACTION>>> ... <<<END_ACTION>>>
        let displayContent = accumulatedContent;
        let detectedAction: any = null;

        const actionMatch = accumulatedContent.match(
          /<<<ACTION>>>([\s\S]*?)<<<END_ACTION>>>/
        );
        if (actionMatch) {
          try {
            detectedAction = JSON.parse(actionMatch[1].trim());
            displayContent = accumulatedContent
              .replace(/<<<ACTION>>>[\s\S]*?<<<END_ACTION>>>/, '')
              .trim();
          } catch (e) {
            // 继续等待完整闭合
          }
        }

        setMessages((prev) => {
          const updated = [...prev];
          if (updated[assistantIndex]) {
            updated[assistantIndex] = {
              role: 'assistant',
              content: displayContent,
              reasoning: accumulatedReasoning,
              action: detectedAction,
            };
          }
          return updated;
        });
      },
      () => {
        setIsStreaming(false);
      },
      (err) => {
        setIsStreaming(false);
        setMessages((prev) => {
          const updated = [...prev];
          if (updated[assistantIndex]) {
            updated[assistantIndex] = {
              role: 'assistant',
              content:
                updated[assistantIndex].content ||
                `[请求异常]：${err.message || '连接失败'}`,
            };
          }
          return updated;
        });
      }
    );
  };

  const toggleReasoning = (idx: number) => {
    setShowReasoning((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  return (
    <>
      {/* 悬浮唤起胶囊按钮：默认由顶部导航栏或工作台唤起，若启用悬浮按钮则定位在 bottom-20，绝不遮挡底部生成预览按钮 */}
      {!isOpen && showFloatingTrigger && (
        <button
          onClick={() => handleSetOpen(true)}
          className="fixed bottom-20 right-6 z-40 flex items-center space-x-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white px-4 py-2.5 rounded-full shadow-lg shadow-blue-500/30 transition-all hover:scale-105 active:scale-95 group cursor-pointer"
        >
          <div className="relative">
            <Sparkles className="w-4 h-4 animate-pulse" />
            <span className="absolute -top-1 -right-1 w-2 h-2 bg-emerald-400 rounded-full"></span>
          </div>
          <span className="text-xs font-semibold tracking-wide">Harness 对话副驾驶</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/20 font-mono">GLM</span>
        </button>
      )}

      {/* 侧边滑出抽屉 */}
      {isOpen && (
        <div className="fixed inset-y-0 right-0 z-50 w-full sm:w-[460px] bg-white shadow-2xl border-l border-gray-200 flex flex-col animate-in slide-in-from-right duration-300">
          {/* 抽屉头部 */}
          <div className="h-14 px-4 border-b border-gray-100 flex items-center justify-between bg-gray-50/60 backdrop-blur-md">
            <div className="flex items-center space-x-2.5">
              <div className="w-7 h-7 rounded-lg bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white shadow-sm">
                <Sparkles className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-xs font-bold text-gray-900 flex items-center space-x-1.5">
                  <span>Harness 创意与剪辑副驾驶</span>
                  <span className="text-[10px] text-emerald-600 bg-emerald-50 px-1.5 py-0.2 rounded border border-emerald-200">
                    Live Stream
                  </span>
                </h3>
                <p className="text-[10px] text-gray-400 font-mono">
                  {currentProjectId ? `已绑定工程: ${currentProjectId.slice(0, 8)}...` : '全局模式 (自由创作与答疑)'}
                </p>
              </div>
            </div>
            <button
              onClick={() => handleSetOpen(false)}
              className="w-7 h-7 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-200/60 flex items-center justify-center transition-colors cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* 对话消息滚动流 */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-[#F8FAFC]/50 text-xs">
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex flex-col ${
                  msg.role === 'user' ? 'items-end' : 'items-start'
                }`}
              >
                <div
                  className={`flex items-start space-x-2 max-w-[90%] ${
                    msg.role === 'user' ? 'flex-row-reverse space-x-reverse' : 'flex-row'
                  }`}
                >
                  <div
                    className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 ${
                      msg.role === 'user'
                        ? 'bg-blue-600 text-white'
                        : 'bg-indigo-100 text-indigo-600'
                    }`}
                  >
                    {msg.role === 'user' ? (
                      <User className="w-3.5 h-3.5" />
                    ) : (
                      <Bot className="w-3.5 h-3.5" />
                    )}
                  </div>

                  <div className="space-y-2">
                    {/* 模型思考过程卡片（默认流式生成时自动展开，支持随时折叠） */}
                    {msg.reasoning && (
                      <div className="bg-indigo-50/60 border border-indigo-200/80 rounded-xl p-2.5 text-[11px] text-gray-700">
                        <button
                          onClick={() => toggleReasoning(idx)}
                          className="flex items-center space-x-1.5 text-indigo-700 hover:text-indigo-900 font-semibold w-full text-left"
                        >
                          <BrainCircuit className={`w-3.5 h-3.5 text-indigo-600 ${isStreaming && idx === messages.length - 1 && !msg.content ? 'animate-pulse' : ''}`} />
                          <span>思考过程分析 (Thinking)</span>
                          {isStreaming && idx === messages.length - 1 && !msg.content && (
                            <span className="text-[9px] bg-indigo-200 text-indigo-800 px-1 rounded animate-pulse">
                              思考中...
                            </span>
                          )}
                          {(showReasoning[idx] ?? true) ? (
                            <ChevronUp className="w-3 h-3 ml-auto" />
                          ) : (
                            <ChevronDown className="w-3 h-3 ml-auto" />
                          )}
                        </button>
                        {(showReasoning[idx] ?? true) && (
                          <div className="mt-2 text-[10px] text-gray-600 whitespace-pre-wrap font-mono border-t border-indigo-200/50 pt-2 leading-relaxed max-h-60 overflow-y-auto">
                            {msg.reasoning}
                          </div>
                        )}
                      </div>
                    )}

                    {/* 正文对话气泡 */}
                    {(msg.content || !msg.reasoning) && (
                      <div
                        className={`p-3 rounded-2xl whitespace-pre-wrap leading-relaxed shadow-sm ${
                          msg.role === 'user'
                            ? 'bg-blue-600 text-white rounded-tr-sm'
                            : 'bg-white border border-gray-200/80 text-gray-800 rounded-tl-sm'
                        }`}
                      >
                        {msg.content}
                        {isStreaming && idx === messages.length - 1 && (
                          <span className="inline-block w-1.5 h-3.5 bg-blue-600 ml-1 translate-y-0.5 animate-pulse" />
                        )}
                      </div>
                    )}

                    {/* 剪辑策略调整行动卡片 (Action Trigger Card) */}
                    {msg.action && (
                      <div className="bg-gradient-to-br from-indigo-50 to-blue-50 border border-indigo-200/80 rounded-2xl p-3.5 shadow-sm text-gray-800 space-y-2.5 animate-in fade-in">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center space-x-1.5 text-indigo-700 font-semibold text-xs">
                            <Sliders className="w-4 h-4 text-indigo-600" />
                            <span>识别到剪辑策略微调意向</span>
                          </div>
                          <span className="text-[10px] font-mono bg-indigo-100 text-indigo-700 px-1.5 py-0.5 rounded">
                            Action Ready
                          </span>
                        </div>
                        <p className="text-[11px] text-gray-600 leading-snug">
                          {msg.action.explanation}
                        </p>

                        <button
                          onClick={() => {
                            if (onApplyStrategyToProject && msg.action) {
                              onApplyStrategyToProject(msg.action);
                              alert('策略已成功应用到当前剪辑工程！');
                            } else {
                              alert('请先在剪辑工作台选择一个视频工程');
                            }
                          }}
                          className="w-full flex items-center justify-center space-x-2 bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 rounded-xl transition-all shadow-sm active:scale-98 text-xs"
                        >
                          <Scissors className="w-3.5 h-3.5" />
                          <span>一键应用此策略至工作台</span>
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* 快捷推荐提示标签 */}
          <div className="p-2.5 bg-gray-50/80 border-t border-gray-100">
            <div className="flex items-center space-x-1.5 overflow-x-auto pb-1 scrollbar-none">
              {quickPrompts.map((qp, i) => (
                <button
                  key={i}
                  disabled={isStreaming}
                  onClick={() => handleSend(qp.prompt)}
                  className="flex-shrink-0 text-[11px] bg-white hover:bg-blue-50 hover:text-blue-600 text-gray-600 border border-gray-200/80 px-2.5 py-1 rounded-full transition-colors disabled:opacity-50 shadow-2xs"
                >
                  {qp.label}
                </button>
              ))}
            </div>
          </div>

          {/* 底部输入框 */}
          <div className="p-3 bg-white border-t border-gray-200/80 flex items-center space-x-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="输入你的问题或剪辑调整想法 (按 Enter 发送)..."
              rows={1}
              disabled={isStreaming}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              className="flex-1 bg-gray-50 border border-gray-200 rounded-xl px-3 py-2 text-xs text-gray-800 outline-none focus:ring-1 focus:ring-blue-500 resize-none max-h-24"
            />
            <button
              onClick={() => handleSend()}
              disabled={isStreaming || !input.trim()}
              className="w-9 h-9 rounded-xl bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white flex items-center justify-center transition-colors shadow-sm flex-shrink-0"
            >
              {isStreaming ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>
      )}
    </>
  );
};