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

interface ConceptGap {
  curriculum_id: string;
  textbook_medium: string;
  class_level: number;
  subject: string;
  chapter: string;
  attempts: number;
  incorrect_count: number;
  incorrect_rate: number;
  seed_attempts: number;
  real_attempts: number;
  unique_sessions: number;
  avg_mastery: number;
  low_sample_warning: boolean;
  is_demo_data: boolean;
}

interface RecurringMisconception {
  likely_misconception: string;
  textbook_medium: string;
  class_level: number;
  subject: string;
  chapter: string;
  count: number;
  seed_count: number;
  real_count: number;
  is_demo_data: boolean;
}

interface TeacherSummary {
  total_queries: number;
  seed_queries: number;
  real_queries: number;
  refused_queries: number;
  refusal_rate: number;
  feedback_count: number;
  helpful_count: number;
  helpful_rate: number | null;
  has_seed_data: boolean;
  privacy_threshold_min_sessions?: number;
  suppressed_small_groups?: number;
  chapters: ChapterStat[];
  top_questions: TopQuestion[];
  concept_gaps?: ConceptGap[];
  recurring_misconceptions?: RecurringMisconception[];
}

function heatBadgeClass(rate: number): string {
  if (rate >= 0.35) return "border-rose-400/40 bg-rose-500/15 text-rose-300";
  if (rate >= 0.15) return "border-amber-400/40 bg-amber-500/15 text-amber-300";
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
  const conceptGaps = data?.concept_gaps ?? [];
  const misconceptions = data?.recurring_misconceptions ?? [];

  return (
    <main className="ambient-glow min-h-screen bg-[#08080d] px-4 py-6 text-[#eef2f3] md:px-8 md:py-10">
      <div className="mx-auto max-w-5xl space-y-6">
        <header className="flex flex-col justify-between gap-4 border-b border-white/10 pb-5 sm:flex-row sm:items-center">
          <div>
            <div className="font-mono-code text-[11px] uppercase tracking-widest text-[#00e5ff]">
              PATHSHALAAI · LEARNING GAP ANALYTICS
            </div>
            <h1 className="mt-1 font-display text-2xl font-bold tracking-tight text-white md:text-3xl">
              শিক্ষক বিশ্লেষণ ড্যাশবোর্ড
            </h1>
            <p className="mt-1 text-xs text-[#8b94a3]">
              অধ্যায়ভিত্তিক শেখার ঘাটতি, সম্ভাব্য ভুল ধারণা ও প্রশ্নের প্রবণতা (ব্যক্তিগত পরিচয় বা চ্যাট সংরক্ষিত হয় না)
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <a
              href={`${API_BASE}/teacher/export/weak-chapters.csv`}
              download="weak_chapters.csv"
              className="rounded-xl border border-[#00e5ff]/40 bg-[#00e5ff]/10 px-3.5 py-2 text-xs font-medium text-[#00e5ff] transition hover:bg-[#00e5ff]/20"
            >
              ⬇ CSV ডাউনলোড
            </a>
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
            <span className="font-semibold">{data.seed_queries}টি ডেমো প্রশ্ন</span> ও পূর্ব-সংরক্ষিত ডেমো অনুশীলন তথ্য (
            <code className="font-mono-code text-amber-200">session_id=&apos;seed&apos;</code>) দেখানো হচ্ছে, প্রকৃত প্রশ্ন{" "}
            <span className="font-semibold">{data.real_queries}টি</span>। গোপনীয়তার জন্য{" "}
            {data.privacy_threshold_min_sessions ?? 3}টির কম প্রকৃত শিক্ষার্থীর গোষ্ঠী প্রদর্শন করা হয় না
            {data.suppressed_small_groups ? ` (${data.suppressed_small_groups}টি গোপন)` : ""}।
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
                  প্রত্যাখ্যাত: {data.refused_queries}টি (n={data.total_queries})
                </div>
              </div>

              <div className="rounded-2xl border border-white/10 bg-[#0d1117] p-5">
                <div className="font-mono-code text-[10px] uppercase tracking-wider text-slate-400">সহায়ক উত্তরের হার</div>
                <div className="mt-1.5 font-display text-3xl font-bold text-[#00e5ff]">
                  {data.helpful_rate !== null ? `${(data.helpful_rate * 100).toFixed(1)}%` : "—"}
                </div>
                <div className="mt-1 font-mono-code text-[11px] text-slate-400">
                  সন্তুষ্ট: {data.helpful_count}/{data.feedback_count}
                </div>
              </div>

              <div className="rounded-2xl border border-white/10 bg-[#0d1117] p-5">
                <div className="font-mono-code text-[10px] uppercase tracking-wider text-slate-400">Concept Rescue অধ্যায়</div>
                <div className="mt-1.5 font-display text-3xl font-bold text-white">{conceptGaps.length}</div>
                <div className="mt-1 font-mono-code text-[11px] text-slate-400">
                  ভুল ধারণা শনাক্ত: {misconceptions.length}টি
                </div>
              </div>
            </section>

            {/* Concept Rescue Learning Gaps */}
            <section className="space-y-4 rounded-2xl border border-white/10 bg-[#0d1117] p-6">
              <div className="flex flex-col justify-between gap-1 sm:flex-row sm:items-center">
                <h2 className="font-display text-lg font-semibold text-white">
                  Concept Rescue · অধ্যায়ভিত্তিক শেখার ঘাটতি (Incorrect Rates &amp; Mastery Estimates)
                </h2>
                <span className="font-mono-code text-[11px] text-slate-400">
                  পরবর্তী ক্লাসে পুনরালোচনার অগ্রাধিকার
                </span>
              </div>

              {conceptGaps.length === 0 ? (
                <p className="text-sm text-slate-400">
                  এখনো কোনো পর্যাপ্ত Concept Rescue অনুশীলন তথ্য জমা হয়নি (ব্যক্তিগত গোপনীয়তার জন্য কমপক্ষে ৩টি সেশন প্রয়োজন)।
                </p>
              ) : (
                <div className="space-y-3">
                  {conceptGaps.map((g, idx) => (
                    <div
                      key={`${g.textbook_medium}-${g.class_level}-${g.subject}-${g.chapter}-${idx}`}
                      className="rounded-xl border border-white/10 bg-[#08080d]/70 p-4 space-y-2"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                        <div className="flex flex-wrap items-center gap-2 font-medium text-white">
                          <span className="rounded border border-white/15 bg-white/5 px-1.5 py-0.5 font-mono-code text-[10px] text-[#00e5ff]">
                            {g.textbook_medium === "english_version" ? "EN Version" : "বাংলা ভার্সন"}
                          </span>
                          <span>
                            Class {g.class_level} · {g.subject} · {g.chapter}
                          </span>
                          {g.is_demo_data && (
                            <span className="rounded bg-amber-500/20 px-1.5 py-0.5 font-mono-code text-[10px] text-amber-300">
                              ডেমো ডেটা
                            </span>
                          )}
                          {g.low_sample_warning && (
                            <span className="rounded bg-slate-700/60 px-1.5 py-0.5 font-mono-code text-[10px] text-slate-300">
                              কম নমুনা (n&lt;3)
                            </span>
                          )}
                        </div>
                        <div className="flex flex-wrap items-center gap-2 font-mono-code text-[11px]">
                          <span className={`rounded-full border px-2.5 py-0.5 ${heatBadgeClass(g.incorrect_rate)}`}>
                            ভুল উত্তর {(g.incorrect_rate * 100).toFixed(0)}% ({g.incorrect_count}/{g.attempts} attempts)
                          </span>
                          <span className="text-slate-300">
                            আনুমানিক দক্ষতা ~{Math.round(g.avg_mastery * 100)}%
                          </span>
                        </div>
                      </div>
                      <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/5">
                        <div
                          className={`h-full rounded-full ${
                            g.incorrect_rate >= 0.35
                              ? "bg-rose-500"
                              : g.incorrect_rate >= 0.15
                                ? "bg-amber-400"
                                : "bg-[#00e5ff]"
                          }`}
                          style={{ width: `${Math.max(5, Math.round(g.incorrect_rate * 100))}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            {/* Recurring Misconceptions */}
            <section className="space-y-4 rounded-2xl border border-white/10 bg-[#0d1117] p-6">
              <div className="flex flex-col justify-between gap-1 sm:flex-row sm:items-center">
                <h2 className="font-display text-lg font-semibold text-white">
                  পুনরাবৃত্ত সম্ভাব্য ভুল ধারণা (Recurring Likely Misconceptions)
                </h2>
                <span className="font-mono-code text-[11px] text-slate-400">
                  পর্যবেক্ষিত ভুল উত্তরের ভিত্তিতে
                </span>
              </div>

              {misconceptions.length === 0 ? (
                <p className="text-sm text-slate-400">এখনো কোনো পুনরাবৃত্ত ভুল ধারণা রেকর্ড হয়নি।</p>
              ) : (
                <ul className="space-y-2.5">
                  {misconceptions.map((m, idx) => (
                    <li
                      key={idx}
                      className="flex flex-col justify-between gap-2 rounded-xl border border-white/10 bg-[#08080d]/70 p-3.5 text-xs sm:flex-row sm:items-center"
                    >
                      <div className="space-y-1">
                        <div className="flex flex-wrap items-center gap-2 font-mono-code text-[10px] text-[#00e5ff]">
                          <span>{m.textbook_medium === "english_version" ? "EN Version" : "বাংলা ভার্সন"}</span>
                          <span>· Class {m.class_level} · {m.subject} · {m.chapter}</span>
                          {m.is_demo_data && (
                            <span className="rounded bg-amber-500/20 px-1.5 py-0.5 text-amber-300">ডেমো ডেটা</span>
                          )}
                        </div>
                        <p className="text-sm text-slate-100">{m.likely_misconception}</p>
                      </div>
                      <span className="shrink-0 rounded-full border border-amber-400/30 bg-amber-500/10 px-3 py-1 font-mono-code text-[11px] text-amber-200">
                        n={m.count} বার
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="space-y-4 rounded-2xl border border-white/10 bg-[#0d1117] p-6">
              <div className="flex flex-col justify-between gap-1 sm:flex-row sm:items-center">
                <h2 className="font-display text-lg font-semibold text-white">অধ্যায়ভিত্তিক প্রশ্ন ও প্রত্যাখ্যান হিটম্যাপ</h2>
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
