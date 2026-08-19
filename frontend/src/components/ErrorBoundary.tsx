import { AlertTriangle, RotateCcw } from "lucide-react";
import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryState {
  error: Error | null;
}

export class ErrorBoundary extends Component<{ children: ReactNode }, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("OpsPilot render failure", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <main className="fatal-state" role="alert">
        <AlertTriangle size={28} aria-hidden="true" />
        <h1>控制台界面发生异常</h1>
        <p>
          数据和后台任务不会受到影响。请重新加载界面；若问题持续，请记录当前时间并联系平台管理员。
        </p>
        <details>
          <summary>技术信息</summary>
          <code>{this.state.error.message}</code>
        </details>
        <button className="button button--primary" onClick={() => window.location.reload()}>
          <RotateCcw size={16} aria-hidden="true" /> 重新加载
        </button>
      </main>
    );
  }
}
