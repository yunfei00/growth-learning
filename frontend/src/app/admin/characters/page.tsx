"use client";

import { type FormEvent, useCallback, useEffect, useState } from "react";

import {
  ApiClientError,
  createAdminCharacter,
  importStarterCharacters,
  listAdminCharacters,
  type CharacterInput,
  type CharacterPage,
  type ChineseCharacter,
  updateAdminCharacter,
} from "@/lib/api/client";

type EnabledFilter = "all" | "enabled" | "disabled";

type FormState = {
  character: string;
  pinyin: string;
  commonWords: string;
  simpleMeaning: string;
  exampleSentence: string;
  radical: string;
  strokeCount: string;
  tags: string;
  isEnabled: boolean;
};

const emptyForm: FormState = {
  character: "",
  pinyin: "",
  commonWords: "",
  simpleMeaning: "",
  exampleSentence: "",
  radical: "",
  strokeCount: "",
  tags: "",
  isEnabled: true,
};

function toForm(character: ChineseCharacter): FormState {
  return {
    character: character.character,
    pinyin: character.pinyin,
    commonWords: character.common_words.join("、"),
    simpleMeaning: character.simple_meaning ?? "",
    exampleSentence: character.example_sentence ?? "",
    radical: character.radical ?? "",
    strokeCount: character.stroke_count?.toString() ?? "",
    tags: character.tags.join("、"),
    isEnabled: character.is_enabled && character.status === "active",
  };
}

