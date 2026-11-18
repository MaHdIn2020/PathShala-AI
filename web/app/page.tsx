"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

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
  transcribed_question?: string;
}

interface PracticeQuestion {
  q: string;
  a: string;
  level: string;
  chunk_id: number;
  chunk_ref?: string;
}

interface PracticeResponse {
  questions: PracticeQuestion[];
  refused: boolean;
  reason?: string | null;
  message?: string;
}

interface CachedEntry {
  question: string;
  classLevel: number;
  subject: string;
  response: AnswerResponse;
}

interface SpeechRecognitionEvent {
  results: {
    [index: number]: {
      [index: number]: {
        transcript: string;
      };
    };
  };
}

interface SpeechRecognitionInstance {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}

interface IWindow extends Window {
  SpeechRecognition?: new () => SpeechRecognitionInstance;
  webkitSpeechRecognition?: new () => SpeechRecognitionInstance;
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
  const [isListening, setIsListening] = useState<boolean>(false);
  const [isOffline, setIsOffline] = useState<boolean>(false);
  const [recentAnswers, setRecentAnswers] = useState<CachedEntry[]>([]);
  const [practiceLoading, setPracticeLoading] = useState<boolean>(false);
  const [practiceData, setPracticeData] = useState<PracticeResponse | null>(null);
  const [openPracticeIdx, setOpenPracticeIdx] = useState<number | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const handleOnline = () => setIsOffline(false);
    const handleOffline = () => setIsOffline(true);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    const win = window as unknown as IWindow;
    const SpeechRecognition = win.SpeechRecognition || win.webkitSpeechRecognition;
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.lang = "bn-BD";
      recognition.continuous = false;
      recognition.interimResults = false;

