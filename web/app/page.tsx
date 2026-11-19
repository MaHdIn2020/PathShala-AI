"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const DEFAULT_ERROR_MSG = "নেটওয়ার্ক বা সার্ভার ত্রুটি হয়েছে। কয়েক সেকেন্ড পর আবার চেষ্টা করুন।";

async function fetchWithRetry(
  url: string,
  init: RequestInit,
  timeoutMs = 25000,
  retries = 1
): Promise<Response> {
  let lastErr: unknown;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch(url, { ...init, signal: controller.signal });
      clearTimeout(timer);
      if (res.ok || (res.status >= 400 && res.status < 500) || attempt === retries) {
        return res;
      }
      lastErr = new Error(`HTTP ${res.status}`);
    } catch (err) {
      clearTimeout(timer);
      lastErr = err;
      if (attempt === retries) throw err;
    }
    await new Promise((r) => setTimeout(r, 1200));
  }
  throw lastErr;
}

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

interface ChatTurn {
  id: string;
  question: string;
  classLevel: number;
  subject: string;
  response: AnswerResponse;
  feedbackSent?: boolean;
  practice?: PracticeResponse | null;
  practiceLoading?: boolean;
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

const SUBJECT_OPTIONS = [
  { value: "", label: "সকল বিষয়" },
  { value: "bangla", label: "বাংলা" },
  { value: "math", label: "গণিত" },
  { value: "science", label: "বিজ্ঞান" },
  { value: "english", label: "ইংরেজি" },
  { value: "bgs", label: "বাংলাদেশ ও বিশ্বপরিচয়" },
  { value: "islam", label: "ইসলাম ও নৈতিক শিক্ষা" },
  { value: "hindu_religion", label: "হিন্দুধর্ম ও নৈতিক শিক্ষা" },
  { value: "buddhist_religion", label: "বৌদ্ধধর্ম ও নৈতিক শিক্ষা" },
  { value: "christian_religion", label: "খ্রিস্টধর্ম ও নৈতিক শিক্ষা" },
];

const STARTER_PROMPTS = [
  {
    classLevel: 5,
    subject: "science",
    tag: "শ্রেণি ৫ · বিজ্ঞান",
    question: "খাদ্যশৃঙ্খল কাকে বলে?",
  },
  {
    classLevel: 5,
    subject: "bangla",
    tag: "শ্রেণি ৫ · বাংলা",
    question: "বাংলাদেশে বসবাসকারী ক্ষুদ্র নৃগোষ্ঠীর মাতৃভাষা কী কী?",
  },
  {
    classLevel: 5,
    subject: "bgs",
    tag: "শ্রেণি ৫ · বাবি",
    question: "লালবাগ কেল্লা কোথায় অবস্থিত?",
  },
  {
    classLevel: 3,
    subject: "bangla",
    tag: "শ্রেণি ৩ · বাংলা",
    question: "আমাদের গ্রাম কবিতায় গ্রামের মানুষ কীভাবে থাকে?",
  },
];

export default function Home() {
  const [classLevel, setClassLevel] = useState<number>(5);
  const [subject, setSubject] = useState<string>("");
  const [question, setQuestion] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [streamPreview, setStreamPreview] = useState<string>("");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [expandedCite, setExpandedCite] = useState<Record<string, number | null>>({});
  const [openPracticeKey, setOpenPracticeKey] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isListening, setIsListening] = useState<boolean>(false);
  const [isOffline, setIsOffline] = useState<boolean>(false);
  const [apiStatus, setApiStatus] = useState<"waking" | "ready" | "degraded">("waking");
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(false);
  const [recommendedChapter, setRecommendedChapter] = useState<{
    chapter: string;
    mastery: number;
    difficulty: string;
    class_level: number;
    subject: string;
  } | null>(null);
  const [weakCount, setWeakCount] = useState<number>(0);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const turnSeqRef = useRef<number>(0);
  const sessionIdRef = useRef<string>("anon-web");

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

