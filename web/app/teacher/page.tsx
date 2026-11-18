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
  if (refusalRate >= 0.35) return "bg-rose-100 text-rose-800 border-rose-300";
  if (refusalRate >= 0.15) return "bg-amber-100 text-amber-800 border-amber-300";
  return "bg-emerald-100 text-emerald-800 border-emerald-300";
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
    <main className="min-h-screen bg-slate-50 text-slate-800 p-4 md:p-8 max-w-5xl mx-auto space-y-6">
      <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-emerald-700">শিক্ষক বিশ্লেষণ ড্যাশবোর্ড</h1>
          <p className="text-sm text-slate-600 mt-1">
            শিক্ষার্থীদের প্রশ্ন, দুর্বল অধ্যায় ও উত্তর প্রত্যাখ্যানের সারসংক্ষেপ (কোনো ব্যক্তিগত তথ্য সংরক্ষিত নয়)
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={loadSummary}
            disabled={loading}
            className="text-xs px-3 py-2 rounded-lg border border-slate-300 bg-white hover:bg-slate-100 disabled:opacity-50"
          >
            🔄 রিফ্রেশ
          </button>
          <Link
            href="/"
            className="text-xs px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-medium"
          >
            ← প্রশ্ন করুন
          </Link>
        </div>
      </header>

      {data?.has_seed_data && (
        <div className="bg-amber-50 border border-amber-300 text-amber-900 p-4 rounded-xl text-sm">
          <span className="font-semibold">নোট (Demo vs Real Data):</span> এই ড্যাশবোর্ডে{" "}
          <span className="font-semibold">{data.seed_queries}টি ডেমো প্রশ্ন</span> (<code>session_id=&apos;seed&apos;</code>)
          এবং <span className="font-semibold">{data.real_queries}টি প্রকৃত প্রশ্ন</span> দেখানো হচ্ছে। ডেমো ডেটা
          শুধুমাত্র প্রদর্শনের জন্য, প্রকৃত ব্যবহার নয়।
        </div>
      )}

      {errorMsg && (
        <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-lg">
          {errorMsg}
        </div>
      )}

      {loading && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 animate-pulse">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="bg-white p-5 rounded-xl border border-slate-200 h-24" />
          ))}
        </div>
      )}

      {data && !loading && (
        <>
          <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
              <div className="text-xs text-slate-500">মোট প্রশ্ন</div>
              <div className="text-2xl font-bold text-slate-800 mt-1">{data.total_queries}</div>
              <div className="text-xs text-slate-500 mt-1">
                ডেমো: {data.seed_queries} · প্রকৃত: {data.real_queries}
              </div>
            </div>

            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
              <div className="text-xs text-slate-500">প্রত্যাখ্যানের হার (Refusal Rate)</div>
              <div className="text-2xl font-bold text-rose-700 mt-1">
                {(data.refusal_rate * 100).toFixed(1)}%
              </div>
              <div className="text-xs text-slate-500 mt-1">প্রত্যাখ্যাত: {data.refused_queries}টি</div>
            </div>

            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
              <div className="text-xs text-slate-500">সহায়ক উত্তরের হার (Helpful)</div>
              <div className="text-2xl font-bold text-emerald-700 mt-1">
                {(data.helpful_rate * 100).toFixed(1)}%
              </div>
              <div className="text-xs text-slate-500 mt-1">
                সন্তুষ্ট: {data.helpful_count}/{data.feedback_count}
              </div>
            </div>

            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
              <div className="text-xs text-slate-500">সক্রিয় অধ্যায়</div>
              <div className="text-2xl font-bold text-slate-800 mt-1">{data.chapters.length}</div>
              <div className="text-xs text-slate-500 mt-1">শীর্ষ অধ্যায়ভিত্তিক তালিকা</div>
            </div>
          </section>

          <section className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1">
              <h2 className="text-lg font-semibold text-slate-800">অধ্যায়ভিত্তিক প্রশ্ন ও দুর্বলতা হিটম্যাপ</h2>
              <span className="text-xs text-slate-500">লাল = বেশি প্রত্যাখ্যান (≥35%) · সবুজ = ভালো ফলাফল</span>
            </div>

            {data.chapters.length === 0 ? (
              <p className="text-sm text-slate-500">এখনো কোনো অধ্যায়ভিত্তিক প্রশ্ন জমা হয়নি।</p>
            ) : (
              <div className="space-y-3">
                {data.chapters.map((ch, idx) => {
                  const pct = Math.max(4, Math.round((ch.n / maxChapterCount) * 100));
                  return (
                    <div key={`${ch.class_level}-${ch.subject}-${ch.topic}-${idx}`} className="space-y-1">
                      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                        <div className="font-medium text-slate-800">
                          শ্রেণি {ch.class_level} · {ch.subject} · {ch.topic}
                        </div>
                        <div className="flex items-center gap-2 text-xs">
                          <span className="text-slate-600">{ch.n}টি (ডেমো {ch.seed_n} / প্রকৃত {ch.real_n})</span>
                          <span className={`px-2 py-0.5 rounded-full border ${heatBadgeClass(ch.refusal_rate)}`}>
                            প্রত্যাখ্যান {(ch.refusal_rate * 100).toFixed(0)}%
                          </span>
                          {ch.feedback_count > 0 && (
                            <span className="text-emerald-700">
                              সহায়ক {(ch.helpful_rate * 100).toFixed(0)}%
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="w-full h-2.5 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${
                            ch.refusal_rate >= 0.35
                              ? "bg-rose-500"
                              : ch.refusal_rate >= 0.15
                                ? "bg-amber-500"
                                : "bg-emerald-500"
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

          <section className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-4">
            <h2 className="text-lg font-semibold text-slate-800">সবচেয়ে বেশি জিজ্ঞাসিত ১০টি প্রশ্ন</h2>
            {data.top_questions.length === 0 ? (
              <p className="text-sm text-slate-500">কোনো প্রশ্ন পাওয়া যায়নি।</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left border-collapse">
                  <thead>
                    <tr className="border-b border-slate-200 text-xs text-slate-500">
                      <th className="py-2 pr-3">#</th>
                      <th className="py-2 pr-3">প্রশ্ন</th>
                      <th className="py-2 pr-3">শ্রেণি / অধ্যায়</th>
                      <th className="py-2 pr-3 text-right">বার</th>
                      <th className="py-2 text-right">প্রত্যাখ্যাত</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.top_questions.map((q, i) => (
                      <tr key={i} className="border-b border-slate-100 last:border-0">
                        <td className="py-2.5 pr-3 text-slate-500">{i + 1}</td>
                        <td className="py-2.5 pr-3 text-slate-800">
                          {q.question}
                          {q.seed_n > 0 && (
                            <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-800">
                              ডেমো
                            </span>
                          )}
                        </td>
                        <td className="py-2.5 pr-3 text-xs text-slate-600">
                          {q.class_level ? `শ্রেণি ${q.class_level}` : ""}
                          {q.subject ? ` · ${q.subject}` : ""}
                          {q.topic ? ` · ${q.topic}` : ""}
                        </td>
                        <td className="py-2.5 pr-3 text-right font-semibold">{q.n}</td>
                        <td className="py-2.5 text-right text-rose-700">{q.refused}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </main>
  );
}

