"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ChapterStat {
  class_level: number;
  subject: string;
  topic: string;
  n: number;
  refused: number;
  seed_n: number;
  real_n: number;
  feedback_count: number;
  helpful_count: number;
  refusal_rate: number;
  helpful_rate: number;
}

interface TopQuestion {
  question: string;
  class_level: number | null;
  subject: string | null;
  topic: string | null;
  n: number;
  refused: number;
  seed_n: number;
}

interface TeacherSummary {
  total_queries: number;
  seed_queries: number;
  real_queries: number;
  refused_queries: number;
  refusal_rate: number;
  feedback_count: number;
  helpful_count: number;
  helpful_rate: number;
  has_seed_data: boolean;
  chapters: ChapterStat[];
  top_questions: TopQuestion[];
}

function heatBadgeClass(refusalRate: number): string {
  if (refusalRate >= 0.35) return "border-rose-400/40 bg-rose-500/15 text-rose-300";
  if (refusalRate >= 0.15) return "border-amber-400/40 bg-amber-500/15 text-amber-300";
  return "border-[#00e5ff]/40 bg-[#00e5ff]/10 text-[#00e5ff]";
}

async function fetchTeacherSummary(): Promise<TeacherSummary> {
  const res = await fetch(`${API_BASE}/teacher/summary`);
  if (!res.ok) {
    throw new Error(`সার্ভার ত্রুটি: ${res.statusText} (${res.status})`);
  }
  return res.json();
}