  useEffect(() => {
    let active = true;
    fetchWithRetry(`${API_BASE}/health`, { method: "GET" }, 15000, 1)
      .then((res) => {
        if (!active) return;
        setApiStatus(res.ok ? "ready" : "degraded");
      })
      .catch(() => {
        if (!active) return;
        setApiStatus("degraded");
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, loading]);

  const askQuestion = async (qText: string, cls: number, subj: string) => {
    const cleanQ = qText.trim();
    if (!cleanQ || loading) return;

    setLoading(true);
    setStreamPreview("");
    setErrorMsg(null);
    setQuestion("");

    try {
      const payload = JSON.stringify({
        question: cleanQ,
        class_level: Number(cls),
        subject: subj.trim() || null,
      });
      const res = await fetchWithRetry(
        `${API_BASE}/ask/stream`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: payload,
        },
        25000,
        1
      );
      if (!res.ok) {
        throw new Error(`HTTP_${res.status}`);
      }
      let data: AnswerResponse | null = null;
      const contentType = res.headers.get("content-type") || "";
      if (contentType.includes("text/event-stream") && res.body) {
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          const parts = buf.split("\n\n");
          buf = parts.pop() || "";
          for (const part of parts) {
            const line = part.trim();
            if (!line.startsWith("data:")) continue;
            try {
              const ev = JSON.parse(line.slice(5).trim());
              if (ev.type === "delta" && typeof ev.text === "string") {
                setStreamPreview((prev) => prev + ev.text);
              } else if (ev.type === "done" && ev.payload) {
                data = ev.payload as AnswerResponse;
              }
            } catch {
              // ignore malformed SSE chunk
            }
          }
        }
      } else {
        data = (await res.json()) as AnswerResponse;
      }
      if (!data) {
        throw new Error("EMPTY_STREAM");
      }
      setApiStatus("ready");
      turnSeqRef.current += 1;
      const id = `t-${turnSeqRef.current}`;
      setTurns((prev) => [...prev, { id, question: cleanQ, classLevel: cls, subject: subj, response: data }].slice(-20));
    } catch (err: unknown) {
      if (err instanceof Error && err.name === "AbortError") {
        setErrorMsg("সার্ভার থেকে উত্তর আসতে বেশি সময় লাগছে (ফ্রি সার্ভার চালু হতে কয়েক সেকেন্ড লাগতে পারে)। আবার চেষ্টা করুন।");
      } else if (err instanceof Error && err.message.startsWith("HTTP_")) {
        setErrorMsg("সার্ভার সাময়িকভাবে ব্যস্ত আছে। কয়েক সেকেন্ড পর আবার চেষ্টা করুন।");
      } else {
        setErrorMsg(DEFAULT_ERROR_MSG);
      }
    } finally {
      setStreamPreview("");
      setLoading(false);
    }
  };

