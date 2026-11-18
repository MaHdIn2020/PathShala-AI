"use client";

import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Citation {
  chunk_id: number;
  chunk_ref?: string;
  book?: string;
  class_level?: number;
  subject?: string;
  chapter_no?: number;
  chapter?: string;
  page?: number | null;
  snippet?: string;
}

interface AnswerResponse {
  answer: string;
  steps: string[];
  citations: Citation[];
  confidence: number;
  refused: boolean;
  reason?: string | null;
  top_score?: number | null;
  topic?: string | null;
  latency_ms: number;
  cost_usd: number;
  cached: boolean;
  query_id?: number | null;
}

export default function Home() {
  const [classLevel, setClassLevel] = useState<number>(5);
  const [subject, setSubject] = useState<string>("");
  const [question, setQuestion] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [response, setResponse] = useState<AnswerResponse | null>(null);
  const [expandedCitation, setExpandedCitation] = useState<number | null>(null);
  const [feedbackSent, setFeedbackSent] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;

    setLoading(true);
    setResponse(null);
    setErrorMsg(null);
    setFeedbackSent(false);
    setExpandedCitation(null);

    try {
      const res = await fetch(`${API_BASE}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: question.trim(),
          class_level: Number(classLevel),
          subject: subject.trim() || null,
        }),
      });

      if (!res.ok) {
        throw new Error(`সার্ভার ত্রুটি: ${res.statusText} (${res.status})`);
      }

      const data: AnswerResponse = await res.json();
      setResponse(data);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMsg(err.message);
      } else {
        setErrorMsg("নেটওয়ার্ক বা সার্ভার ত্রুটি হয়েছে। অনুগ্রহ করে আবার চেষ্টা করুন।");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleFeedback = async (helpful: boolean) => {
    if (!response?.query_id || feedbackSent) return;
    try {
      await fetch(`${API_BASE}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query_id: response.query_id,
          helpful,
        }),
      });
      setFeedbackSent(true);
    } catch {
      // best-effort feedback
    }
  };

  const handleSpeech = () => {
    if (!response?.answer || typeof window === "undefined" || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(response.answer);
    utterance.lang = "bn-BD";
    window.speechSynthesis.speak(utterance);
  };

  return (
    <main className="min-h-screen bg-slate-50 text-slate-800 p-4 md:p-8 max-w-4xl mx-auto">
      <header className="mb-8 text-center">
        <h1 className="text-3xl font-bold text-emerald-700">পাঠশালা এআই (PathShala AI)</h1>
        <p className="text-slate-600 mt-1">জাতীয় শিক্ষাক্রম ও পাঠ্যপুস্তক বোর্ড (NCTB) ভিত্তিক নির্ভরযোগ্য গৃহশিক্ষক</p>
      </header>

      <form onSubmit={handleSubmit} className="bg-white p-6 rounded-xl shadow-sm border border-slate-200 mb-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
          <div>
            <label htmlFor="class-select" className="block text-sm font-medium text-slate-700 mb-1">
              শ্রেণি (Class):
            </label>
            <select
              id="class-select"
              value={classLevel}
              onChange={(e) => setClassLevel(Number(e.target.value))}
              className="w-full border border-slate-300 rounded-lg p-2.5 focus:ring-2 focus:ring-emerald-500 bg-white"
            >
              {[1, 2, 3, 4, 5].map((c) => (
                <option key={c} value={c}>
                  শ্রেণি {c}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="subject-input" className="block text-sm font-medium text-slate-700 mb-1">
              বিষয় (ঐচ্ছিক):
            </label>
            <input
              id="subject-input"
              type="text"
              placeholder="যেমন: বাংলা, গণিত, বিজ্ঞান..."
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              className="w-full border border-slate-300 rounded-lg p-2.5 focus:ring-2 focus:ring-emerald-500"
            />
          </div>
        </div>

        <div className="mb-4">
          <label htmlFor="question-input" className="block text-sm font-medium text-slate-700 mb-1">
            তোমার প্রশ্ন লিখো:
          </label>
          <textarea
            id="question-input"
            rows={3}
            placeholder="পাঠ্যবই থেকে যেকোনো প্রশ্ন জিজ্ঞাসা করো..."
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            className="w-full border border-slate-300 rounded-lg p-3 focus:ring-2 focus:ring-emerald-500"
            required
          />
        </div>

        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-medium py-3 px-4 rounded-lg transition disabled:opacity-50"
        >
          {loading ? "উত্তর খোঁজা হচ্ছে..." : "উত্তর জানাও"}
        </button>
      </form>

      {errorMsg && (
        <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-lg mb-6">
          {errorMsg}
        </div>
      )}

      {loading && (
        <div className="bg-white p-6 rounded-xl border border-slate-200 animate-pulse space-y-4">
          <div className="h-4 bg-slate-200 rounded w-1/4"></div>
          <div className="h-4 bg-slate-200 rounded w-3/4"></div>
          <div className="h-4 bg-slate-200 rounded w-1/2"></div>
        </div>
      )}

      {response && (
        <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200 space-y-4">
          {response.refused ? (
            <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
              <h2 className="font-semibold text-amber-800 text-lg mb-1">পাঠ্যবইয়ে পাওয়া যায়নি</h2>
              <p className="text-amber-700">
                {response.answer || "এই প্রশ্নের উত্তর পাঠ্যবইয়ে খুঁজে পাইনি।"}
              </p>
              <p className="text-sm text-amber-600 mt-2">
                পরামর্শ: প্রশ্নের বানান ঠিক করে বা নির্দিষ্ট অধ্যায়ের নাম উল্লেখ করে পুনরায় জিজ্ঞাসা করো।
              </p>
            </div>
          ) : (
            <>
              <div className="flex justify-between items-start">
                <h2 className="text-lg font-semibold text-slate-800">উত্তর:</h2>
                <button
                  type="button"
                  onClick={handleSpeech}
                  title="উচ্চারণ শোনো"
                  className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 py-1 px-3 rounded-full border border-slate-300"
                >
                  🔊 পড়ে শোনাও
                </button>
              </div>

              <div className="text-slate-800 leading-relaxed whitespace-pre-line text-base">
                {response.answer}
              </div>

              {response.steps && response.steps.length > 0 && (
                <div className="bg-slate-50 p-4 rounded-lg border border-slate-200">
                  <h3 className="text-sm font-semibold text-slate-700 mb-2">ধাপসমূহ:</h3>
                  <ol className="list-decimal list-inside space-y-1 text-sm text-slate-600">
                    {response.steps.map((st, i) => (
                      <li key={i}>{st}</li>
                    ))}
                  </ol>
                </div>
              )}

              {response.citations && response.citations.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-slate-700 mb-2">উৎস ও প্রমাণ (Citations):</h3>
                  <div className="flex flex-wrap gap-2">
                    {response.citations.map((c) => (
                      <button
                        key={c.chunk_id}
                        type="button"
                        onClick={() =>
                          setExpandedCitation(expandedCitation === c.chunk_id ? null : c.chunk_id)
                        }
                        className={`text-xs px-3 py-1.5 rounded-full border transition ${
                          expandedCitation === c.chunk_id
                            ? "bg-emerald-100 border-emerald-400 text-emerald-800 font-medium"
                            : "bg-slate-100 hover:bg-slate-200 border-slate-300 text-slate-700"
                        }`}
                      >
                        {c.class_level ? `শ্রেণি ${c.class_level}` : ""}
                        {c.subject ? ` · ${c.subject}` : ""}
                        {c.chapter_no ? ` · অধ্যায় ${c.chapter_no}` : ""}
                        {c.chapter ? `: ${c.chapter}` : ""}
                        {c.chunk_ref ? ` (${c.chunk_ref})` : ""}
                      </button>
                    ))}
                  </div>

                  {expandedCitation !== null && (
                    <div className="mt-3 p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-xs text-slate-700">
                      <span className="font-semibold text-emerald-800 block mb-1">পাঠ্যবইয়ের সংশ্লিষ্ট অংশ:</span>
                      <p className="whitespace-pre-line">
                        {response.citations.find((c) => c.chunk_id === expandedCitation)?.snippet ||
                          "উদ্ধৃতি পাওয়া যায়নি"}
                      </p>
                    </div>
                  )}
                </div>
              )}

              <div className="pt-4 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
                <div className="flex items-center gap-2">
                  <span>সহায়ক ছিল?</span>
                  <button
                    type="button"
                    onClick={() => handleFeedback(true)}
                    disabled={feedbackSent}
                    className="hover:text-emerald-600 disabled:opacity-50"
                  >
                    👍 হ্যাঁ
                  </button>
                  <button
                    type="button"
                    onClick={() => handleFeedback(false)}
                    disabled={feedbackSent}
                    className="hover:text-rose-600 disabled:opacity-50"
                  >
                    👎 না
                  </button>
                  {feedbackSent && <span className="text-emerald-600 font-medium ml-1">ধন্যবাদ!</span>}
                </div>

                <span>দেরি: {response.latency_ms}ms</span>
              </div>
            </>
          )}
        </div>
      )}
    </main>
  );
}
