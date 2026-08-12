"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, Suspense, useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { ApiClientError, listFamilies } from "@/lib/api/client";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { status, login } = useAuth();
  const [email, setEmail] = useState(searchParams.get("email") ?? "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (status === "authenticated") {
      router.replace("/home");
    }
  }, [router, status]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);

    try {
      await login(email, password);
      const families = await listFamilies();
      router.replace(families.length === 0 ? "/onboarding" : "/home");
      router.refresh();
    } catch (requestError) {
      setError(
        requestError instanceof ApiClientError
          ? requestError.message
          : "登录失败，请稍后重试",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="auth-page section-shell">
      <div className="auth-card">
        <p className="eyebrow">成长学习</p>
        <h1>登录</h1>
        <p className="auth-intro">回到你的家庭成长空间。</p>

        {searchParams.get("registered") === "1" ? (
          <p className="form-message form-success">账号创建成功，请登录。</p>
        ) : null}

        <form className="form-stack" onSubmit={(event) => void handleSubmit(event)}>
          <label>
            <span>邮箱</span>
            <input
              autoComplete="email"
              inputMode="email"
              onChange={(event) => setEmail(event.target.value)}
              placeholder="name@example.com"
              required
              type="email"
              value={email}
            />
          </label>
          <label>
            <span>密码</span>
            <input
              autoComplete="current-password"
              onChange={(event) => setPassword(event.target.value)}
              placeholder="输入密码"
              required
              type="password"
              value={password}
            />
          </label>

          {error ? (
            <p className="form-message form-error" role="alert">
              {error}
            </p>
          ) : null}

          <button className="button button-primary form-submit" disabled={isSubmitting} type="submit">
            {isSubmitting ? "正在登录…" : "登录"}
          </button>
        </form>

        <p className="auth-alternate">
          还没有账号？<Link href="/register">创建账号</Link>
        </p>
      </div>
    </section>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <section className="center-state section-shell">
          <span className="loading-spinner" aria-hidden="true" />
          <p>正在加载登录页面…</p>
        </section>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
