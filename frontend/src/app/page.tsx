import Link from "next/link";

const principles = [
  {
    number: "01",
    title: "从真实学习出发",
    description: "长期保留学习、测评与复习记录，让每一次进步都有依据。",
  },
  {
    number: "02",
    title: "让成长可以重算",
    description: "掌握状态与原始证据分离，算法升级也不会抹去孩子的历史。",
  },
  {
    number: "03",
    title: "把决定留给家庭",
    description: "老师有限授权，AI 在明确规则内提供建议，家长始终拥有控制权。",
  },
];

export default function Home() {
  return (
    <>
      <section className="hero section-shell">
        <div className="hero-copy">
          <p className="eyebrow">长期学习与成长档案</p>
          <h1>
            看见每一步学习，
            <span>陪伴每一段成长。</span>
          </h1>
          <p className="hero-description">
            Growth Learning 连接家庭、孩子与经授权的老师，从汉字学习开始，建立可解释、可延续的成长记录。
          </p>
          <div className="hero-actions">
            <Link className="button button-primary" href="/status">
              查看开发状态
            </Link>
            <a className="button button-secondary" href="#foundation">
              了解设计原则
            </a>
          </div>
        </div>

        <aside className="foundation-card" aria-label="Phase 1 工程状态">
          <div className="foundation-card-header">
            <span className="status-dot" aria-hidden="true" />
            <span>Phase 1 · Foundation</span>
          </div>
          <p className="foundation-value">工程基础搭建中</p>
          <p className="foundation-note">
            当前阶段专注于稳定的架构、开发环境与质量基线，不填充虚假业务数据。
          </p>
          <dl className="foundation-list">
            <div>
              <dt>Frontend</dt>
              <dd>Next.js</dd>
            </div>
            <div>
              <dt>Backend</dt>
              <dd>FastAPI</dd>
            </div>
            <div>
              <dt>Data</dt>
              <dd>Postgres</dd>
            </div>
          </dl>
        </aside>
      </section>

      <section className="principles section-shell" id="foundation">
        <div className="section-heading">
          <p className="eyebrow">Product foundation</p>
          <h2>为五年、十年后的成长而设计</h2>
          <p>先把证据、边界和信任建立好，再逐步扩展学习体验。</p>
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

      <section className="next-step section-shell">
        <div>
          <p className="eyebrow">当前里程碑</p>
          <h2>保持基础简单，也保持方向清晰。</h2>
        </div>
        <p>
          本阶段只交付可运行、可测试的应用骨架。家庭权限、汉字学习和自适应复习会在后续里程碑中按真实用例逐步实现。
        </p>
      </section>
    </>
  );
}

