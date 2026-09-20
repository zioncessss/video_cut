import React, { createContext, useContext, useState, useRef, useEffect, ReactNode } from 'react';
import {
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  Info,
  X,
  Trash2
} from 'lucide-react';

export type DialogType = 'info' | 'success' | 'warning' | 'error';

export interface AlertOptions {
  title?: string;
  message: string;
  type?: DialogType;
  confirmText?: string;
}

export interface ConfirmOptions {
  title?: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  isDestructive?: boolean;
  type?: DialogType;
}

export interface ToastItem {
  id: string;
  message: string;
  type: DialogType;
}

interface DialogContextValue {
  showAlert: (opts: AlertOptions | string) => Promise<void>;
  showConfirm: (opts: ConfirmOptions | string) => Promise<boolean>;
  showToast: (message: string, type?: DialogType, duration?: number) => void;
}

const DialogContext = createContext<DialogContextValue | null>(null);

export const useDialog = (): DialogContextValue => {
  const ctx = useContext(DialogContext);
  if (!ctx) {
    throw new Error('useDialog must be used within a DialogProvider');
  }
  return ctx;
};

interface DialogState {
  isOpen: boolean;
  isConfirm: boolean;
  title?: string;
  message: string;
  type: DialogType;
  confirmText: string;
  cancelText?: string;
  isDestructive?: boolean;
  resolve?: (value: any) => void;
}

