"use client";

import Link from "next/link";
import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ProtectedPage } from "@/components/protected-page";
import {
  ApiClientError,
  type AdultChildRelation,
  type Child,
  type ChildGender,
  type FamilyActivity,
  type FamilyInvitation,
  type FamilyMember,
  type FamilyRole,
  archiveChild,
  createChild,
  createFamilyInvitation,
  listChildren,
  listFamilyActivity,
  listFamilyInvitations,
  listFamilyMembers,
  removeFamilyMember,
  restoreChild,
  revokeFamilyInvitation,
  setAdultChildRelation,
  updateChild,
  updateFamily,
  updateFamilyMemberRole,
} from "@/lib/api/client";

const RELATIONS: Array<[AdultChildRelation, string]> = [
  ["father", "爸爸"],
  ["mother", "妈妈"],
  ["grandfather", "爷爷 / 外公"],
  ["grandmother", "奶奶 / 外婆"],
  ["guardian", "监护人"],
  ["other", "其他关系"],
];

function expiresTomorrow(): string {
  const value = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000);
  value.setMinutes(value.getMinutes() - value.getTimezoneOffset());
  return value.toISOString().slice(0, 16);
}

function FamilyManagementContent() {
  const {
    status,
    families,
    family,
    setActiveFamilyId,
    refresh: refreshHousehold,
  } = useActiveChild();
  const [members, setMembers] = useState<FamilyMember[]>([]);
  const [allChildren, setAllChildren] = useState<Child[]>([]);
  const [invitations, setInvitations] = useState<FamilyInvitation[]>([]);
  const [activity, setActivity] = useState<FamilyActivity[]>([]);
  const [familyName, setFamilyName] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<FamilyRole>("companion");
  const [inviteExpires, setInviteExpires] = useState(expiresTomorrow);
  const [oneTimeCode, setOneTimeCode] = useState("");
  const [childName, setChildName] = useState("");
  const [childNickname, setChildNickname] = useState("");
  const [childBirthDate, setChildBirthDate] = useState("");
  const [childGender, setChildGender] = useState<ChildGender | "">("");
  const [editingChildId, setEditingChildId] = useState("");
  const [working, setWorking] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const isAdmin = family?.current_role === "admin";

  const load = useCallback(async () => {
    if (!family) return;
    try {
      const [memberRows, childRows, activityRows, invitationRows] = await Promise.all([
        listFamilyMembers(family.id),
        listChildren(family.id, true),
        listFamilyActivity(family.id),
        family.current_role === "admin" ? listFamilyInvitations(family.id) : Promise.resolve([]),
      ]);
      setMembers(memberRows);
      setAllChildren(childRows);
      setActivity(activityRows);
      setInvitations(invitationRows);
      setFamilyName(family.name);
      setError("");
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "家庭资料暂时无法加载");
    }
  }, [family]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const activeChildren = useMemo(
    () => allChildren.filter((child) => !child.is_archived),
    [allChildren],
  );

  const run = async (key: string, action: () => Promise<void>, success: string) => {
    setWorking(key);
    setMessage("");
    setError("");
    try {
      await action();
      setMessage(success);
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "操作没有成功，请稍后重试");
    } finally {
      setWorking("");
    }
  };

  const renameFamily = async (event: FormEvent) => {
    event.preventDefault();
    if (!family || !isAdmin) return;
    await run("family-name", async () => {
      await updateFamily(family.id, familyName);
      await refreshHousehold();
    }, "家庭名称已保存。");
  };

  const invite = async (event: FormEvent) => {
    event.preventDefault();
    if (!family || !isAdmin) return;
    await run("invite", async () => {
      const created = await createFamilyInvitation(family.id, {
        email_constraint: inviteEmail.trim() || null,
        role_to_grant: inviteRole,
        expires_at: new Date(inviteExpires).toISOString(),
      });
      setOneTimeCode(created.invitation_code);
      setInviteEmail("");
      setInvitations(await listFamilyInvitations(family.id));
    }, "家庭邀请已创建。邀请码只在本次显示，请立即安全发送给对方。");
  };

  const submitChild = async (event: FormEvent) => {
    event.preventDefault();
    if (!family || !isAdmin) return;
    await run("child", async () => {
      const payload = {
        display_name: childName,
        nickname: childNickname || null,
        birth_date: childBirthDate,
        gender: childGender || null,
      };
      if (editingChildId) await updateChild(editingChildId, payload);
      else await createChild(family.id, payload);
      setChildName("");
      setChildNickname("");
      setChildBirthDate("");
      setChildGender("");
      setEditingChildId("");
      await Promise.all([load(), refreshHousehold()]);
    }, editingChildId ? "孩子资料已保存。" : "孩子已加入当前家庭。");
  };

  const startEditChild = (child: Child) => {
    setEditingChildId(child.id);
    setChildName(child.display_name);
    setChildNickname(child.nickname ?? "");
    setChildBirthDate(child.birth_date);
    setChildGender(child.gender ?? "");
  };

  if (status !== "ready" || !family) {
    return <section className="center-state section-shell"><span className="loading-spinner" /><p>正在打开家庭协作空间…</p></section>;
  }

  return (
    <section className="family-management-page section-shell">
      <header className="family-management-header">
        <div><p className="eyebrow">Family collaboration</p><h1>家庭成员与孩子</h1><p>同一家庭的成人共享孩子的真实学习、阅读、科学实验和成长记录。</p></div>
        <Link className="button button-secondary" href="/settings">返回家庭设置</Link>
      </header>

      {families.length > 1 ? <label className="family-page-switcher"><span>当前家庭</span><select onChange={(event) => setActiveFamilyId(event.target.value)} value={family.id}>{families.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label> : null}
      {error ? <p className="form-message form-error" role="alert">{error}</p> : null}
      {message ? <p className="form-message form-success" role="status">{message}</p> : null}

      <section className="family-management-card">
        <div><h2>家庭资料</h2><p>成员权限与亲子称谓分别管理，不会混在一起。</p></div>
        <form className="inline-family-form" onSubmit={(event) => void renameFamily(event)}><label><span>家庭名称</span><input disabled={!isAdmin} maxLength={100} onChange={(event) => setFamilyName(event.target.value)} required value={familyName} /></label>{isAdmin ? <button className="button button-secondary" disabled={working === "family-name"} type="submit">保存名称</button> : null}</form>
      </section>

      <section className="family-management-card">
        <div><h2>家庭成员</h2><p>管理员可管理家庭；陪伴者可共同学习和查看同一份孩子记录。</p></div>
        <div className="family-member-list">
          {members.map((member) => <article key={member.id}><div className="member-identity"><strong>{member.user.display_name}</strong><small>{member.user.email}</small></div><label><span>权限</span><select disabled={!isAdmin || working === member.id} onChange={(event) => void run(member.id, async () => { await updateFamilyMemberRole(family.id, member.id, event.target.value as FamilyRole); await load(); }, "成员权限已更新。")} value={member.role}><option value="admin">管理员</option><option value="companion">陪伴者</option></select></label>{activeChildren.map((child) => { const relation = member.relations.find((item) => item.child_id === child.id)?.relation ?? ""; return <label key={child.id}><span>与{child.nickname || child.display_name}的关系</span><select disabled={!isAdmin || working === `${member.id}:${child.id}`} onChange={(event) => { if (event.target.value) void run(`${member.id}:${child.id}`, async () => { await setAdultChildRelation(family.id, member.id, child.id, event.target.value as AdultChildRelation); await load(); }, "亲子关系已保存。"); }} value={relation}><option disabled value="">未设置</option>{RELATIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>; })}{isAdmin ? <button className="button button-danger" disabled={working === `remove:${member.id}`} onClick={() => { if (window.confirm(`确定将 ${member.user.display_name} 移出这个家庭吗？账号和历史学习证据不会被删除。`)) void run(`remove:${member.id}`, async () => { await removeFamilyMember(family.id, member.id); await load(); }, "成员已移出家庭，账号和学习历史均已保留。"); }} type="button">移出家庭</button> : null}</article>)}
        </div>
      </section>

      {isAdmin ? <section className="family-management-card"><div><h2>邀请成人加入</h2><p>家庭邀请与平台注册邀请码完全分离；每个家庭邀请码只可使用一次。</p></div><form className="family-invite-form" onSubmit={(event) => void invite(event)}><label><span>对方邮箱（推荐绑定）</span><input onChange={(event) => setInviteEmail(event.target.value)} placeholder="已有账号的邮箱" type="email" value={inviteEmail} /></label><label><span>加入后的权限</span><select onChange={(event) => setInviteRole(event.target.value as FamilyRole)} value={inviteRole}><option value="companion">陪伴者</option><option value="admin">管理员</option></select></label><label><span>有效期</span><input min={new Date().toISOString().slice(0, 16)} onChange={(event) => setInviteExpires(event.target.value)} required type="datetime-local" value={inviteExpires} /></label><button className="button button-primary" disabled={working === "invite"} type="submit">创建家庭邀请</button></form>{oneTimeCode ? <div className="one-time-invitation"><span>一次性家庭邀请码</span><code>{oneTimeCode}</code><button className="button button-secondary" onClick={() => void navigator.clipboard.writeText(oneTimeCode)} type="button">复制邀请码</button></div> : null}<div className="invitation-list">{invitations.map((invitation) => <article key={invitation.id}><div><strong>{invitation.email_constraint ?? "未绑定邮箱"}</strong><small>{invitation.role_to_grant === "admin" ? "管理员" : "陪伴者"} · {invitation.status}</small></div>{invitation.status === "active" ? <button className="button button-secondary" disabled={working === invitation.id} onClick={() => void run(invitation.id, async () => { await revokeFamilyInvitation(family.id, invitation.id); setInvitations(await listFamilyInvitations(family.id)); }, "邀请已撤销。") } type="button">撤销</button> : null}</article>)}</div></section> : null}

      <section className="family-management-card"><div><h2>孩子资料</h2><p>可添加多个孩子。归档只隐藏资料，不删除任何学习证据。</p></div><div className="family-child-list">{allChildren.map((child) => <article className={child.is_archived ? "archived" : ""} key={child.id}><div><strong>{child.display_name}</strong><small>{child.nickname || "暂无昵称"} · {child.birth_date}{child.is_archived ? " · 已归档" : ""}</small></div>{isAdmin ? <div><button className="button button-secondary" onClick={() => startEditChild(child)} type="button">编辑</button><button className="button button-secondary" disabled={working === `archive:${child.id}`} onClick={() => void run(`archive:${child.id}`, async () => { if (child.is_archived) await restoreChild(child.id); else await archiveChild(child.id); await Promise.all([load(), refreshHousehold()]); }, child.is_archived ? "孩子资料已恢复。" : "孩子资料已归档，历史证据未删除。") } type="button">{child.is_archived ? "恢复" : "归档"}</button></div> : null}</article>)}</div>{isAdmin ? <form className="family-child-form" onSubmit={(event) => void submitChild(event)}><h3>{editingChildId ? "编辑孩子资料" : "+ 添加孩子"}</h3><label><span>姓名</span><input maxLength={80} onChange={(event) => setChildName(event.target.value)} required value={childName} /></label><label><span>昵称（可选）</span><input maxLength={80} onChange={(event) => setChildNickname(event.target.value)} value={childNickname} /></label><label><span>出生日期</span><input max={new Date().toISOString().slice(0, 10)} onChange={(event) => setChildBirthDate(event.target.value)} required type="date" value={childBirthDate} /></label><label><span>性别</span><select onChange={(event) => setChildGender(event.target.value as ChildGender | "")} value={childGender}><option value="">暂不填写</option><option value="female">女</option><option value="male">男</option><option value="other">其他</option></select></label><button className="button button-primary" disabled={working === "child"} type="submit">{editingChildId ? "保存修改" : "添加孩子"}</button>{editingChildId ? <button className="button button-secondary" onClick={() => { setEditingChildId(""); setChildName(""); setChildNickname(""); setChildBirthDate(""); setChildGender(""); }} type="button">取消编辑</button> : null}</form> : null}</section>

      <section className="family-management-card"><div><h2>最近家庭动态</h2><p>直接来自正式学习证据，不额外复制或制造学习记录。</p></div><div className="family-activity-list">{activity.map((item) => <article key={`${item.kind}:${item.id}`}><span>{item.kind === "science" ? "🔬" : item.kind === "reading" ? "📖" : item.kind === "growth" ? "🌱" : "字"}</span><div><strong>{item.title}</strong><small>{item.child_name} · {item.actor_display_name || "家庭成员"} · {new Date(item.occurred_at).toLocaleString("zh-CN")}</small></div></article>)}{activity.length === 0 ? <p className="empty-note">还没有可展示的家庭动态。</p> : null}</div></section>
    </section>
  );
}

export default function FamilyManagementPage() {
  return <ProtectedPage><FamilyManagementContent /></ProtectedPage>;
}