function splitList(value: string): string[] {
  return Array.from(
    new Set(
      value
        .split(/[、，,]/)
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  );
}

function toPayload(form: FormState): CharacterInput {
  return {
    character: form.character.trim(),
    pinyin: form.pinyin.trim(),
    common_words: splitList(form.commonWords),
    simple_meaning: form.simpleMeaning.trim() || null,
    example_sentence: form.exampleSentence.trim() || null,
    radical: form.radical.trim() || null,
    stroke_count: form.strokeCount ? Number(form.strokeCount) : null,
    tags: splitList(form.tags),
    is_enabled: form.isEnabled,
  };
}

export default function CharacterCatalogPage() {
  const [data, setData] = useState<CharacterPage | null>(null);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [enabledFilter, setEnabledFilter] = useState<EnabledFilter>("all");
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [editing, setEditing] = useState<ChineseCharacter | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [formError, setFormError] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const result = await listAdminCharacters({
        search,
        enabled:
          enabledFilter === "all" ? undefined : enabledFilter === "enabled",
        page,
        pageSize: 20,
      });
      setData(result);
    } catch (requestError) {
      setError(
        requestError instanceof ApiClientError
          ? requestError.message
          : "无法加载汉字知识库",
      );
    } finally {
      setIsLoading(false);
    }
  }, [enabledFilter, page, search]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timeoutId);
  }, [load]);

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setFormError("");
    setIsFormOpen(true);
  };

  const openEdit = (character: ChineseCharacter) => {
    setEditing(character);
    setForm(toForm(character));
    setFormError("");
    setIsFormOpen(true);
  };

  const handleSave = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError("");
    setNotice("");
    if (Array.from(form.character.trim()).length !== 1) {
      setFormError("汉字必须是单个字符。");
      return;
    }
    if (!form.pinyin.trim()) {
      setFormError("请输入拼音。");
      return;
    }
    if (form.strokeCount && (!Number.isInteger(Number(form.strokeCount)) || Number(form.strokeCount) < 1)) {
      setFormError("笔画数必须是大于 0 的整数。");
      return;
    }

    setIsSaving(true);
    try {
      const payload = toPayload(form);
      if (editing) {
        await updateAdminCharacter(editing.id, {
          ...payload,
          status: form.isEnabled ? "active" : "archived",
        });
        setNotice(`“${payload.character}”已保存。`);
      } else {
        await createAdminCharacter(payload);
        setNotice(`“${payload.character}”已加入知识库。`);
      }
      setIsFormOpen(false);
      await load();
    } catch (requestError) {
      setFormError(
        requestError instanceof ApiClientError ? requestError.message : "保存失败，请重试",
      );
    } finally {
      setIsSaving(false);
    }
  };

  const handleToggle = async (character: ChineseCharacter) => {
    setBusyId(character.id);
    setError("");
    setNotice("");
    const enable = !character.is_enabled || character.status === "archived";
    try {
      await updateAdminCharacter(character.id, {
        is_enabled: enable,
        status: enable ? "active" : "archived",
      });
      setNotice(`“${character.character}”已${enable ? "启用" : "归档"}。`);
      await load();
    } catch (requestError) {
      setError(
        requestError instanceof ApiClientError ? requestError.message : "状态更新失败",
      );
    } finally {
      setBusyId(null);
    }
  };

  const handleStarterImport = async () => {
    setIsImporting(true);
    setError("");
    setNotice("");
    try {
      const report = await importStarterCharacters();
      if (report.errors.length > 0) {
        setError(`导入遇到 ${report.errors.length} 个错误，请检查服务器日志。`);
      } else {
        setNotice(
          `导入完成：新增 ${report.created}，更新 ${report.updated}，跳过 ${report.skipped}。`,
        );
      }
      setPage(1);
      await load();
    } catch (requestError) {
      setError(
        requestError instanceof ApiClientError ? requestError.message : "批量导入失败",
      );
    } finally {
      setIsImporting(false);
    }
  };

  return (
    <section className="admin-page character-page">
      <header className="admin-page-header">
        <div>
          <p className="eyebrow">知识库</p>
          <h2>汉字知识库</h2>
          <p>维护系统规范知识，不包含任何孩子的学习状态。</p>
        </div>
        <div className="admin-actions">
          <button
            className="button button-secondary"
            disabled={isImporting}
            onClick={() => void handleStarterImport()}
            type="button"
          >
            {isImporting ? "正在导入…" : "批量导入"}
          </button>
          <button className="button button-primary" onClick={openCreate} type="button">
            新增汉字
          </button>
        </div>
      </header>

      <form
        className="catalog-filters"
        onSubmit={(event) => {
          event.preventDefault();
          setPage(1);
          setSearch(searchInput.trim());
        }}
      >
        <label>
          <span>搜索</span>
          <input
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="汉字或拼音"
            type="search"
            value={searchInput}
          />
        </label>
        <label>
          <span>状态</span>
          <select
            onChange={(event) => {
              setEnabledFilter(event.target.value as EnabledFilter);
              setPage(1);
            }}
            value={enabledFilter}
          >
            <option value="all">全部</option>
            <option value="enabled">启用</option>
            <option value="disabled">已归档</option>
          </select>
        </label>
        <button className="button button-secondary" type="submit">
          查询
        </button>
      </form>

      {notice ? <p className="form-message form-success catalog-message">{notice}</p> : null}
      {error ? (
        <p className="form-message form-error catalog-message" role="alert">
          {error}
        </p>
      ) : null}

      <div className="catalog-table-wrap" aria-busy={isLoading}>
        <table className="catalog-table">
          <thead>
            <tr>
              <th>字</th>
              <th>拼音</th>
              <th>常用词</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={5}>正在加载…</td>
              </tr>
            ) : data?.items.length ? (
              data.items.map((item) => (
                <tr key={item.id}>
                  <td className="character-glyph">{item.character}</td>
                  <td>{item.pinyin}</td>
                  <td>{item.common_words.join("、") || "—"}</td>
                  <td>
                    <span className={`status-pill ${item.is_enabled && item.status === "active" ? "enabled" : "disabled"}`}>
                      {item.is_enabled && item.status === "active" ? "启用" : "已归档"}
                    </span>
                  </td>
                  <td>
                    <div className="table-actions">
                      <button onClick={() => openEdit(item)} type="button">
                        编辑
                      </button>
                      <button
                        disabled={busyId === item.id}
                        onClick={() => void handleToggle(item)}
                        type="button"
                      >
                        {item.is_enabled && item.status === "active" ? "归档" : "启用"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5}>没有符合条件的汉字。</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="pagination">
        <span>
          共 {data?.total ?? 0} 个 · 第 {data?.page ?? page} / {data?.pages ?? 1} 页
        </span>
        <div>
          <button
            disabled={page <= 1 || isLoading}
            onClick={() => setPage((current) => Math.max(1, current - 1))}
            type="button"
          >
            上一页
          </button>
          <button
            disabled={isLoading || page >= (data?.pages ?? 1)}
            onClick={() => setPage((current) => current + 1)}
            type="button"
          >
            下一页
          </button>
        </div>
      </div>

      {isFormOpen ? (
        <div className="modal-backdrop" role="presentation">
          <section aria-labelledby="character-form-title" aria-modal="true" className="catalog-modal" role="dialog">
            <header>
              <div>
                <p className="eyebrow">{editing ? "编辑" : "新增"}</p>
                <h3 id="character-form-title">{editing ? `编辑“${editing.character}”` : "新增汉字"}</h3>
              </div>
              <button aria-label="关闭" onClick={() => setIsFormOpen(false)} type="button">
                ×
              </button>
            </header>
            <form className="character-form" onSubmit={(event) => void handleSave(event)}>
              <div className="form-grid">
                <label>
                  <span>汉字 *</span>
                  <input required value={form.character} onChange={(event) => setForm({ ...form, character: event.target.value })} />
                </label>
                <label>
                  <span>拼音 *</span>
                  <input required placeholder="例如 rén" value={form.pinyin} onChange={(event) => setForm({ ...form, pinyin: event.target.value })} />
                </label>
                <label>
                  <span>部首</span>
                  <input value={form.radical} onChange={(event) => setForm({ ...form, radical: event.target.value })} />
                </label>
                <label>
                  <span>笔画</span>
                  <input min="1" step="1" type="number" value={form.strokeCount} onChange={(event) => setForm({ ...form, strokeCount: event.target.value })} />
                </label>
              </div>
              <label>
                <span>常用词（用顿号或逗号分隔）</span>
                <input value={form.commonWords} onChange={(event) => setForm({ ...form, commonWords: event.target.value })} />
              </label>
              <label>
                <span>简单解释</span>
                <textarea rows={3} value={form.simpleMeaning} onChange={(event) => setForm({ ...form, simpleMeaning: event.target.value })} />
              </label>
              <label>
                <span>示例句</span>
                <textarea rows={2} value={form.exampleSentence} onChange={(event) => setForm({ ...form, exampleSentence: event.target.value })} />
              </label>
              <label>
                <span>标签（用顿号或逗号分隔）</span>
                <input value={form.tags} onChange={(event) => setForm({ ...form, tags: event.target.value })} />
              </label>
              <label className="checkbox-label">
                <input checked={form.isEnabled} onChange={(event) => setForm({ ...form, isEnabled: event.target.checked })} type="checkbox" />
                <span>启用，允许普通只读 API 返回</span>
              </label>

              {formError ? (
                <p className="form-message form-error" role="alert">
                  {formError}
                </p>
              ) : null}

              <footer>
                <button className="button button-secondary" onClick={() => setIsFormOpen(false)} type="button">
                  取消
                </button>
                <button className="button button-primary" disabled={isSaving} type="submit">
                  {isSaving ? "正在保存…" : "保存"}
                </button>
              </footer>
            </form>
          </section>
        </div>
      ) : null}
    </section>
  );
}