export const DialogProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [dialogState, setDialogState] = useState<DialogState | null>(null);
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const toastTimers = useRef<Map<string, NodeJS.Timeout>>(new Map());

  const showToast = (message: string, type: DialogType = 'success', duration: number = 3000) => {
    const id = `${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    setToasts(prev => [...prev, { id, message, type }]);

    const timer = setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
      toastTimers.current.delete(id);
    }, duration);

    toastTimers.current.set(id, timer);
  };

  const showAlert = (opts: AlertOptions | string): Promise<void> => {
    const options: AlertOptions = typeof opts === 'string' ? { message: opts } : opts;
    return new Promise((resolve) => {
      setDialogState({
        isOpen: true,
        isConfirm: false,
        title: options.title || '提示',
        message: options.message,
        type: options.type || 'info',
        confirmText: options.confirmText || '确定',
        resolve: () => {
          setDialogState(null);
          resolve();
        }
      });
    });
  };

  const showConfirm = (opts: ConfirmOptions | string): Promise<boolean> => {
    const options: ConfirmOptions = typeof opts === 'string' ? { message: opts } : opts;
    return new Promise((resolve) => {
      setDialogState({
        isOpen: true,
        isConfirm: true,
        title: options.title || (options.isDestructive ? '确认删除' : '确认操作'),
        message: options.message,
        type: options.type || (options.isDestructive ? 'error' : 'warning'),
        confirmText: options.confirmText || (options.isDestructive ? '确认删除' : '确认'),
        cancelText: options.cancelText || '取消',
        isDestructive: options.isDestructive,
        resolve: (confirmed: boolean) => {
          setDialogState(null);
          resolve(confirmed);
        }
      });
    });
  };

  // 全局桥接挂载（供兜底与非 React 快速调用）
  useEffect(() => {
    (window as any).__showCustomAlert = showAlert;
    (window as any).__showCustomConfirm = showConfirm;
    (window as any).__showCustomToast = showToast;
  }, []);

  // 快捷键支持：Esc 取消，Enter 确认
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!dialogState || !dialogState.isOpen) return;
      if (e.key === 'Escape') {
        e.preventDefault();
        dialogState.resolve?.(false);
      } else if (e.key === 'Enter') {
        e.preventDefault();
        dialogState.resolve?.(true);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [dialogState]);

  const renderIcon = (type: DialogType, isDestructive?: boolean) => {
    if (isDestructive) {
      return (
        <div className="w-10 h-10 rounded-xl bg-red-50 border border-red-100 text-red-600 flex items-center justify-center flex-shrink-0">
          <Trash2 className="w-5 h-5" />
        </div>
      );
    }
    switch (type) {
      case 'success':
        return (
          <div className="w-10 h-10 rounded-xl bg-emerald-50 border border-emerald-100 text-emerald-600 flex items-center justify-center flex-shrink-0">
            <CheckCircle2 className="w-5 h-5" />
          </div>
        );
      case 'error':
        return (
          <div className="w-10 h-10 rounded-xl bg-red-50 border border-red-100 text-red-600 flex items-center justify-center flex-shrink-0">
            <AlertCircle className="w-5 h-5" />
          </div>
        );
      case 'warning':
        return (
          <div className="w-10 h-10 rounded-xl bg-amber-50 border border-amber-100 text-amber-600 flex items-center justify-center flex-shrink-0">
            <AlertTriangle className="w-5 h-5" />
          </div>
        );
      case 'info':
      default:
        return (
          <div className="w-10 h-10 rounded-xl bg-blue-50 border border-blue-100 text-blue-600 flex items-center justify-center flex-shrink-0">
            <Info className="w-5 h-5" />
          </div>
        );
    }
  };

  return (
    <DialogContext.Provider value={{ showAlert, showConfirm, showToast }}>
      {children}

      {/* 1. 全局模态弹窗 */}
      {dialogState && dialogState.isOpen && (
        <div
          className="fixed inset-0 z-[9999] bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in duration-200"
          onClick={() => dialogState.resolve?.(false)}
        >
          <div
            className="bg-white rounded-2xl max-w-md w-full p-5 border border-gray-200/80 shadow-2xl space-y-4 animate-in zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start space-x-3.5">
              {renderIcon(dialogState.type, dialogState.isDestructive)}
              <div className="flex-1 min-w-0">
                <h3 className="text-sm font-bold text-gray-900 leading-snug">
                  {dialogState.title}
                </h3>
                <p className="text-xs text-gray-600 mt-1.5 leading-relaxed break-words whitespace-pre-line">
                  {dialogState.message}
                </p>
              </div>
            </div>

            <div className="flex items-center justify-end space-x-2 pt-2 border-t border-gray-100">
              {dialogState.isConfirm && (
                <button
                  type="button"
                  onClick={() => dialogState.resolve?.(false)}
                  className="px-4 py-2 rounded-xl text-xs text-gray-600 hover:text-gray-900 hover:bg-gray-100 font-medium transition-colors cursor-pointer"
                >
                  {dialogState.cancelText || '取消'}
                </button>
              )}
              <button
                type="button"
                onClick={() => dialogState.resolve?.(true)}
                className={`px-4 py-2 rounded-xl text-xs font-semibold text-white shadow-xs transition-all cursor-pointer active:scale-95 ${
                  dialogState.isDestructive
                    ? 'bg-red-600 hover:bg-red-700 active:bg-red-800'
                    : 'bg-blue-600 hover:bg-blue-700 active:bg-blue-800'
                }`}
              >
                {dialogState.confirmText}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 2. 全局轻量级 Toast 提示栈 */}
      <div className="fixed bottom-6 right-6 z-[9999] flex flex-col space-y-2 pointer-events-none max-w-sm w-full">
        {toasts.map((t) => {
          let badgeColor = 'bg-emerald-500';
          let textColor = 'text-white';
          if (t.type === 'error') badgeColor = 'bg-red-500';
          if (t.type === 'warning') badgeColor = 'bg-amber-500';
          if (t.type === 'info') badgeColor = 'bg-blue-500';

          return (
            <div
              key={t.id}
              className="pointer-events-auto flex items-center justify-between space-x-3 px-4 py-2.5 rounded-xl bg-gray-900 text-white shadow-xl border border-gray-800 text-xs animate-in fade-in slide-in-from-bottom-2 duration-200"
            >
              <div className="flex items-center space-x-2 min-w-0">
                <span className={`w-2 h-2 rounded-full ${badgeColor} flex-shrink-0`} />
                <span className={`truncate leading-normal ${textColor}`}>{t.message}</span>
              </div>
              <button
                type="button"
                onClick={() => {
                  setToasts(prev => prev.filter(item => item.id !== t.id));
                }}
                className="text-gray-400 hover:text-white p-0.5 rounded transition-colors cursor-pointer flex-shrink-0"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          );
        })}
      </div>
    </DialogContext.Provider>
  );
};
