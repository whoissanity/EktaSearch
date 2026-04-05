import { useCallback, useEffect, useState } from "react";
import { MessageCirclePlus, Loader, Store, Tag } from "lucide-react";
import type { CommunityPost, CommunityTopic } from "../types";
import { RETAILERS } from "../types";
import { createCommunityPost, fetchCommunityPosts } from "../services/api";

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
  const [authorName, setAuthorName] = useState("");

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

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await createCommunityPost({
        title: title.trim(),
        body: body.trim(),
        topic: formTopic,
        author_name: authorName.trim(),
        retailer_id: formRetailer || undefined,
      });
      setTitle("");
      setBody("");
      setAuthorName("");
      setFormRetailer("");
      setFormTopic("general");
      setFormOpen(false);
      await load();
    } catch {
      setError("Could not publish. Check fields (title ≥3 chars, post ≥10).");
    } finally {
      setSubmitting(false);
    }
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
                required
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
                </span>
              </div>
              <h2 className="text-base font-medium text-zinc-100 m-0 mb-2">{p.title}</h2>
              <p className="text-sm text-zinc-400 whitespace-pre-wrap m-0 leading-relaxed">{p.body}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
