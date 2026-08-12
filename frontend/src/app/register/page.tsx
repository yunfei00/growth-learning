"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { ApiClientError, registerAccount } from "@/lib/api/client";

export default function RegisterPage() {
  const router = useRouter();
  const { status } = useAuth();
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
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

    if (password !== confirmPassword) {
      setError("两次输入的密码不一致");
      return;
    }

    setIsSubmitting(true);
    try {
      await registerAccount({ display_name: displayName, email, password });
      router.push(`/login?registered=1&email=${encodeURIComponent(email)}`);
    } catch (requestError) {
      setError(
        requestError instanceof ApiClientError
          ? requestError.message
          : "注册失败，请稍后重试",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="auth-page section-shell">
      <div className="auth-card">
        <p className="eyebrow">成长学习</p>
        <h1>创建账号</h1>
        <p className="auth-intro">为家庭建立安全、独立的成长空间。</p>

        <form className="form-stack" onSubmit={(event) => void handleSubmit(event)}>
          <label>
            <span>姓名</span>
            <input
              autoComplete="name"
              maxLength={80}
              onChange={(event) => setDisplayName(event.target.value)}
              placeholder="你的姓名"
              required
              value={displayName}
            />
          </label>
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
              autoComplete="new-password"
              minLength={10}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="至少 10 个字符"
              required
              type="password"
              value={password}
            />
          </label>
          <label>
            <span>确认密码</span>
            <input
              autoComplete="new-password"
              minLength={10}
              onChange={(event) => setConfirmPassword(event.target.value)}
              placeholder="再次输入密码"
              required
              type="password"
              value={confirmPassword}
            />
          </label>

          {error ? (
            <p className="form-message form-error" role="alert">
              {error}
            </p>
          ) : null}

          <button className="button button-primary form-submit" disabled={isSubmitting} type="submit">
            {isSubmitting ? "正在创建…" : "注册"}
          </button>
        </form>

        <p className="auth-alternate">
          已有账号？<Link href="/login">登录</Link>
        </p>
      </div>
    </section>
  );
}
