import { useState, type FormEvent } from "react";

import loginBackgroundVideo from "../assets/login-bg.mp4";

type AuthMode = "login" | "register";

type Props = {
  error: string | null;
  loading: boolean;
  onSubmit: (mode: AuthMode, loginId: string, password: string) => void;
};

export function AuthPane({ error, loading, onSubmit }: Props) {
  const [mode, setMode] = useState<AuthMode>("login");
  const [loginId, setLoginId] = useState("");
  const [password, setPassword] = useState("");
  const [passwordVisible, setPasswordVisible] = useState(false);

  const title = mode === "login" ? "登录工作室" : "注册账号";
  const actionLabel = mode === "login" ? "登录" : "注册并进入";
  const canSubmit = loginId.trim().length >= 2 && password.length >= 6 && !loading;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) return;
    onSubmit(mode, loginId, password);
  }

  return (
    <main className="figma-auth-screen" aria-label="登录注册">
      <video
        aria-hidden="true"
        autoPlay
        className="figma-auth-video"
        loop
        muted
        playsInline
        preload="metadata"
        src={loginBackgroundVideo}
      />
      <div className="figma-auth-video-tint" aria-hidden="true" />
      <section className="figma-auth-card">
        <div className="figma-auth-copy">
          <div className="figma-auth-brand">NovelScript AI</div>
          <h1>{title}</h1>
          <p>登录后项目会按账号隔离保存，继续上传小说、设计风格并生成场景计划。</p>
        </div>

        <div className="figma-auth-switch" role="tablist" aria-label="认证方式">
          <button
            aria-selected={mode === "login"}
            className={mode === "login" ? "active" : ""}
            role="tab"
            type="button"
            onClick={() => setMode("login")}
          >
            登录
          </button>
          <button
            aria-selected={mode === "register"}
            className={mode === "register" ? "active" : ""}
            role="tab"
            type="button"
            onClick={() => setMode("register")}
          >
            注册
          </button>
        </div>

        <form className="figma-auth-form" onSubmit={handleSubmit}>
          <label>
            <span>账号</span>
            <input
              autoComplete="username"
              autoFocus
              aria-label="账号"
              placeholder="输入账号"
              value={loginId}
              onChange={(event) => setLoginId(event.target.value)}
            />
          </label>
          <label>
            <span>密码</span>
            <div className="figma-auth-password">
              <input
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                aria-label="密码"
                placeholder="至少 6 位"
                type={passwordVisible ? "text" : "password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
              <button
                aria-label={passwordVisible ? "隐藏密码" : "显示密码"}
                type="button"
                onClick={() => setPasswordVisible((value) => !value)}
              >
                {passwordVisible ? "隐藏" : "显示"}
              </button>
            </div>
          </label>

          {error ? <p className="figma-auth-error">{error}</p> : null}

          <button className="figma-primary figma-auth-submit" disabled={!canSubmit} type="submit">
            {loading ? "处理中..." : actionLabel}
          </button>
        </form>
      </section>
    </main>
  );
}