      recognition.onresult = (event: SpeechRecognitionEvent) => {
        const transcript = event.results[0]?.[0]?.transcript;
        if (transcript) {
          setQuestion((prev) => (prev ? `${prev} ${transcript}` : transcript));
        }
        setIsListening(false);
      };
      recognition.onerror = () => setIsListening(false);
      recognition.onend = () => setIsListening(false);
      recognitionRef.current = recognition;
    }

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  const cacheAnswer = (qText: string, cls: number, subj: string, data: AnswerResponse) => {
    setRecentAnswers((prev) => {
      const filtered = prev.filter((item) => !(item.question === qText && item.classLevel === cls));
      return [{ question: qText, classLevel: cls, subject: subj, response: data }, ...filtered].slice(0, 20);
    });
  };

  const toggleListening = () => {
    if (!recognitionRef.current) {
      setErrorMsg("আপনার ব্রাউজারে বাংলা কণ্ঠ শনাক্তকরণ (Voice Input) সমর্থিত নয়।");
      return;
    }
    if (isListening) {
      recognitionRef.current.stop();
      setIsListening(false);
    } else {
      try {
        recognitionRef.current.start();
        setIsListening(true);
      } catch {
        setIsListening(false);
      }
    }
  };

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 2 * 1024 * 1024) {
      setErrorMsg("ছবির আকার ২ মেগাবাইট (2MB) এর চেয়ে ছোট হতে হবে।");
      return;
    }

    setLoading(true);
    setResponse(null);
    setPracticeData(null);
    setErrorMsg(null);
    setFeedbackSent(false);

    const reader = new FileReader();
    reader.onload = async () => {
      try {
        const base64Data = (reader.result as string).split(",")[1];
        const res = await fetch(`${API_BASE}/ask-image`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            image_base64: base64Data,
            mime_type: file.type || "image/jpeg",
            class_level: Number(classLevel),
            subject: subject.trim() || null,
          }),
        });

        if (!res.ok) {
          throw new Error(`সার্ভার ত্রুটি: ${res.statusText} (${res.status})`);
        }

        const data: AnswerResponse = await res.json();
        setResponse(data);
        const qText = data.transcribed_question || question.trim();
        if (data.transcribed_question) {
          setQuestion(data.transcribed_question);
        }
        if (qText) cacheAnswer(qText, classLevel, subject, data);
      } catch (err: unknown) {
        setErrorMsg(err instanceof Error ? err.message : "ছবি পাঠাতে সমস্যা হয়েছে। আবার চেষ্টা করুন।");
      } finally {
        setLoading(false);
        if (fileInputRef.current) fileInputRef.current.value = "";
      }
    };
    reader.readAsDataURL(file);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const qText = question.trim();
    if (!qText) return;

    setLoading(true);
    setResponse(null);
    setPracticeData(null);
    setOpenPracticeIdx(null);
    setErrorMsg(null);
    setFeedbackSent(false);
    setExpandedCitation(null);

    try {
      const res = await fetch(`${API_BASE}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: qText,
          class_level: Number(classLevel),
          subject: subject.trim() || null,
        }),
      });

      if (!res.ok) {
        throw new Error(`সার্ভার ত্রুটি: ${res.statusText} (${res.status})`);
      }

      const data: AnswerResponse = await res.json();
      setResponse(data);
      cacheAnswer(qText, classLevel, subject, data);
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof Error ? err.message : "নেটওয়ার্ক বা সার্ভার ত্রুটি হয়েছে। অনুগ্রহ করে আবার চেষ্টা করুন।"
      );
    } finally {
      setLoading(false);
    }
  };

  const handlePractice = async () => {
    const topicText = response?.topic || question.trim();
    if (!topicText || practiceLoading) return;
    setPracticeLoading(true);
    setPracticeData(null);
    setOpenPracticeIdx(null);
    try {
      const res = await fetch(`${API_BASE}/practice`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: topicText,
          class_level: Number(classLevel),
          subject: subject.trim() || null,
        }),
      });
      if (!res.ok) {
        throw new Error(`অনুশীলন প্রশ্ন লোড করা যায়নি (${res.status})`);
      }
      const data: PracticeResponse = await res.json();
      setPracticeData(data);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "অনুশীলন প্রশ্ন আনতে সমস্যা হয়েছে।");
    } finally {
      setPracticeLoading(false);
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
      <header className="mb-6 text-center">
        <h1 className="text-3xl font-bold text-emerald-700">পাঠশালা এআই (PathShala AI)</h1>
        <p className="text-slate-600 mt-1">জাতীয় শিক্ষাক্রম ও পাঠ্যপুস্তক বোর্ড (NCTB) ভিত্তিক নির্ভরযোগ্য গৃহশিক্ষক</p>
        <nav aria-label="প্রধান নেভিগেশন" className="mt-3 flex justify-center gap-2">
          <Link
            href="/teacher"
            className="inline-block text-xs px-3 py-1.5 rounded-full border border-emerald-300 bg-emerald-50 text-emerald-800 hover:bg-emerald-100 font-medium"
          >
            📊 শিক্ষক ড্যাশবোর্ড
          </Link>
        </nav>
      </header>

      {isOffline && (
        <div role="alert" className="bg-amber-50 border border-amber-300 text-amber-900 p-3 rounded-lg mb-4 text-sm">
          ইন্টারনেট সংযোগ বিচ্ছিন্ন রয়েছে। নতুন প্রশ্ন করতে অনলাইনে আসুন—তবে নিচে থাকা সাম্প্রতিক উত্তরগুলো দেখতে পারবেন।
        </div>
      )}

      <form onSubmit={handleSubmit} className="bg-white p-6 rounded-xl shadow-sm border border-slate-200 mb-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
          <div>
            <label htmlFor="class-select" className="block text-sm font-medium text-slate-700 mb-1">
              শ্রেণি (১-৫):
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
          <div className="flex justify-between items-center mb-1 gap-2 flex-wrap">
            <label htmlFor="question-input" className="block text-sm font-medium text-slate-700">
              তোমার প্রশ্ন লিখো বা ছবি তোলো:
            </label>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={toggleListening}
                aria-label="মুখে প্রশ্ন বলুন"
                aria-pressed={isListening}
                className={`text-xs px-2.5 py-1 rounded-full border transition flex items-center gap-1 ${
                  isListening
                    ? "bg-rose-100 text-rose-700 border-rose-300 animate-pulse font-medium"
                    : "bg-slate-100 text-slate-700 border-slate-300 hover:bg-slate-200"
                }`}
              >
                🎤 {isListening ? "শুনছি..." : "মুখে বলো"}
              </button>
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                aria-label="পাঠ্যবইয়ের প্রশ্নের ছবি আপলোড করুন"
                className="text-xs px-2.5 py-1 rounded-full border border-slate-300 bg-slate-100 text-slate-700 hover:bg-slate-200 flex items-center gap-1"
              >
                📷 ছবি আপলোড
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                capture="environment"
                onChange={handleImageUpload}
                aria-label="প্রশ্নের ছবি ফাইল নির্বাচন করুন"
                className="hidden"
              />
            </div>
          </div>

          <textarea
            id="question-input"
            rows={3}
            placeholder="পাঠ্যবই থেকে যেকোনো প্রশ্ন জিজ্ঞাসা করো অথবা পাতার ছবি তোলো..."
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
        <div role="alert" className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-lg mb-6">
          {errorMsg}
        </div>
      )}

      {loading && (
        <div aria-busy="true" aria-live="polite" className="bg-white p-6 rounded-xl border border-slate-200 animate-pulse space-y-4">
          <div className="h-4 bg-slate-200 rounded w-1/4"></div>
          <div className="h-4 bg-slate-200 rounded w-3/4"></div>
          <div className="h-4 bg-slate-200 rounded w-1/2"></div>
        </div>
      )}

      {response && (
        <section aria-live="polite" className="bg-white p-6 rounded-xl shadow-sm border border-slate-200 space-y-4">
          {response.reason === "safety_distress" ? (
            <div role="alert" className="p-4 bg-sky-50 border border-sky-300 rounded-lg space-y-2">
              <h2 className="font-semibold text-sky-900 text-lg">আমরা তোমার পাশে আছি</h2>
              <p className="text-sky-900 leading-relaxed">{response.answer}</p>
            </div>
          ) : response.refused ? (
            <div role="status" className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
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
              <div className="flex flex-wrap justify-between items-center gap-2">
                <h2 className="text-lg font-semibold text-slate-800">উত্তর:</h2>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={handlePractice}
                    disabled={practiceLoading}
                    aria-label="এই অধ্যায় থেকে অনুশীলন প্রশ্ন তৈরি করুন"
                    className="text-xs bg-emerald-50 hover:bg-emerald-100 text-emerald-800 py-1 px-3 rounded-full border border-emerald-300 disabled:opacity-50"
                  >
                    {practiceLoading ? "প্রশ্ন তৈরি হচ্ছে..." : "📝 অনুশীলন"}
                  </button>
                  <button
                    type="button"
                    onClick={handleSpeech}
                    aria-label="উত্তর পড়ে শোনান"
                    title="উচ্চারণ শোনো"
                    className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 py-1 px-3 rounded-full border border-slate-300"
                  >
                    🔊 পড়ে শোনাও
                  </button>
                </div>
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
                  <h3 className="text-sm font-semibold text-slate-700 mb-2">উৎস ও প্রমাণ (পাঠ্যবইয়ের অংশ):</h3>
                  <div className="flex flex-wrap gap-2">
                    {response.citations.map((c) => (
                      <button
                        key={c.chunk_id}
                        type="button"
                        aria-expanded={expandedCitation === c.chunk_id}
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

              {practiceData && (
                <div className="mt-3 p-4 bg-slate-50 border border-slate-200 rounded-lg space-y-3">
                  <h3 className="text-sm font-semibold text-slate-800">অনুশীলন প্রশ্ন</h3>
                  {practiceData.refused || practiceData.questions.length === 0 ? (
                    <p className="text-xs text-slate-600">
                      {practiceData.message || "এই বিষয়ে অনুশীলন প্রশ্ন তৈরি করা যায়নি।"}
                    </p>
                  ) : (
                    <ol className="space-y-2 text-sm">
                      {practiceData.questions.map((pq, i) => (
                        <li key={i} className="bg-white p-3 rounded-lg border border-slate-200">
                          <div className="font-medium text-slate-800">
                            {i + 1}. {pq.q}
                          </div>
                          <div className="mt-1 flex items-center justify-between text-xs text-slate-500">
                            <span>উৎস: {pq.chunk_ref || `#${pq.chunk_id}`}</span>
                            <button
                              type="button"
                              onClick={() => setOpenPracticeIdx(openPracticeIdx === i ? null : i)}
                              className="text-emerald-700 hover:underline font-medium"
                            >
                              {openPracticeIdx === i ? "উত্তর লুকাও" : "উত্তর দেখো"}
                            </button>
                          </div>
                          {openPracticeIdx === i && (
                            <p className="mt-2 text-xs text-slate-700 bg-emerald-50 p-2 rounded border border-emerald-200">
                              {pq.a}
                            </p>
                          )}
                        </li>
                      ))}
                    </ol>
                  )}
                </div>
              )}

              <div className="pt-4 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
                <div className="flex items-center gap-2">
                  <span>সহায়ক ছিল?</span>
                  <button
                    type="button"
                    aria-label="হ্যাঁ, উত্তরটি সহায়ক ছিল"
                    onClick={() => handleFeedback(true)}
                    disabled={feedbackSent}
                    className="hover:text-emerald-600 disabled:opacity-50"
                  >
                    👍 হ্যাঁ
                  </button>
                  <button
                    type="button"
                    aria-label="না, উত্তরটি সহায়ক ছিল না"
                    onClick={() => handleFeedback(false)}
                    disabled={feedbackSent}
                    className="hover:text-rose-600 disabled:opacity-50"
                  >
                    👎 না
                  </button>
                  {feedbackSent && <span className="text-emerald-600 font-medium ml-1">ধন্যবাদ!</span>}
                </div>

                <span>সময়: {response.latency_ms}ms</span>
              </div>
            </>
          )}
        </section>
      )}

      {recentAnswers.length > 0 && (
        <section aria-label="সাম্প্রতিক প্রশ্ন ও উত্তর" className="mt-6 bg-white p-4 rounded-xl border border-slate-200">
          <h2 className="text-xs font-semibold text-slate-600 mb-2">সাম্প্রতিক প্রশ্ন (এই সেশনে সংরক্ষিত):</h2>
          <div className="flex flex-wrap gap-2">
            {recentAnswers.map((entry, idx) => (
              <button
                key={`${entry.classLevel}-${idx}`}
                type="button"
                onClick={() => {
                  setClassLevel(entry.classLevel);
                  setSubject(entry.subject);
                  setQuestion(entry.question);
                  setResponse(entry.response);
                  setPracticeData(null);
                  setExpandedCitation(null);
                }}
                className="text-xs px-2.5 py-1 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300 truncate max-w-xs"
              >
                শ্রেণি {entry.classLevel}: {entry.question}
              </button>
            ))}
          </div>
        </section>
      )}

      <footer className="mt-8 text-center text-xs text-slate-500">
        সতর্কতা: এআই ভুল করতে পারে — এনসিটিবি পাঠ্যবই-ই চূড়ান্ত কর্তৃপক্ষ। কোনো ব্যক্তিগত তথ্য বা ছবি সংরক্ষণ করা হয় না।
      </footer>
    </main>
  );
}
