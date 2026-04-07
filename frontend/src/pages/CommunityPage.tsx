import { useCallback, useEffect, useState } from "react";
import { MessageCirclePlus, Loader, MessageCircle, Paperclip, Store, Tag, ThumbsDown, ThumbsUp } from "lucide-react";
import type { AuthUser, CommunityAttachment, CommunityPost, CommunityTopic } from "../types";
import { RETAILERS } from "../types";
import {
  createCommunityPost,
  createCommunityReply,
  fetchCommunityPosts,
  getAuthToken,
  login,
  logout,
  me,
  register,
  setAuthToken,
  uploadCommunityAttachments,
  voteCommunityPost,
} from "../services/api";

const TOPICS: { id: CommunityTopic | "all"; label: string; hint: string }[] = [
  { id: "all", label: "All", hint: "Everything" },
  { id: "review", label: "Review", hint: "Your take on a shop or product" },
  { id: "issue", label: "Issue", hint: "Problems, scams, bad service" },
  { id: "suggestion", label: "Suggestion", hint: "Ideas for retailers or this site" },
  { id: "general", label: "General", hint: "GPU advice, builds, chat" },
];

function topicBadgeClass(topic: CommunityTopic): string {
  switch (topic) {
    case "review":
      return "bg-emerald-500/20 text-emerald-300 border-emerald-500/30";
    case "issue":
      return "bg-rose-500/20 text-rose-300 border-rose-500/30";
    case "suggestion":
      return "bg-amber-500/20 text-amber-200 border-amber-500/30";
    default:
      return "bg-zinc-500/20 text-zinc-300 border-zinc-500/35";
  }
}

function formatTime(iso: string | null): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

