"use client";

import Link from "next/link";

import { useAuth } from "@/components/auth-provider";

const principles = [
  {
    number: "01",
    title: "家庭是数据边界",
    description: "每个家庭独立管理成员与孩子，所有访问都经过服务端权限验证。",
  },
  {
    number: "02",
    title: "记录真实成长",
    description: "从真实家庭和孩子资料开始，不用虚构指标装饰尚未发生的学习。",
  },
  {
    number: "03",
    title: "为长期陪伴设计",
    description: "孩子拥有独立成长档案，年龄由出生日期动态计算，记录能够持续多年。",
  },
];

export default function LandingPage() {
  const { status } = useAuth();

  return (
    <>
      <section className="hero section-shell">
        <div className="hero-copy">
          <p className="eyebrow">家庭学习与成长档案</p>
          <h1>
            看见每一步学习，
            <span>陪伴每一段成长。</span>
          </h1>
          <p className="hero-description">
            成长学习从家庭和孩子的真实信息出发，为长期学习建立清晰、安全、可持续的基础。
          </p>
          <div className="hero-actions">
            {status === "authenticated" ? (
              <Link className="button button-primary" href="/home">
                进入家长首页
              </Link>
            ) : (
              <>
                <Link className="button button-primary" href="/register">
                  创建账号
                </Link>
                <Link className="button button-secondary" href="/login">
                  登录
                </Link>
              </>
            )}
          </div>
        </div>

        <aside className="foundation-card" aria-label="家庭成长档案说明">
          <div className="foundation-card-header">
            <span className="status-dot" aria-hidden="true" />
            <span>Family first</span>
          </div>
          <p className="foundation-value">从一个真实家庭开始</p>
          <p className="foundation-note">
            创建账号后，建立家庭并添加第一个孩子。以后每一项学习记录都围绕你选择的孩子展开。
          </p>
          <dl className="foundation-list">
            <div>
              <dt>账户</dt>
              <dd>安全登录</dd>
            </div>
            <div>
              <dt>家庭</dt>
              <dd>权限隔离</dd>
            </div>
            <div>
              <dt>孩子</dt>
              <dd>长期档案</dd>
            </div>
          </dl>
        </aside>
      </section>

      <section className="principles section-shell">
        <div className="section-heading">
          <p className="eyebrow">产品基础</p>
          <h2>先建立可信的家庭与身份基础</h2>
          <p>登录状态、家庭权限与孩子资料都来自真实数据库，并在每一次请求中验证访问边界。</p>
        </div>
        <div className="principle-grid">
          {principles.map((principle) => (
            <article className="principle-card" key={principle.number}>
              <span>{principle.number}</span>
              <h3>{principle.title}</h3>
              <p>{principle.description}</p>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}