  const recordPracticeAttempt = async (turn: ChatTurn, correct: boolean) => {
    const chapter = turn.response.topic || turn.response.citations?.[0]?.chapter || "অধ্যায়";
    try {
      const res = await fetch(`${API_BASE}/practice/attempt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionIdRef.current,
          class_level: turn.classLevel,
          subject: turn.subject || "general",
          chapter,
          correct,
        }),
      });
      if (!res.ok) return;
      const data = await res.json();
      setRecommendedChapter(data?.mastery?.recommended_chapter || null);
      setWeakCount((data?.mastery?.weak_chapters || []).length);
    } catch {
      // ignore offline attempt error
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    askQuestion(question, classLevel, subject);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      askQuestion(question, classLevel, subject);
    }
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

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) {
      setErrorMsg("ছবির আকার ২ মেগাবাইট (2MB) এর চেয়ে ছোট হতে হবে।");
      return;
    }

    setLoading(true);
    setErrorMsg(null);
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
        turnSeqRef.current += 1;
        const id = `t-${turnSeqRef.current}`;
        const qText = data.transcribed_question || "📷 ছবির প্রশ্ন";
        setTurns((prev) => [...prev, { id, question: qText, classLevel, subject, response: data }].slice(-20));
      } catch (err: unknown) {
        setErrorMsg(err instanceof Error ? err.message : "ছবি পাঠাতে সমস্যা হয়েছে। আবার চেষ্টা করুন।");
      } finally {
        setLoading(false);
        if (fileInputRef.current) fileInputRef.current.value = "";
      }
    };
    reader.readAsDataURL(file);
  };

  const handlePractice = async (turn: ChatTurn) => {
    if (turn.practiceLoading) return;
    setTurns((prev) => prev.map((t) => (t.id === turn.id ? { ...t, practiceLoading: true } : t)));
    try {
      const res = await fetch(`${API_BASE}/practice`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: turn.response.topic || turn.question,
          class_level: turn.classLevel,
          subject: turn.subject.trim() || null,
        }),
      });
      if (!res.ok) throw new Error(`অনুশীলন প্রশ্ন লোড করা যায়নি (${res.status})`);
      const data: PracticeResponse = await res.json();
      setTurns((prev) =>
        prev.map((t) => (t.id === turn.id ? { ...t, practice: data, practiceLoading: false } : t))
      );
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "অনুশীলন প্রশ্ন আনতে সমস্যা হয়েছে।");
      setTurns((prev) => prev.map((t) => (t.id === turn.id ? { ...t, practiceLoading: false } : t)));
    }
  };

  const handleFeedback = async (turn: ChatTurn, helpful: boolean) => {
    if (!turn.response.query_id || turn.feedbackSent) return;
    setTurns((prev) => prev.map((t) => (t.id === turn.id ? { ...t, feedbackSent: true } : t)));
    try {
      await fetch(`${API_BASE}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query_id: turn.response.query_id, helpful }),
      });
    } catch {
      // best-effort feedback
    }
  };

  const handleSpeech = (text: string) => {
    if (!text || typeof window === "undefined" || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "bn-BD";
    window.speechSynthesis.speak(utterance);
  };

  const subjectLabel = SUBJECT_OPTIONS.find((s) => s.value === subject)?.label || "সকল বিষয়";

  return (
    <div className="flex h-screen w-full overflow-hidden bg-[#08080d] text-[#eef2f3]">
      {/* Mobile Sidebar Backdrop */}
      {sidebarOpen && (
        <button
          type="button"
          aria-label="সাইডবার বন্ধ করুন"
          onClick={() => setSidebarOpen(false)}
          className="fixed inset-0 z-30 bg-black/60 backdrop-blur-xs md:hidden"
        />
      )}

      {/* Left Sidebar (ChatGPT / Claude Style) */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-white/10 bg-[#0d1117] transition-transform duration-200 md:static md:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between border-b border-white/10 px-4 py-4">
          <div className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-[#00e5ff]/40 bg-[#00e5ff]/10 font-display text-sm font-bold text-[#00e5ff]">
              পা
            </span>
            <div>
              <div className="font-display text-sm font-bold tracking-tight text-white">PathShalaAI</div>
              <div className="font-mono-code text-[10px] uppercase tracking-widest text-[#00e5ff]">
                NCTB PRIMARY · 1–5
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setSidebarOpen(false)}
            aria-label="মেনু বন্ধ করুন"
            className="rounded-lg p-1.5 text-slate-400 hover:bg-white/5 hover:text-white md:hidden"
          >
            ✕
          </button>
        </div>

        <div className="p-3">
          <button
            type="button"
            onClick={() => {
              setTurns([]);
              setErrorMsg(null);
              setSidebarOpen(false);
            }}
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-[#00e5ff]/35 bg-[#00e5ff]/10 px-3 py-2.5 text-sm font-medium text-[#00e5ff] transition hover:bg-[#00e5ff]/20"
          >
            <span>＋</span> নতুন আলোচনা
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-3 py-2">
          <div className="mb-2 px-2 font-mono-code text-[10px] uppercase tracking-widest text-slate-500">
            সাম্প্রতিক প্রশ্ন ({turns.length})
          </div>
          {turns.length === 0 ? (
            <p className="px-2 text-xs text-slate-500">তোমার করা প্রশ্নগুলো এখানে দেখা যাবে।</p>
          ) : (
            <ul className="space-y-1">
              {[...turns].reverse().map((t) => (
                <li key={t.id}>
                  <button
                    type="button"
                    onClick={() => {
                      document.getElementById(`turn-${t.id}`)?.scrollIntoView({ behavior: "smooth" });
                      setSidebarOpen(false);
                    }}
                    className="w-full truncate rounded-lg px-2.5 py-2 text-left text-xs text-slate-300 transition hover:bg-white/5 hover:text-white"
                  >
                    <span className="mr-1.5 font-mono-code text-[10px] text-[#00e5ff]">C{t.classLevel}</span>
                    {t.question}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="border-t border-white/10 p-3 space-y-2">
          <Link
            href="/teacher"
            className="flex items-center justify-between rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2.5 text-xs font-medium text-slate-200 transition hover:border-[#00e5ff]/40 hover:bg-[#00e5ff]/10 hover:text-[#00e5ff]"
          >
            <span>📊 শিক্ষক ড্যাশবোর্ড</span>
            <span className="font-mono-code text-[10px] text-slate-400">→</span>
          </Link>
          <div className="flex items-center justify-between px-2 font-mono-code text-[10px] text-slate-500">
            <span className="flex items-center gap-1.5">
              <span className={`h-1.5 w-1.5 rounded-full ${isOffline ? "bg-amber-400" : "bg-[#00e5ff]"}`} />
              {isOffline ? "OFFLINE" : "GROUNDED RAG"}
            </span>
            <span>CC BY 4.0</span>
          </div>
        </div>
      </aside>

      {/* Main Chat Area */}
      <div className="ambient-glow flex flex-1 flex-col overflow-hidden">
        {/* Top Header Bar */}
        <header className="flex items-center justify-between border-b border-white/10 bg-[#08080d]/80 px-4 py-3 backdrop-blur-md">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setSidebarOpen(true)}
              aria-label="সাইডবার খুলুন"
              className="rounded-lg border border-white/10 bg-white/5 px-2.5 py-1.5 text-sm text-slate-200 hover:bg-white/10 md:hidden"
            >
              ☰
            </button>
            <div className="flex items-center gap-2">
              <span className="font-display text-sm font-semibold text-white">PathShalaAI</span>
              <span className="rounded-full border border-[#00e5ff]/30 bg-[#00e5ff]/10 px-2.5 py-0.5 font-mono-code text-[11px] text-[#00e5ff]">
                শ্রেণি {classLevel} · {subjectLabel}
              </span>
            </div>
          </div>
          <Link
            href="/teacher"
            className="hidden rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs text-slate-300 transition hover:border-[#00e5ff]/40 hover:text-[#00e5ff] sm:inline-block"
          >
            শিক্ষক ড্যাশবোর্ড
          </Link>
        </header>

        {isOffline && (
          <div role="alert" className="border-b border-amber-500/30 bg-amber-500/10 px-4 py-2 text-center text-xs text-amber-200">
            ইন্টারনেট সংযোগ বিচ্ছিন্ন রয়েছে। নতুন প্রশ্ন করতে অনলাইনে আসুন—পূর্বের উত্তরগুলো নিচে দেখা যাবে।
          </div>
        )}

        {!isOffline && apiStatus === "waking" && (
          <div role="status" aria-live="polite" className="border-b border-[#00e5ff]/25 bg-[#00e5ff]/10 px-4 py-2 text-center text-xs text-[#a5f3fc]">
            সার্ভার চালু হচ্ছে... প্রথমবার উত্তর আসতে কয়েক সেকেন্ড লাগতে পারে।
          </div>
        )}

        {!isOffline && apiStatus === "degraded" && (
          <div role="status" aria-live="polite" className="border-b border-amber-500/30 bg-amber-500/10 px-4 py-2 text-center text-xs text-amber-200">
            সার্ভার এখন জেগে উঠছে বা ব্যস্ত আছে—প্রশ্ন করলে স্বয়ংক্রিয়ভাবে আবার চেষ্টা করা হবে।
          </div>
        )}

        {recommendedChapter && (
          <div className="border-b border-[#00e5ff]/20 bg-[#0d1117] px-4 py-2 text-center text-xs text-slate-200">
            পরবর্তী সুপারিশকৃত অধ্যায়: <span className="font-semibold text-[#00e5ff]">{recommendedChapter.chapter}</span>{" "}
            (দক্ষতা {Math.round(recommendedChapter.mastery * 100)}% · ধাপ: {recommendedChapter.difficulty}
            {weakCount > 0 ? ` · দুর্বল অধ্যায়: ${weakCount}` : ""})
          </div>
        )}

        {/* Scrollable Chat Thread */}
        <main className="flex-1 overflow-y-auto px-4 py-6">
          <div className="mx-auto max-w-3xl space-y-6">
            {turns.length === 0 && !loading ? (
              <div className="flex flex-col items-center justify-center py-10 text-center md:py-16">
                <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-[#00e5ff]/30 bg-[#00e5ff]/10 px-3.5 py-1 font-mono-code text-[11px] uppercase tracking-widest text-[#00e5ff]">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#00e5ff]" />
                  NCTB Textbook Grounded Tutor
                </div>
                <h1 className="font-display text-3xl font-bold tracking-tight text-white md:text-5xl">
                  আজ কী শিখতে চাও?
                </h1>
                <p className="mt-3 max-w-xl text-sm leading-relaxed text-[#8b94a3] md:text-base">
                  ১ম থেকে ৫ম শ্রেণির এনসিটিবি পাঠ্যবই থেকে যেকোনো প্রশ্ন করো—লিখে, মুখে বলে বা পাতার ছবি তুলে। প্রতিটি উত্তর আসবে অধ্যায়ের প্রমাণসহ।
                </p>

                <div className="mt-8 grid w-full grid-cols-1 gap-3 sm:grid-cols-2">
                  {STARTER_PROMPTS.map((item, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => {
                        setClassLevel(item.classLevel);
                        setSubject(item.subject);
                        askQuestion(item.question, item.classLevel, item.subject);
                      }}
                      className="group rounded-2xl border border-white/10 bg-[#0d1117]/90 p-4 text-left transition hover:border-[#00e5ff]/50 hover:bg-[#111827]"
                    >
                      <div className="mb-1.5 font-mono-code text-[10px] uppercase tracking-wider text-[#00e5ff]">
                        {item.tag}
                      </div>
                      <div className="text-sm font-medium text-slate-200 group-hover:text-white">
                        {item.question}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              turns.map((turn) => {
                const resp = turn.response;
                const activeCiteId = expandedCite[turn.id] ?? null;
                return (
                  <article key={turn.id} id={`turn-${turn.id}`} className="space-y-4">
                    {/* User Bubble */}
                    <div className="flex justify-end">
                      <div className="max-w-[85%] rounded-2xl rounded-tr-sm border border-white/10 bg-[#161d2b] px-4 py-3 text-sm text-white shadow-sm">
                        <div className="mb-1 font-mono-code text-[10px] text-[#00e5ff]">
                          শ্রেণি {turn.classLevel}
                          {turn.subject ? ` · ${turn.subject}` : ""}
                        </div>
                        <p className="whitespace-pre-line leading-relaxed">{turn.question}</p>
                      </div>
                    </div>

                    {/* Assistant Response */}
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-[#00e5ff]/40 bg-[#00e5ff]/10 font-display text-xs font-bold text-[#00e5ff]">
                        AI
                      </div>

                      <div className="min-w-0 flex-1 space-y-3 rounded-2xl border border-white/10 bg-[#0d1117] p-4 md:p-5">
                        {resp.reason === "safety_distress" ? (
                          <div role="alert" className="rounded-xl border border-sky-400/40 bg-sky-500/10 p-4 text-sky-100">
                            <h2 className="mb-1 text-base font-semibold text-sky-300">আমরা তোমার পাশে আছি</h2>
                            <p className="text-sm leading-relaxed">{resp.answer}</p>
                          </div>
                        ) : resp.refused ? (
                          <div role="status" className="rounded-xl border border-amber-400/30 bg-amber-500/10 p-4">
                            <div className="mb-1 font-display text-sm font-semibold text-amber-300">
                              পাঠ্যবইয়ে পাওয়া যায়নি
                            </div>
                            <p className="text-sm text-amber-100/90">
                              {resp.answer || "এই প্রশ্নের উত্তর পাঠ্যবইয়ে খুঁজে পাইনি।"}
                            </p>
                            <p className="mt-2 text-xs text-amber-200/70">
                              পরামর্শ: সঠিক শ্রেণি ও বিষয় নির্বাচন করে বা অধ্যায়ের মূল শব্দ দিয়ে পুনরায় জিজ্ঞাসা করো।
                            </p>
                          </div>
                        ) : (
                          <>
                            <div className="whitespace-pre-line text-[15px] leading-7 text-[#eef2f3]">
                              {resp.answer}
                            </div>

                            {resp.steps && resp.steps.length > 0 && (
                              <div className="rounded-xl border border-white/10 bg-[#08080d]/70 p-3.5">
                                <div className="mb-2 font-mono-code text-[11px] uppercase tracking-wider text-[#00e5ff]">
                                  ধাপসমূহ (Steps)
                                </div>
                                <ol className="list-inside list-decimal space-y-1.5 text-sm text-slate-300">
                                  {resp.steps.map((st, i) => (
                                    <li key={i}>{st}</li>
                                  ))}
                                </ol>
                              </div>
                            )}

                            {resp.citations && resp.citations.length > 0 && (
                              <div className="pt-1">
                                <div className="mb-2 font-mono-code text-[10px] uppercase tracking-widest text-slate-400">
                                  উৎস ও প্রমাণ (Citations)
                                </div>
                                <div className="flex flex-wrap gap-2">
                                  {resp.citations.map((c) => {
                                    const isOpen = activeCiteId === c.chunk_id;
                                    return (
                                      <button
                                        key={c.chunk_id}
                                        type="button"
                                        aria-expanded={isOpen}
                                        onClick={() =>
                                          setExpandedCite((prev) => ({
                                            ...prev,
                                            [turn.id]: isOpen ? null : c.chunk_id,
                                          }))
                                        }
                                        className={`rounded-full border px-3 py-1 font-mono-code text-[11px] transition ${
                                          isOpen
                                            ? "border-[#00e5ff] bg-[#00e5ff]/15 text-[#00e5ff]"
                                            : "border-white/15 bg-white/[0.03] text-slate-300 hover:border-[#00e5ff]/50 hover:text-white"
                                        }`}
                                      >
                                        {c.class_level ? `শ্রেণি ${c.class_level}` : ""}
                                        {c.subject ? ` · ${c.subject}` : ""}
                                        {c.chapter_no ? ` · অধ্যায় ${c.chapter_no}` : ""}
                                        {c.chapter ? `: ${c.chapter}` : ""}
                                      </button>
                                    );
                                  })}
                                </div>

                                {activeCiteId !== null && (
                                  <div className="mt-3 rounded-xl border border-[#00e5ff]/30 bg-[#00e5ff]/[0.06] p-3.5 text-xs text-slate-200">
                                    <div className="mb-1 font-mono-code text-[10px] uppercase tracking-wider text-[#00e5ff]">
                                      পাঠ্যবইয়ের মূল অংশ (
                                      {resp.citations.find((c) => c.chunk_id === activeCiteId)?.chunk_ref || `#${activeCiteId}`}
                                      )
                                    </div>
                                    <p className="whitespace-pre-line leading-relaxed text-slate-200">
                                      {resp.citations.find((c) => c.chunk_id === activeCiteId)?.snippet || "উদ্ধৃতি পাওয়া যায়নি"}
                                    </p>
                                  </div>
                                )}
                              </div>
                            )}

                            {/* Practice Section */}
                            {turn.practice && (
                              <div className="mt-3 space-y-2.5 rounded-xl border border-white/10 bg-[#08080d]/80 p-4">
                                <div className="font-mono-code text-[11px] uppercase tracking-wider text-[#00e5ff]">
                                  অনুশীলন প্রশ্ন (Practice)
                                </div>
                                {turn.practice.refused || turn.practice.questions.length === 0 ? (
                                  <p className="text-xs text-slate-400">
                                    {turn.practice.message || "এই বিষয়ে অনুশীলন প্রশ্ন তৈরি করা যায়নি।"}
                                  </p>
                                ) : (
                                  <ol className="space-y-2 text-sm">
                                    {turn.practice.questions.map((pq, idx) => {
                                      const key = `${turn.id}-${idx}`;
                                      const isOpen = openPracticeKey === key;
                                      return (
                                        <li key={key} className="rounded-lg border border-white/10 bg-[#0d1117] p-3">
                                          <div className="font-medium text-slate-100">
                                            {idx + 1}. {pq.q}
                                          </div>
                                          <div className="mt-1.5 flex items-center justify-between text-xs text-slate-400">
                                            <span className="font-mono-code text-[10px]">
                                              উৎস: {pq.chunk_ref || `#${pq.chunk_id}`}
                                            </span>
                                            <button
                                              type="button"
                                              onClick={() => setOpenPracticeKey(isOpen ? null : key)}
                                              className="font-medium text-[#00e5ff] hover:underline"
                                            >
                                              {isOpen ? "উত্তর লুকাও" : "উত্তর দেখো"}
                                            </button>
                                          </div>
                                          {isOpen && (
                                            <div className="mt-2 space-y-2 rounded-lg border border-[#00e5ff]/25 bg-[#00e5ff]/10 p-2.5 text-xs text-slate-100">
                                              <p>{pq.a}</p>
                                              <div className="flex items-center gap-2 pt-1">
                                                <button
                                                  type="button"
                                                  onClick={() => recordPracticeAttempt(turn, true)}
                                                  className="rounded border border-emerald-400/40 bg-emerald-500/10 px-2 py-0.5 text-[11px] text-emerald-200 hover:bg-emerald-500/20"
                                                >
                                                  ✓ পেরেছি
                                                </button>
                                                <button
                                                  type="button"
                                                  onClick={() => recordPracticeAttempt(turn, false)}
                                                  className="rounded border border-amber-400/40 bg-amber-500/10 px-2 py-0.5 text-[11px] text-amber-200 hover:bg-amber-500/20"
                                                >
                                                  ✗ আবার শিখব
                                                </button>
                                              </div>
                                            </div>
                                          )}
                                        </li>
                                      );
                                    })}
                                  </ol>
                                )}
                              </div>
                            )}

                            {/* Action Toolbar */}
                            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-white/10 pt-3 text-xs text-slate-400">
                              <div className="flex flex-wrap items-center gap-2">
                                <button
                                  type="button"
                                  onClick={() => handleSpeech(resp.answer)}
                                  aria-label="উত্তর পড়ে শোনান"
                                  className="rounded-lg border border-white/10 bg-white/[0.03] px-2.5 py-1 transition hover:border-[#00e5ff]/40 hover:text-white"
                                >
                                  🔊 শোনো
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handlePractice(turn)}
                                  disabled={turn.practiceLoading}
                                  aria-label="অনুশীলন প্রশ্ন তৈরি করুন"
                                  className="rounded-lg border border-white/10 bg-white/[0.03] px-2.5 py-1 transition hover:border-[#00e5ff]/40 hover:text-[#00e5ff] disabled:opacity-50"
                                >
                                  {turn.practiceLoading ? "তৈরি হচ্ছে..." : "📝 অনুশীলন"}
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleFeedback(turn, true)}
                                  disabled={turn.feedbackSent}
                                  aria-label="উত্তরটি সহায়ক ছিল"
                                  className="rounded-lg px-2 py-1 transition hover:bg-white/5 hover:text-[#00e5ff] disabled:opacity-40"
                                >
                                  👍
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleFeedback(turn, false)}
                                  disabled={turn.feedbackSent}
                                  aria-label="উত্তরটি সহায়ক ছিল না"
                                  className="rounded-lg px-2 py-1 transition hover:bg-white/5 hover:text-rose-400 disabled:opacity-40"
                                >
                                  👎
                                </button>
                                {turn.feedbackSent && <span className="text-[#00e5ff]">ধন্যবাদ!</span>}
                              </div>
                              <span className="font-mono-code text-[11px] text-slate-500">
                                {resp.latency_ms}ms
                              </span>
                            </div>
                          </>
                        )}
                      </div>
                    </div>
                  </article>
                );
              })
            )}

            {loading && (
              <div aria-busy="true" aria-live="polite" className="flex items-start gap-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-[#00e5ff]/40 bg-[#00e5ff]/10 font-display text-xs font-bold text-[#00e5ff]">
                  AI
                </div>
                <div className="flex items-center gap-2 rounded-2xl border border-white/10 bg-[#0d1117] px-4 py-3 text-sm text-slate-300">
                  <span className="h-2 w-2 shrink-0 animate-pulse rounded-full bg-[#00e5ff]" />
                  <span>{streamPreview || "পাঠ্যবই খুঁজে উত্তর তৈরি হচ্ছে..."}</span>
                </div>
              </div>
            )}

            {errorMsg && (
              <div role="alert" className="rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
                {errorMsg.trim() || DEFAULT_ERROR_MSG}
              </div>
            )}

            <div ref={bottomRef} />
          </div>
        </main>

        {/* Floating Chat Composer */}
        <div className="border-t border-white/10 bg-[#08080d]/90 px-4 pb-4 pt-3 backdrop-blur-md">
          <form onSubmit={handleSubmit} className="mx-auto max-w-3xl">
            <div className="rounded-2xl border border-white/15 bg-[#0d1117] p-2.5 shadow-lg transition focus-within:border-[#00e5ff]/60">
              <div className="mb-2 flex flex-wrap items-center gap-2 border-b border-white/5 pb-2">
                <select
                  aria-label="শ্রেণি নির্বাচন করুন"
                  value={classLevel}
                  onChange={(e) => setClassLevel(Number(e.target.value))}
                  className="rounded-lg border border-white/10 bg-[#111827] px-2.5 py-1 text-xs font-medium text-slate-200 focus:border-[#00e5ff] focus:outline-none"
                >
                  {[1, 2, 3, 4, 5].map((c) => (
                    <option key={c} value={c}>
                      শ্রেণি {c}
                    </option>
                  ))}
                </select>
                <select
                  aria-label="বিষয় নির্বাচন করুন"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  className="rounded-lg border border-white/10 bg-[#111827] px-2.5 py-1 text-xs font-medium text-slate-200 focus:border-[#00e5ff] focus:outline-none"
                >
                  {SUBJECT_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-end gap-2">
                <textarea
                  id="question-input"
                  rows={2}
                  placeholder="পাঠ্যবই থেকে যেকোনো প্রশ্ন লিখো... (Enter চাপলে উত্তর আসবে)"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={handleKeyDown}
                  className="max-h-40 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm text-white placeholder-slate-500 focus:outline-none"
                />

                <div className="flex items-center gap-1.5 pb-1">
                  <button
                    type="button"
                    onClick={toggleListening}
                    aria-label="মুখে প্রশ্ন বলুন"
                    aria-pressed={isListening}
                    title="মুখে বলো (বাংলা)"
                    className={`rounded-xl border px-2.5 py-2 text-xs transition ${
                      isListening
                        ? "animate-pulse border-rose-400 bg-rose-500/20 text-rose-200"
                        : "border-white/10 bg-white/[0.04] text-slate-300 hover:border-[#00e5ff]/40 hover:text-white"
                    }`}
                  >
                    🎤
                  </button>
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    aria-label="প্রশ্নের ছবি আপলোড করুন"
                    title="ছবি আপলোড"
                    className="rounded-xl border border-white/10 bg-white/[0.04] px-2.5 py-2 text-xs text-slate-300 transition hover:border-[#00e5ff]/40 hover:text-white"
                  >
                    📷
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
                  <button
                    type="submit"
                    disabled={loading || !question.trim()}
                    aria-label="প্রশ্ন পাঠান"
                    className="rounded-xl bg-[#00e5ff] px-4 py-2 font-display text-xs font-bold text-[#001318] transition hover:bg-[#33ecff] disabled:opacity-40"
                  >
                    পাঠাও ↑
                  </button>
                </div>
              </div>
            </div>
            <p className="mt-2 text-center font-mono-code text-[10px] text-slate-500">
              এআই ভুল করতে পারে — এনসিটিবি পাঠ্যবই-ই চূড়ান্ত কর্তৃপক্ষ · কোনো ব্যক্তিগত তথ্য বা ছবি সংরক্ষিত হয় না
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}
