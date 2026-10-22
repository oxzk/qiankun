import { Component, type ErrorInfo, type ReactNode } from "react";
import { Button } from "@/components/ui/button";

export interface ErrorBoundaryProps {
  /**
   * 受保护的子节点。
   */
  children: ReactNode;
}

interface ErrorBoundaryState {
  /**
   * 是否已捕获渲染错误。
   */
  hasError: boolean;
  /**
   * 错误消息。
   */
  message: string;
}

/**
 * 页面级错误边界, 避免单页崩溃白屏。
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  /**
   * 初始化错误边界状态。
   */
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, message: "" };
  }

  /**
   * 从渲染错误派生 UI 状态。
   */
  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return {
      hasError: true,
      message: error.message || "页面渲染失败",
    };
  }

  /**
   * 记录渲染错误详情。
   */
  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("页面渲染错误", error, info.componentStack);
  }

  /**
   * 重置错误状态并刷新当前页。
   */
  private handleRetry = (): void => {
    this.setState({ hasError: false, message: "" });
    window.location.reload();
  };

  /**
   * 渲染子树或错误回退。
   */
  render(): ReactNode {
    if (!this.state.hasError) return this.props.children;

    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 px-4 text-center">
        <div>
          <h1 className="text-2xl font-semibold">页面出错了</h1>
          <p className="mt-2 max-w-md text-sm text-muted-foreground">{this.state.message}</p>
        </div>
        <Button type="button" onClick={this.handleRetry}>
          重试
        </Button>
      </div>
    );
  }
}
