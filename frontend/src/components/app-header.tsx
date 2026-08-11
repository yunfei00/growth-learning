import Link from "next/link";

export function AppHeader() {
  return (
    <header className="site-header">
      <Link className="brand" href="/" aria-label="Growth Learning 首页">
        <span className="brand-mark" aria-hidden="true">
          生
        </span>
        <span>Growth Learning</span>
      </Link>
      <nav aria-label="主要导航">
        <Link href="/">首页</Link>
        <Link href="/status">开发状态</Link>
      </nav>
    </header>
  );
}