export default function CommunityPage() {
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authEmail, setAuthEmail] = useState("");
  const [authUsername, setAuthUsername] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authLoading, setAuthLoading] = useState(false);
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);

  const [topicFilter, setTopicFilter] = useState<CommunityTopic | "all">("all");
  const [retailerFilter, setRetailerFilter] = useState<string | "all">("all");
  const [posts, setPosts] = useState<CommunityPost[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);

  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [formTopic, setFormTopic] = useState<CommunityTopic>("general");
  const [formRetailer, setFormRetailer] = useState<string>("");
  const [authorName, setAuthorName] = useState(localStorage.getItem("community_name") ?? "");
  const [replyDrafts, setReplyDrafts] = useState<Record<string, string>>({});
  const [replying, setReplying] = useState<Record<string, boolean>>({});
  const [postAttachments, setPostAttachments] = useState<CommunityAttachment[]>([]);
  const [replyAttachments, setReplyAttachments] = useState<Record<string, CommunityAttachment[]>>({});

  useEffect(() => {
    if (!getAuthToken()) return;
    void me().then(setCurrentUser).catch(() => setAuthToken(null));
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchCommunityPosts({
        topic: topicFilter === "all" ? undefined : topicFilter,
        retailer_id: retailerFilter === "all" ? undefined : retailerFilter,
        limit: 50,
      });
      setPosts(res.posts);
      setTotal(res.total);
    } catch {
      setError("Could not load posts. Is the API running?");
      setPosts([]);
    } finally {
      setLoading(false);
    }
  }, [topicFilter, retailerFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthLoading(true);
    setError(null);
    try {
      const out =
        authMode === "register"
          ? await register({
              email: authEmail.trim(),
              username: authUsername.trim(),
              password: authPassword,
            })
          : await login({ email: authEmail.trim(), password: authPassword });
      setAuthToken(out.token);
      setCurrentUser(out.user);
      setAuthorName(out.user.username);
    } catch {
      setError("Auth failed. Check credentials.");
    } finally {
      setAuthLoading(false);
    }
  };

  const onLogout = async () => {
    await logout();
    setAuthToken(null);
    setCurrentUser(null);
  };

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await createCommunityPost({
        title: title.trim(),
        body: body.trim(),
        topic: formTopic,
        author_name: currentUser ? undefined : authorName.trim(),
        retailer_id: formRetailer || undefined,
        attachment_ids: postAttachments.map((a) => a.id),
      });
      localStorage.setItem("community_name", authorName.trim());
      setTitle("");
      setBody("");
      setFormRetailer("");
      setFormTopic("general");
      setPostAttachments([]);
      setFormOpen(false);
      await load();
    } catch {
      setError("Could not publish. Check fields (title ≥3 chars, post ≥10).");
    } finally {
      setSubmitting(false);
    }
  };

  const applyVote = async (post: CommunityPost, value: -1 | 1) => {
    try {
      const next = post.user_vote === value ? 0 : value;
      const res = await voteCommunityPost(post.id, next as -1 | 0 | 1);
      setPosts((curr) =>
        curr.map((p) =>
          p.id === post.id
            ? { ...p, likes: res.likes, dislikes: res.dislikes, score: res.score, user_vote: res.user_vote }
            : p
        )
      );
    } catch {
      setError("Could not vote on this post.");
    }
  };

  const submitReply = async (postId: string) => {
    const text = (replyDrafts[postId] ?? "").trim();
    if (!text) return;
    setReplying((s) => ({ ...s, [postId]: true }));
    try {
      const r = await createCommunityReply(postId, {
        body: text,
        author_name: currentUser ? undefined : (authorName.trim() || "Anonymous"),
        attachment_ids: (replyAttachments[postId] ?? []).map((a) => a.id),
      });
      setPosts((curr) =>
        curr.map((p) =>
          p.id === postId
            ? {
                ...p,
                replies: [...p.replies, r],
                replies_count: p.replies_count + 1,
              }
            : p
        )
      );
      setReplyDrafts((s) => ({ ...s, [postId]: "" }));
      setReplyAttachments((s) => ({ ...s, [postId]: [] }));
    } catch {
      setError("Could not add reply.");
    } finally {
      setReplying((s) => ({ ...s, [postId]: false }));
    }
  };

  const onUploadPostFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const uploaded = await uploadCommunityAttachments(Array.from(files));
    setPostAttachments((s) => [...s, ...uploaded]);
  };

  const onUploadReplyFiles = async (postId: string, files: FileList | null) => {
    if (!files || files.length === 0) return;
    const uploaded = await uploadCommunityAttachments(Array.from(files));
    setReplyAttachments((s) => ({ ...s, [postId]: [...(s[postId] ?? []), ...uploaded] }));
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <header className="mb-8">
        <h1 className="text-xl font-semibold text-zinc-50 m-0 flex items-center gap-2">
          <MessageCirclePlus className="text-cyan-400 shrink-0" size={26} />
          Community
        </h1>
        <p className="text-sm text-zinc-500 mt-2 leading-relaxed max-w-2xl">
          Share experiences with Bangladeshi PC retailers, warn others about bad service, suggest improvements, or ask
          whether a GPU is right for you — tagged like subreddits, optional shop flair.
        </p>
        <div className="mt-4 glass p-3 rounded-lg">
          {currentUser ? (
            <div className="flex items-center justify-between gap-3 text-sm">
              <div>
                Logged in as <span className="text-zinc-100 font-medium">{currentUser.username}</span>{" "}
                <span className="text-zinc-500">({currentUser.email})</span>
                {currentUser.is_owner && (
                  <span className="ml-2 px-2 py-0.5 rounded bg-amber-500/25 text-amber-200 text-xs">Owner</span>
                )}
              </div>
              <button type="button" className="btn-secondary text-xs" onClick={() => void onLogout()}>
                Logout
              </button>
            </div>
          ) : (
            <form onSubmit={handleAuthSubmit} className="space-y-2">
              <div className="flex gap-2">
                <button type="button" className="btn-secondary text-xs" onClick={() => setAuthMode("login")}>
                  Login
                </button>
                <button
                  type="button"
                  className="btn-secondary text-xs"
                  onClick={() => setAuthMode("register")}
                >
                  Create account
                </button>
              </div>
              <div className="grid sm:grid-cols-3 gap-2">
                <input
                  className="input text-sm"
                  placeholder="Email"
                  value={authEmail}
                  onChange={(e) => setAuthEmail(e.target.value)}
                  required
                />
                {authMode === "register" && (
                  <input
                    className="input text-sm"
                    placeholder="Username"
                    value={authUsername}
                    onChange={(e) => setAuthUsername(e.target.value)}
                    required
                  />
                )}
                <input
                  className="input text-sm"
                  type="password"
                  placeholder="Password"
                  value={authPassword}
                  onChange={(e) => setAuthPassword(e.target.value)}
                  required
                />
              </div>
              <button type="submit" className="btn-primary text-xs" disabled={authLoading}>
                {authLoading ? "Please wait..." : authMode === "register" ? "Create account" : "Login"}
              </button>
            </form>
          )}
        </div>
      </header>

      <div className="flex flex-wrap gap-2 mb-4">
        {TOPICS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTopicFilter(t.id)}
            title={t.hint}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
              topicFilter === t.id
                ? "bg-cyan-500/25 text-cyan-200 border-cyan-500/40"
                : "bg-white/[0.06] text-zinc-400 border-white/[0.1] hover:border-white/[0.18]"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2 mb-6">
        <span className="text-xs text-zinc-500 flex items-center gap-1">
          <Store size={14} /> Retailer
        </span>
        <button
          type="button"
          onClick={() => setRetailerFilter("all")}
          className={`px-2.5 py-1 rounded-md text-xs border ${
            retailerFilter === "all"
              ? "bg-violet-500/20 text-violet-200 border-violet-500/35"
              : "bg-white/[0.05] text-zinc-500 border-white/[0.08]"
          }`}
        >
          Any
        </button>
        {Object.entries(RETAILERS).map(([id, { name }]) => (
          <button
            key={id}
            type="button"
            onClick={() => setRetailerFilter(id)}
            className={`px-2.5 py-1 rounded-md text-xs border truncate max-w-[9rem] ${
              retailerFilter === id
                ? "bg-violet-500/20 text-violet-200 border-violet-500/35"
                : "bg-white/[0.05] text-zinc-500 border-white/[0.08] hover:text-zinc-300"
            }`}
            title={name}
          >
            {name}
          </button>
        ))}
      </div>

      <button
        type="button"
        onClick={() => setFormOpen((v) => !v)}
        className="btn-secondary text-sm mb-6 w-full sm:w-auto"
      >
        {formOpen ? "Close composer" : "New post"}
      </button>

      {formOpen && (
        <form onSubmit={onSubmit} className="glass p-4 rounded-xl mb-8 space-y-3">
          <div className="grid sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-zinc-500 mb-1">Display name</label>
              <input
                className="input text-sm w-full"
                value={authorName}
                onChange={(e) => setAuthorName(e.target.value)}
                placeholder="Anonymous warrior"
                required={!currentUser}
                disabled={!!currentUser}
                maxLength={64}
              />
            </div>
            <div>
              <label className="block text-xs text-zinc-500 mb-1">Topic</label>
              <select
                className="input text-sm w-full"
                value={formTopic}
                onChange={(e) => setFormTopic(e.target.value as CommunityTopic)}
              >
                <option value="general">General</option>
                <option value="review">Review</option>
                <option value="issue">Issue</option>
                <option value="suggestion">Suggestion</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs text-zinc-500 mb-1">Retailer (optional)</label>
            <select
              className="input text-sm w-full"
              value={formRetailer}
              onChange={(e) => setFormRetailer(e.target.value)}
            >
              <option value="">— Not specific to one shop —</option>
              {Object.entries(RETAILERS).map(([id, { name }]) => (
                <option key={id} value={id}>
                  {name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-zinc-500 mb-1">Title</label>
            <input
              className="input text-sm w-full"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Short headline"
              required
              minLength={3}
              maxLength={200}
            />
          </div>
          <div>
            <label className="block text-xs text-zinc-500 mb-1">Post</label>
            <textarea
              className="input text-sm w-full min-h-[140px] resize-y"
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="Rant, question, or story…"
              required
              minLength={10}
              maxLength={10000}
            />
          </div>
          <div>
            <label className="block text-xs text-zinc-500 mb-1">Attachments</label>
            <input type="file" multiple onChange={(e) => void onUploadPostFiles(e.target.files)} className="text-xs" />
            {postAttachments.map((a) => (
              <div key={a.id} className="text-xs text-zinc-400 inline-flex items-center gap-1 mr-2">
                <Paperclip size={12} /> {a.file_name}
              </div>
            ))}
          </div>
          <button type="submit" className="btn-primary text-sm" disabled={submitting}>
            {submitting ? "Publishing…" : "Publish"}
          </button>
        </form>
      )}

      {error && (
        <p className="text-sm text-rose-400 mb-4" role="alert">
          {error}
        </p>
      )}

      <p className="text-xs text-zinc-500 mb-4">
        {loading ? "Loading…" : `${total} post${total === 1 ? "" : "s"}`}
      </p>

      {loading && posts.length === 0 ? (
        <div className="flex justify-center py-16 text-zinc-500">
          <Loader className="animate-spin" size={28} />
        </div>
      ) : posts.length === 0 ? (
        <div className="glass rounded-xl p-8 text-center text-zinc-500 text-sm">
          No posts yet with these filters. Be the first to share something.
        </div>
      ) : (
        <ul className="space-y-4 list-none p-0 m-0">
          {posts.map((p) => (
            <li key={p.id} className="glass rounded-xl p-4">
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <span
                  className={`inline-flex items-center gap-0.5 px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wide border ${topicBadgeClass(p.topic)}`}
                >
                  <Tag size={10} />
                  {p.topic}
                </span>
                {p.retailer_id && RETAILERS[p.retailer_id] && (
                  <span
                    className="text-[11px] px-2 py-0.5 rounded-md bg-white/[0.08] text-zinc-300 border border-white/[0.1]"
                    style={{
                      borderLeftWidth: 3,
                      borderLeftColor: RETAILERS[p.retailer_id].color,
                    }}
                  >
                    {RETAILERS[p.retailer_id].name}
                  </span>
                )}
                <span className="text-xs text-zinc-500 ml-auto">
                  {p.author_name} · {formatTime(p.created_at)}
                  {p.is_owner && (
                    <span className="ml-2 px-2 py-0.5 rounded bg-amber-500/25 text-amber-200 text-[10px]">
                      Owner
                    </span>
                  )}
                </span>
              </div>
              <h2 className="text-base font-medium text-zinc-100 m-0 mb-2">{p.title}</h2>
              <p className="text-sm text-zinc-400 whitespace-pre-wrap m-0 leading-relaxed">{p.body}</p>
              {(p.attachments ?? []).map((a) => (
                <a
                  key={a.id}
                  href={a.file_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-cyan-300 block"
                >
                  <Paperclip size={12} className="inline mr-1" />
                  {a.file_name}
                </a>
              ))}
              <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                <button
                  type="button"
                  onClick={() => void applyVote(p, 1)}
                  className={`px-2 py-1 rounded-md border inline-flex items-center gap-1 ${
                    p.user_vote === 1
                      ? "border-emerald-400/60 text-emerald-300"
                      : "border-white/15 text-zinc-300"
                  }`}
                >
                  <ThumbsUp size={13} /> {p.likes}
                </button>
                <button
                  type="button"
                  onClick={() => void applyVote(p, -1)}
                  className={`px-2 py-1 rounded-md border inline-flex items-center gap-1 ${
                    p.user_vote === -1
                      ? "border-rose-400/60 text-rose-300"
                      : "border-white/15 text-zinc-300"
                  }`}
                >
                  <ThumbsDown size={13} /> {p.dislikes}
                </button>
                <span className="text-zinc-400">
                  Reputation:{" "}
                  <span className={p.score >= 0 ? "text-emerald-300" : "text-rose-300"}>
                    {p.score}
                  </span>
                </span>
                <span className="text-zinc-500 inline-flex items-center gap-1">
                  <MessageCircle size={13} /> {p.replies_count}
                </span>
              </div>
              <div className="mt-3 space-y-2">
                {p.replies.map((r) => (
                  <div key={r.id} className="rounded-lg bg-white/[0.04] border border-white/[0.08] p-2">
                    <div className="text-[11px] text-zinc-500">
                      {r.author_name} · {formatTime(r.created_at)}
                      {r.is_owner && (
                        <span className="ml-2 px-2 py-0.5 rounded bg-amber-500/25 text-amber-200 text-[10px]">
                          Owner
                        </span>
                      )}
                    </div>
                    <div className="text-sm text-zinc-300 whitespace-pre-wrap">{r.body}</div>
                    {(r.attachments ?? []).map((a) => (
                      <a
                        key={a.id}
                        href={a.file_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs text-cyan-300 block"
                      >
                        <Paperclip size={12} className="inline mr-1" />
                        {a.file_name}
                      </a>
                    ))}
                  </div>
                ))}
              </div>
              <div className="mt-3 flex gap-2">
                <input
                  className="input text-sm w-full"
                  value={replyDrafts[p.id] ?? ""}
                  onChange={(e) =>
                    setReplyDrafts((s) => ({
                      ...s,
                      [p.id]: e.target.value,
                    }))
                  }
                  placeholder="Reply to this thread..."
                  maxLength={3000}
                />
                <button
                  type="button"
                  className="btn-secondary text-xs"
                  disabled={!!replying[p.id]}
                  onClick={() => void submitReply(p.id)}
                >
                  {replying[p.id] ? "Replying..." : "Reply"}
                </button>
              </div>
              <div className="mt-1">
                <input
                  type="file"
                  multiple
                  onChange={(e) => void onUploadReplyFiles(p.id, e.target.files)}
                  className="text-xs"
                />
              </div>
              {(replyAttachments[p.id] ?? []).map((a) => (
                <div key={a.id} className="text-xs text-zinc-400 inline-flex items-center gap-1 mr-2">
                  <Paperclip size={12} /> {a.file_name}
                </div>
              ))}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
