import { useMutation, useQuery } from "@tanstack/react-query";
import { Activity, AlertCircle, Eye, EyeOff, LoaderCircle, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { ApiError, authApi } from "../api";
import { useAuth } from "../auth/authContext";
import "./login.css";
import { queryKeys } from "../query/queryKeys";

function LoginBrandPanel() {
  return (
    <div className="login-brand">
      <div className="login-brand__header">
        <div className="login-brand__logo">
          <Activity size={24} aria-hidden="true" />
        </div>
        <div className="login-brand__title">
          <strong>OPSPILOT</strong>
          <span>云原生运维控制台</span>
        </div>
      </div>
      <p className="login-brand__slogan">Linux 运行状态与审计入口</p>
    </div>
  );
}

interface LoginError {
  title: string;
  message: string;
  requestId?: string;
}

function LoginFormPanel() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loginError, setLoginError] = useState<LoginError | null>(null);
  const { data: status } = useQuery({
    queryKey: queryKeys.auth.status,
    queryFn: authApi.status,
    staleTime: 300_000,
  });
  const loginMutation = useMutation({
    mutationFn: async () => {
      setLoginError(null);
      await login(username, password);
    },
    onError: (error: Error) => {
      const apiError = error instanceof ApiError ? error : undefined;
      if (apiError?.code === "INVALID_CREDENTIALS") {
        setLoginError({
          title: "登录失败",
          message: "账号或密码不正确",
          requestId: apiError.requestId,
        });
      } else if (apiError?.code === "ACCOUNT_DISABLED") {
        setLoginError({
          title: "账号已禁用",
          message: "账号已被禁用，请联系系统管理员",
          requestId: apiError.requestId,
        });
      } else {
        setLoginError({
          title: "登录服务暂时不可用",
          message: "登录服务暂时不可用，请稍后重试。",
          requestId: apiError?.requestId,
        });
      }
    },
  });
  const isSubmitting = loginMutation.isPending;
  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!isSubmitting && username && password) loginMutation.mutate();
  };
  const safeDescription = status
    ? `${status.executor} · 写操作${status.write_operations ? "受控" : "关闭"}`
    : "Executor 与写操作状态尚未检查";

  return (
    <div className="login-form-panel">
      <div className="login-card">
        <div className="login-card__icon">
          <ShieldCheck size={24} aria-hidden="true" />
        </div>
        <h1 className="login-card__title">登录 OPSPILOT 运维控制台</h1>
        <p className="login-card__desc">使用运维账号进入当前环境。</p>
        {loginError && (
          <div className="login-error" role="alert">
            <AlertCircle size={16} aria-hidden="true" />
            <div className="login-error__body">
              <strong>{loginError.title}</strong>
              <span>{loginError.message}</span>
              {loginError.requestId && <small>Request ID：{loginError.requestId}</small>}
            </div>
          </div>
        )}
        <form className="login-form" onSubmit={handleSubmit} noValidate>
          <div className="login-form__field">
            <label htmlFor="login-username">账号</label>
            <input
              id="login-username"
              type="text"
              placeholder="请输入账号"
              autoComplete="username"
              autoFocus
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              disabled={isSubmitting}
              required
            />
          </div>
          <div className="login-form__field">
            <label htmlFor="login-password">密码</label>
            <div className="login-form__password-wrapper">
              <input
                id="login-password"
                type={showPassword ? "text" : "password"}
                placeholder="请输入密码"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                disabled={isSubmitting}
                required
              />
              <button
                type="button"
                className="login-form__toggle-pw"
                onClick={() => setShowPassword((value) => !value)}
                aria-label={showPassword ? "隐藏密码" : "显示密码"}
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>
          <button
            type="submit"
            className="login-form__submit"
            disabled={isSubmitting || !username || !password}
            aria-live="polite"
          >
            {isSubmitting ? (
              <>
                <LoaderCircle size={18} className="spin" aria-hidden="true" />
                <span>正在验证</span>
              </>
            ) : (
              "进入控制台"
            )}
          </button>
        </form>
        <div className="login-security-context">
          <ShieldCheck size={14} aria-hidden="true" />
          <div className="login-security-context__body">
            <strong>
              {status ? (status.safe_mode ? "安全模拟环境" : "受控环境") : "安全状态尚未检查"}
            </strong>
            <span>{safeDescription}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <div className="login-page">
      <div className="login-container">
        <LoginBrandPanel />
        <LoginFormPanel />
      </div>
    </div>
  );
}
