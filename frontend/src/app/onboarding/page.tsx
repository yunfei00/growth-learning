"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";

import { ProtectedPage } from "@/components/protected-page";
import {
  ApiClientError,
  type ChildGender,
  type FamilyInvitation,
  acceptFamilyInvitation,
  acceptPendingFamilyInvitation,
  createChild,
  createFamily,
  listChildren,
  listFamilies,
  listPendingFamilyInvitations,
} from "@/lib/api/client";
import {
  ACTIVE_FAMILY_KEY,
  activeChildKey,
  selectRemembered,
} from "@/lib/household-selection";

type OnboardingState =
  | { kind: "loading" }
  | { kind: "family" }
  | { kind: "child"; familyId: string; familyName: string; canManage: boolean };

function OnboardingContent() {
  const router = useRouter();
  const [state, setState] = useState<OnboardingState>({ kind: "loading" });
  const [familyName, setFamilyName] = useState("");
  const [invitationCode, setInvitationCode] = useState("");
  const [pendingInvitations, setPendingInvitations] = useState<FamilyInvitation[]>([]);
  const [displayName, setDisplayName] = useState("");
  const [nickname, setNickname] = useState("");
  const [birthDate, setBirthDate] = useState("");
  const [gender, setGender] = useState<ChildGender | "">("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([listFamilies(), listPendingFamilyInvitations()])
      .then(async ([families, pending]) => {
        if (!cancelled) setPendingInvitations(pending);
        if (families.length === 0) {
          return { kind: "family" as const };
        }
        const family = selectRemembered(
          families,
          window.localStorage.getItem(ACTIVE_FAMILY_KEY),
        );
        if (!family) return { kind: "family" as const };
        window.localStorage.setItem(ACTIVE_FAMILY_KEY, family.id);
        const children = await listChildren(family.id);
        return { kind: "existing" as const, family, children };
      })
      .then((result) => {
        if (cancelled) {
          return;
        }
        if (result.kind === "family") {
          setState({ kind: "family" });
        } else if (result.children.length > 0) {
          router.replace("/home");
        } else {
          setState({
            kind: "child",
            familyId: result.family.id,
            familyName: result.family.name,
            canManage: result.family.current_role === "admin",
          });
        }
      })
      .catch((requestError: unknown) => {
        if (!cancelled) {
          setError(
            requestError instanceof ApiClientError
              ? requestError.message
              : "暂时无法加载家庭信息",
          );
          setState({ kind: "family" });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [router]);

  const handleFamily = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);
    try {
      const family = await createFamily(familyName);
      window.localStorage.setItem(ACTIVE_FAMILY_KEY, family.id);
      setState({
        kind: "child",
        familyId: family.id,
        familyName: family.name,
        canManage: true,
      });
    } catch (requestError) {
      setError(
        requestError instanceof ApiClientError ? requestError.message : "家庭创建失败",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChild = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (state.kind !== "child") {
      return;
    }
    setError("");
    setIsSubmitting(true);
    try {
      const child = await createChild(state.familyId, {
        display_name: displayName,
        nickname: nickname || null,
        birth_date: birthDate,
        gender: gender || null,
      });
      window.localStorage.setItem(ACTIVE_FAMILY_KEY, state.familyId);
      window.localStorage.setItem(activeChildKey(state.familyId), child.id);
      window.dispatchEvent(new Event("growth-learning:household-changed"));
      router.replace("/home");
      router.refresh();
    } catch (requestError) {
      setError(
        requestError instanceof ApiClientError ? requestError.message : "孩子资料创建失败",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const finishInvitationAcceptance = async (
    familyId: string,
    familyName: string,
    role: "admin" | "companion",
  ) => {
    window.localStorage.setItem(ACTIVE_FAMILY_KEY, familyId);
    window.dispatchEvent(new Event("growth-learning:household-changed"));
    const children = await listChildren(familyId);
    if (children.length > 0) {
      router.replace("/home");
      router.refresh();
    } else {
      setState({ kind: "child", familyId, familyName, canManage: role === "admin" });
    }
  };

  const handleInvitationCode = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);
    try {
      const accepted = await acceptFamilyInvitation(invitationCode.trim());
      await finishInvitationAcceptance(accepted.family_id, accepted.family_name, accepted.role);
    } catch (requestError) {
      setError(
        requestError instanceof ApiClientError ? requestError.message : "家庭邀请无法接受",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handlePendingInvitation = async (invitation: FamilyInvitation) => {
    setError("");
    setIsSubmitting(true);
    try {
      const accepted = await acceptPendingFamilyInvitation(invitation.id);
      await finishInvitationAcceptance(accepted.family_id, accepted.family_name, accepted.role);
    } catch (requestError) {
      setError(
        requestError instanceof ApiClientError ? requestError.message : "家庭邀请无法接受",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  if (state.kind === "loading") {
    return (
      <section className="center-state section-shell">
        <span className="loading-spinner" aria-hidden="true" />
        <p>正在准备你的家庭空间…</p>
      </section>
    );
  }

  return (
    <section className="onboarding-page section-shell">
      <div className="onboarding-card">
        <div className="step-indicator" aria-label={`第 ${state.kind === "family" ? 1 : 2} 步，共 2 步`}>
          <span className="step-active" />
          <span className={state.kind === "child" ? "step-active" : ""} />
        </div>

        {state.kind === "family" ? (
          <>
            <p className="eyebrow">欢迎使用成长学习</p>
            <h1>创建或加入家庭</h1>
            <p className="auth-intro">家庭是成员和孩子资料的安全边界。已有邀请时，请直接加入同一个家庭。</p>
            {pendingInvitations.length > 0 ? (
              <div className="onboarding-invitations">
                <h2>等待你的家庭邀请</h2>
                {pendingInvitations.map((invitation) => (
                  <article key={invitation.id}>
                    <div>
                      <strong>{invitation.family_name}</strong>
                      <small>{invitation.created_by_display_name} 邀请你加入</small>
                    </div>
                    <button
                      className="button button-primary"
                      disabled={isSubmitting}
                      onClick={() => void handlePendingInvitation(invitation)}
                      type="button"
                    >
                      接受邀请
                    </button>
                  </article>
                ))}
              </div>
            ) : null}
            <form className="form-stack onboarding-join-form" onSubmit={(event) => void handleInvitationCode(event)}>
              <label>
                <span>家庭邀请码</span>
                <input
                  maxLength={80}
                  onChange={(event) => setInvitationCode(event.target.value)}
                  placeholder="输入家庭管理员发给你的邀请码"
                  required
                  value={invitationCode}
                />
              </label>
              <button className="button button-secondary" disabled={isSubmitting} type="submit">
                加入已有家庭
              </button>
            </form>
            <div className="onboarding-divider"><span>或创建新家庭</span></div>
            <form className="form-stack" onSubmit={(event) => void handleFamily(event)}>
              <label>
                <span>家庭名称</span>
                <input
                  autoFocus
                  maxLength={100}
                  onChange={(event) => setFamilyName(event.target.value)}
                  placeholder="例如：我们家、贾家"
                  required
                  value={familyName}
                />
              </label>
              <button className="button button-primary form-submit" disabled={isSubmitting} type="submit">
                {isSubmitting ? "正在创建…" : "下一步"}
              </button>
            </form>
            {error ? (
              <p className="form-message form-error" role="alert">{error}</p>
            ) : null}
          </>
        ) : (
          <>
            <p className="eyebrow">{state.familyName} · 第 2 步</p>
            <h1>{state.canManage ? "添加第一个孩子" : "已加入家庭"}</h1>
            {state.canManage ? (
              <>
                <p className="auth-intro">出生日期用于动态计算年龄，不会保存会过期的年龄数字。</p>
                <form className="form-stack" onSubmit={(event) => void handleChild(event)}>
              <label>
                <span>姓名</span>
                <input
                  autoFocus
                  maxLength={80}
                  onChange={(event) => setDisplayName(event.target.value)}
                  placeholder="孩子姓名"
                  required
                  value={displayName}
                />
              </label>
              <label>
                <span>昵称（可选）</span>
                <input
                  maxLength={80}
                  onChange={(event) => setNickname(event.target.value)}
                  placeholder="家里常用的称呼"
                  value={nickname}
                />
              </label>
              <label>
                <span>出生日期</span>
                <input
                  max={new Date().toISOString().slice(0, 10)}
                  onChange={(event) => setBirthDate(event.target.value)}
                  required
                  type="date"
                  value={birthDate}
                />
              </label>
              <label>
                <span>性别（可选）</span>
                <select
                  onChange={(event) => setGender(event.target.value as ChildGender | "")}
                  value={gender}
                >
                  <option value="">暂不填写</option>
                  <option value="female">女</option>
                  <option value="male">男</option>
                  <option value="other">其他</option>
                </select>
              </label>
              {error ? (
                <p className="form-message form-error" role="alert">
                  {error}
                </p>
              ) : null}
              <button className="button button-primary form-submit" disabled={isSubmitting} type="submit">
                {isSubmitting ? "正在完成…" : "完成"}
              </button>
                </form>
              </>
            ) : (
              <div className="onboarding-invitations">
                <p>这个家庭暂时还没有孩子资料。请让家庭管理员添加孩子后再进入学习空间。</p>
                <button className="button button-secondary" onClick={() => window.location.reload()} type="button">重新检查</button>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}

export default function OnboardingPage() {
  return (
    <ProtectedPage>
      <OnboardingContent />
    </ProtectedPage>
  );
}