export default function TeacherPage() {
  const [data, setData] = useState<TeacherSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const loadSummary = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      setData(await fetchTeacherSummary());
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "শিক্ষক ড্যাশবোর্ড ডেটা লোড করতে সমস্যা হয়েছে।");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    fetchTeacherSummary()
      .then((json) => {
        if (!cancelled) setData(json);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setErrorMsg(err instanceof Error ? err.message : "শিক্ষক ড্যাশবোর্ড ডেটা লোড করতে সমস্যা হয়েছে।");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const maxChapterCount = data?.chapters.reduce((m, c) => Math.max(m, c.n), 1) || 1;

  return (
    <main className="ambient-glow min-h-screen bg-[#08080d] px-4 py-6 text-[#eef2f3] md:px-8 md:py-10">
      <div className="mx-auto max-w-5xl space-y-6">
        <header className="flex flex-col justify-between gap-4 border-b border-white/10 pb-5 sm:flex-row sm:items-center">
          <div>
            <div className="font-mono-code text-[11px] uppercase tracking-widest text-[#00e5ff]">
              PATHSHALAAI · ANALYTICS
            </div>
            <h1 className="mt-1 font-display text-2xl font-bold tracking-tight text-white md:text-3xl">
              শিক্ষক বিশ্লেষণ ড্যাশবোর্ড
            </h1>
            <p className="mt-1 text-xs text-[#8b94a3]">
              শিক্ষার্থীদের প্রশ্ন, দুর্বল অধ্যায় ও প্রত্যাখ্যানের হার (কোনো ব্যক্তিগত তথ্য সংরক্ষিত নয়)
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={loadSummary}
              disabled={loading}
              className="rounded-xl border border-white/15 bg-white/[0.04] px-3.5 py-2 text-xs text-slate-200 transition hover:border-[#00e5ff]/40 hover:text-white disabled:opacity-50"
            >
              🔄 রিফ্রেশ
            </button>
            <Link
              href="/"
              className="rounded-xl bg-[#00e5ff] px-4 py-2 font-display text-xs font-bold text-[#001318] transition hover:bg-[#33ecff]"
            >
              ← প্রশ্ন করুন
            </Link>
          </div>
        </header>

        {data?.has_seed_data && (
          <div className="rounded-xl border border-amber-400/30 bg-amber-500/10 p-4 text-xs leading-relaxed text-amber-100">
            <span className="font-semibold text-amber-300">নোট (Demo vs Real Data):</span> এই ড্যাশবোর্ডে{" "}
            <span className="font-semibold">{data.seed_queries}টি ডেমো প্রশ্ন</span> (
            <code className="font-mono-code text-amber-200">session_id=&apos;seed&apos;</code>) এবং{" "}
            <span className="font-semibold">{data.real_queries}টি প্রকৃত প্রশ্ন</span> দেখানো হচ্ছে। ডেমো ডেটা শুধুমাত্র প্রদর্শনের জন্য।
          </div>
        )}

        {errorMsg && (
          <div role="alert" className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-4 text-sm text-rose-200">
            {errorMsg}
          </div>
        )}

        {loading && (
          <div className="grid grid-cols-2 gap-4 animate-pulse md:grid-cols-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-24 rounded-2xl border border-white/10 bg-[#0d1117]" />
            ))}
          </div>
        )}

        {data && !loading && (
          <>
            <section className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <div className="rounded-2xl border border-white/10 bg-[#0d1117] p-5">
                <div className="font-mono-code text-[10px] uppercase tracking-wider text-slate-400">মোট প্রশ্ন</div>
                <div className="mt-1.5 font-display text-3xl font-bold text-white">{data.total_queries}</div>
                <div className="mt-1 font-mono-code text-[11px] text-slate-400">
                  ডেমো: {data.seed_queries} · প্রকৃত: {data.real_queries}
                </div>
              </div>

              <div className="rounded-2xl border border-white/10 bg-[#0d1117] p-5">
                <div className="font-mono-code text-[10px] uppercase tracking-wider text-slate-400">প্রত্যাখ্যানের হার</div>
                <div className="mt-1.5 font-display text-3xl font-bold text-rose-400">
                  {(data.refusal_rate * 100).toFixed(1)}%
                </div>
                <div className="mt-1 font-mono-code text-[11px] text-slate-400">
                  প্রত্যাখ্যাত: {data.refused_queries}টি
                </div>
              </div>

              <div className="rounded-2xl border border-white/10 bg-[#0d1117] p-5">
                <div className="font-mono-code text-[10px] uppercase tracking-wider text-slate-400">সহায়ক উত্তরের হার</div>
                <div className="mt-1.5 font-display text-3xl font-bold text-[#00e5ff]">
                  {(data.helpful_rate * 100).toFixed(1)}%
                </div>
                <div className="mt-1 font-mono-code text-[11px] text-slate-400">
                  সন্তুষ্ট: {data.helpful_count}/{data.feedback_count}
                </div>
              </div>

              <div className="rounded-2xl border border-white/10 bg-[#0d1117] p-5">
                <div className="font-mono-code text-[10px] uppercase tracking-wider text-slate-400">সক্রিয় অধ্যায়</div>
                <div className="mt-1.5 font-display text-3xl font-bold text-white">{data.chapters.length}</div>
                <div className="mt-1 font-mono-code text-[11px] text-slate-400">শীর্ষ অধ্যায় তালিকা</div>
              </div>
            </section>

            <section className="space-y-4 rounded-2xl border border-white/10 bg-[#0d1117] p-6">
              <div className="flex flex-col justify-between gap-1 sm:flex-row sm:items-center">
                <h2 className="font-display text-lg font-semibold text-white">অধ্যায়ভিত্তিক প্রশ্ন ও দুর্বলতা হিটম্যাপ</h2>
                <span className="font-mono-code text-[11px] text-slate-400">
                  লাল ≥35% প্রত্যাখ্যান · সায়ান ভালো ফলাফল
                </span>
              </div>

              {data.chapters.length === 0 ? (
                <p className="text-sm text-slate-400">এখনো কোনো অধ্যায়ভিত্তিক প্রশ্ন জমা হয়নি।</p>
              ) : (
                <div className="space-y-3.5">
                  {data.chapters.map((ch, idx) => {
                    const pct = Math.max(4, Math.round((ch.n / maxChapterCount) * 100));
                    return (
                      <div key={`${ch.class_level}-${ch.subject}-${ch.topic}-${idx}`} className="space-y-1.5">
                        <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                          <div className="font-medium text-slate-100">
                            শ্রেণি {ch.class_level} · {ch.subject} · {ch.topic}
                          </div>
                          <div className="flex items-center gap-2 font-mono-code text-[11px]">
                            <span className="text-slate-400">
                              {ch.n}টি (ডেমো {ch.seed_n} / প্রকৃত {ch.real_n})
                            </span>
                            <span className={`rounded-full border px-2 py-0.5 ${heatBadgeClass(ch.refusal_rate)}`}>
                              প্রত্যাখ্যান {(ch.refusal_rate * 100).toFixed(0)}%
                            </span>
                            {ch.feedback_count > 0 && (
                              <span className="text-[#00e5ff]">
                                সহায়ক {(ch.helpful_rate * 100).toFixed(0)}%
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="h-2 w-full overflow-hidden rounded-full bg-white/5">
                          <div
                            className={`h-full rounded-full ${
                              ch.refusal_rate >= 0.35
                                ? "bg-rose-500"
                                : ch.refusal_rate >= 0.15
                                  ? "bg-amber-400"
                                  : "bg-[#00e5ff]"
                            }`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>

            <section className="space-y-4 rounded-2xl border border-white/10 bg-[#0d1117] p-6">
              <h2 className="font-display text-lg font-semibold text-white">সবচেয়ে বেশি জিজ্ঞাসিত ১০টি প্রশ্ন</h2>
              {data.top_questions.length === 0 ? (
                <p className="text-sm text-slate-400">কোনো প্রশ্ন পাওয়া যায়নি।</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse text-left text-sm">
                    <thead>
                      <tr className="border-b border-white/10 font-mono-code text-[11px] uppercase text-slate-400">
                        <th className="py-2 pr-3">#</th>
                        <th className="py-2 pr-3">প্রশ্ন</th>
                        <th className="py-2 pr-3">শ্রেণি / অধ্যায়</th>
                        <th className="py-2 pr-3 text-right">বার</th>
                        <th className="py-2 text-right">প্রত্যাখ্যাত</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.top_questions.map((q, i) => (
                        <tr key={i} className="border-b border-white/5 last:border-0">
                          <td className="py-2.5 pr-3 font-mono-code text-xs text-slate-500">{i + 1}</td>
                          <td className="py-2.5 pr-3 text-slate-200">
                            {q.question}
                            {q.seed_n > 0 && (
                              <span className="ml-2 rounded bg-amber-500/20 px-1.5 py-0.5 font-mono-code text-[10px] text-amber-300">
                                ডেমো
                              </span>
                            )}
                          </td>
                          <td className="py-2.5 pr-3 text-xs text-slate-400">
                            {q.class_level ? `শ্রেণি ${q.class_level}` : ""}
                            {q.subject ? ` · ${q.subject}` : ""}
                            {q.topic ? ` · ${q.topic}` : ""}
                          </td>
                          <td className="py-2.5 pr-3 text-right font-mono-code font-semibold text-white">{q.n}</td>
                          <td className="py-2.5 text-right font-mono-code text-rose-400">{q.refused}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </main>
  );
}
