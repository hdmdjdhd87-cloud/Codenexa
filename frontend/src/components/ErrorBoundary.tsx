import { Component, type ErrorInfo, type ReactNode } from "react";
import t from "@/i18n";

interface Props {
  children: ReactNode;
  onReset?: () => void;
}

interface State {
  hasError: boolean;
}

/**
 * Ловит ошибки рендера внутри модулей (например AI Docs). Раньше
 * необработанное исключение внутри lazy-loaded компонента размонтировало
 * всё дерево React → пользователь видел полностью чёрный экран (см.
 * реальный баг с asyncpg jsonb, зафиксированный ранее). Теперь — понятный
 * экран с кнопками "Повторить"/"Назад" вместо этого (п.41 промпта).
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error("ErrorBoundary caught:", error, info.componentStack);
  }

  handleRetry = () => {
    this.setState({ hasError: false });
    this.props.onReset?.();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center py-16 text-center px-6" role="alert">
          <div className="w-12 h-12 rounded-2xl bg-error/10 border border-error/30 mb-4" aria-hidden="true" />
          <p className="text-text-primary font-medium text-[15px]">Что-то пошло не так.</p>
          <div className="flex gap-2 mt-5">
            <button
              onClick={this.handleRetry}
              className="px-5 py-2.5 rounded-xl bg-accent text-white text-[13px] font-semibold"
            >
              {t("common.retry")}
            </button>
            <button
              onClick={() => window.history.back()}
              className="px-5 py-2.5 rounded-xl bg-surface-elevated border border-border text-[13px] font-semibold text-text-primary"
            >
              {t("common.back")}
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
