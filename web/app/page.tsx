"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

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

interface CatalogBook {
  id: number;
  curriculum_id: string;
  textbook_medium: "bangla_version" | "english_version";
  class_level: number;
  subject: string;
  title: string;
  chunk_count: number;
  embedded_count: number;
}

interface Citation {
  chunk_id: number;
  chunk_ref?: string;
  book?: string;
  curriculum_id?: string;
  textbook_medium?: string;
  class_level?: number;
  subject?: string;
  chapter_no?: number;
  chapter?: string;
  page?: number | null;
  page_start?: number | null;
  page_end?: number | null;
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
  textbook_medium?: string;
  answer_language?: string;
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

interface McqOption {
  id: "A" | "B" | "C" | "D";
  text: string;
}

interface DiagnosticCheck {
  refused?: boolean;
  reason?: string | null;
  message?: string;
  question_id: string;
  curriculum_id: string;
  textbook_medium: string;
  class_level: number;
  subject: string;
  chapter_no?: number | null;
  chapter: string;
  learning_objective: string;
  question_text: string;
  answer_language: string;
  options: McqOption[];
  correct_option: "A" | "B" | "C" | "D";
  explanation: string;
  misconception_labels: Record<string, string>;
  source: Citation;
}

interface MasteryChapter {
  class_level: number;
  subject: string;
  chapter: string;
  mastery: number;
  attempts: number;
  correct: number;
  difficulty: string;
}

interface MasterySnapshot {
  session_id: string;
  indicator_label?: string;
  chapters: MasteryChapter[];
  weak_chapters: MasteryChapter[];
  recommended_chapter: MasteryChapter | null;
}

interface ConceptSubmitResult {
  is_correct: boolean;
  selected_option: string;
  correct_option: string;
  feedback: string;
  likely_misconception: string | null;
  confidence: number | null;
  reteach_explanation: string | null;
  follow_up_question: DiagnosticCheck | null;
  source: Citation;
  attempt: {
    mastery: number;
    attempts: number;
    correct: number;
    difficulty: string;
    duplicate?: boolean;
  };
  mastery: MasterySnapshot;
}

interface ChatTurn {
  id: string;
  question: string;
  classLevel: number;
  subject: string;
  textbookMedium: "bangla_version" | "english_version";
  answerLanguage: "bn" | "en";
  response: AnswerResponse;
  feedbackSent?: boolean;
  practice?: PracticeResponse | null;
  practiceLoading?: boolean;
  englishExplain?: string | null;
  englishLoading?: boolean;
  diagnostic?: DiagnosticCheck | null;
  diagnosticLoading?: boolean;
  diagnosticResult?: ConceptSubmitResult | null;
  diagnosticSubmitting?: boolean;
  followUpResult?: ConceptSubmitResult | null;
  followUpSubmitting?: boolean;
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

const SUBJECT_LABELS: Record<string, { bn: string; en: string }> = {
  bangla: { bn: "বাংলা", en: "Bangla" },
  bangla_grammar: { bn: "বাংলা ব্যাকরণ", en: "Bangla Grammar" },
  bangla_rapidreader: { bn: "সহপাঠ", en: "Bangla Rapid Reader" },
  english: { bn: "ইংরেজি", en: "English" },
  english_grammar: { bn: "ইংরেজি ব্যাকরণ", en: "English Grammar" },
  math: { bn: "গণিত", en: "Mathematics" },
  higher_math: { bn: "উচ্চতর গণিত", en: "Higher Math" },
  science: { bn: "বিজ্ঞান", en: "Science" },
  physics_secondary: { bn: "পদার্থবিজ্ঞান", en: "Physics" },
  chemistry_secondary: { bn: "রসায়ন", en: "Chemistry" },
  biology_secondary: { bn: "জীববিজ্ঞান", en: "Biology" },
  bgs: { bn: "বাংলাদেশ ও বিশ্বপরিচয়", en: "Bangladesh & Global Studies" },
  ict: { bn: "তথ্য ও যোগাযোগ প্রযুক্তি", en: "ICT" },
  agriculture: { bn: "কৃষিশিক্ষা", en: "Agriculture Studies" },
  home_science: { bn: "গার্হস্থ্য বিজ্ঞান", en: "Home Science" },
  work_and_life: { bn: "কর্ম ও জীবনমুখী শিক্ষা", en: "Work & Life Oriented Edu." },
  arts_and_crafts: { bn: "চারু ও কারুকলা", en: "Arts & Crafts" },
  physical_education: { bn: "শারীরিক শিক্ষা ও স্বাস্থ্য", en: "Physical Education" },
  islam: { bn: "ইসলাম ও নৈতিক শিক্ষা", en: "Islam & Moral Edu." },
  hindu_religion: { bn: "হিন্দুধর্ম ও নৈতিক শিক্ষা", en: "Hinduism & Moral Edu." },
  buddhist_religion: { bn: "বৌদ্ধধর্ম ও নৈতিক শিক্ষা", en: "Buddhism & Moral Edu." },
  christian_religion: { bn: "খ্রিস্টধর্ম ও নৈতিক শিক্ষা", en: "Christianity & Moral Edu." },
  accounting: { bn: "হিসাববিজ্ঞান", en: "Accounting" },
  economics: { bn: "অর্থনীতি", en: "Economics" },
  civics: { bn: "পৌরনীতি ও নাগরিকতা", en: "Civics & Citizenship" },
  geography: { bn: "ভূগোল ও পরিবেশ", en: "Geography" },
  history: { bn: "বাংলাদেশের ইতিহাস ও বিশ্বসভ্যতা", en: "History" },
  finance: { bn: "ফিন্যান্স ও ব্যাংকিং", en: "Finance & Banking" },
  career_education: { bn: "ক্যারিয়ার শিক্ষা", en: "Career Education" },
};

function subjectName(slug: string, uiLang: "bn" | "en"): string {
  const entry = SUBJECT_LABELS[slug];
  if (entry) return entry[uiLang];
  return slug.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatPageLabel(c: Citation, uiLang: "bn" | "en"): string {
  if (c.page_start !== null && c.page_start !== undefined) {
    if (c.page_end && c.page_end !== c.page_start) {
      return uiLang === "bn" ? `পৃষ্ঠা ${c.page_start}–${c.page_end}` : `pp. ${c.page_start}-${c.page_end}`;
    }
    return uiLang === "bn" ? `পৃষ্ঠা ${c.page_start}` : `p. ${c.page_start}`;
  }
  return uiLang === "bn" ? "অধ্যায়-ভিত্তিক উৎস (পৃষ্ঠা নম্বর নেই)" : "Chapter-level source (no page #)";
}

const FALLBACK_CATALOG: CatalogBook[] = [
  ...[1, 2].flatMap((c) =>
    ["bangla", "english", "math"].map((s, idx) => ({
      id: c * 100 + idx,
      curriculum_id: "nctb",
      textbook_medium: "bangla_version" as const,
      class_level: c,
      subject: s,
      title: `NCTB শ্রেণি ${c} · ${s}`,
      chunk_count: 50,
      embedded_count: 50,
    }))
  ),
  ...[3, 4, 5].flatMap((c) =>
    ["bangla", "math", "science", "english", "bgs", "islam", "hindu_religion", "buddhist_religion", "christian_religion"].map(
      (s, idx) => ({
        id: c * 100 + idx,
        curriculum_id: "nctb",
        textbook_medium: "bangla_version" as const,
        class_level: c,
        subject: s,
        title: `NCTB শ্রেণি ${c} · ${s}`,
        chunk_count: 100,
        embedded_count: 100,
      })
    )
  ),
  {
    id: 8001,
    curriculum_id: "nctb",
    textbook_medium: "english_version",
    class_level: 8,
    subject: "science",
    title: "NCTB Class 8 · science (English Version)",
    chunk_count: 824,
    embedded_count: 824,
  },
];

const STARTER_PROMPTS = [
  {
    medium: "english_version" as const,
    answerLang: "bn" as const,
    classLevel: 8,
    subject: "science",
    tag: "EN Version · Class 8 · Science → বাংলায় ব্যাখ্যা",
    question: "What is diffusion and how does it work in plants?",
  },
  {
    medium: "bangla_version" as const,
    answerLang: "bn" as const,
    classLevel: 5,
    subject: "science",
    tag: "বাংলা ভার্সন · শ্রেণি ৫ · বিজ্ঞান",
    question: "খাদ্যশৃঙ্খল কাকে বলে?",
  },
  {
    medium: "english_version" as const,
    answerLang: "en" as const,
    classLevel: 8,
    subject: "science",
    tag: "EN Version · Class 8 · Science → English",
    question: "What is the difference between an acid and a base?",
  },
  {
    medium: "bangla_version" as const,
    answerLang: "bn" as const,
    classLevel: 5,
    subject: "bgs",
    tag: "বাংলা ভার্সন · শ্রেণি ৫ · বাবি",
    question: "লালবাগ কেল্লা কোথায় অবস্থিত?",
  },
];

export default function Home() {
  const [textbookMedium, setTextbookMedium] = useState<"bangla_version" | "english_version">("english_version");
  const [answerLanguage, setAnswerLanguage] = useState<"bn" | "en">("bn");
  const [classLevel, setClassLevel] = useState<number>(8);
  const [subject, setSubject] = useState<string>("science");
  const [catalog, setCatalog] = useState<CatalogBook[]>(FALLBACK_CATALOG);
  const [question, setQuestion] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [streamPreview, setStreamPreview] = useState<string>("");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [expandedCite, setExpandedCite] = useState<Record<string, number | null>>({});
  const [openPracticeKey, setOpenPracticeKey] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isListening, setIsListening] = useState<boolean>(false);
  const [isOffline, setIsOffline] = useState<boolean>(false);
  const [uiLang, setUiLang] = useState<"bn" | "en">("bn");
  const [apiStatus, setApiStatus] = useState<"waking" | "ready" | "degraded">("waking");
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(false);
  const [recommendedChapter, setRecommendedChapter] = useState<MasteryChapter | null>(null);
  const [weakCount, setWeakCount] = useState<number>(0);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const turnSeqRef = useRef<number>(0);
  const sessionIdRef = useRef<string>("anon-web");

  useEffect(() => {
    if (typeof window === "undefined") return;
    let sid = window.localStorage.getItem("pathshala_session_id");
    if (!sid) {
      sid = `anon-${Math.random().toString(36).slice(2, 10)}`;
      window.localStorage.setItem("pathshala_session_id", sid);
    }
    sessionIdRef.current = sid;

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

    fetch(`${API_BASE}/curriculum/catalog`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!active || !data?.books?.length) return;
        setCatalog(data.books as CatalogBook[]);
      })
      .catch(() => {
        // fallback catalog remains active
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, loading]);

  const availableClasses = useMemo(() => {
    const set = new Set<number>();
    for (const b of catalog) {
      if (b.textbook_medium === textbookMedium) set.add(b.class_level);
    }
    const list = Array.from(set).sort((a, b) => a - b);
    return list.length ? list : [1, 2, 3, 4, 5];
  }, [catalog, textbookMedium]);

  const availableSubjects = useMemo(() => {
    const subs = catalog
      .filter((b) => b.textbook_medium === textbookMedium && b.class_level === classLevel)
      .map((b) => b.subject);
    return Array.from(new Set(subs)).sort();
  }, [catalog, textbookMedium, classLevel]);

  const handleMediumChange = (med: "bangla_version" | "english_version") => {
    setTextbookMedium(med);
    const classesForMed = Array.from(
      new Set(catalog.filter((b) => b.textbook_medium === med).map((b) => b.class_level))
    ).sort((a, b) => a - b);
    const nextClass = classesForMed.includes(classLevel)
      ? classLevel
      : med === "english_version" && classesForMed.includes(8)
        ? 8
        : classesForMed[0] ?? 5;
    setClassLevel(nextClass);
    const subsForClass = catalog
      .filter((b) => b.textbook_medium === med && b.class_level === nextClass)
      .map((b) => b.subject);
    if (subject && !subsForClass.includes(subject)) {
      setSubject(subsForClass.includes("science") ? "science" : "");
    }
  };

  const handleClassChange = (cls: number) => {
    setClassLevel(cls);
    const subsForClass = catalog
      .filter((b) => b.textbook_medium === textbookMedium && b.class_level === cls)
      .map((b) => b.subject);
    if (subject && !subsForClass.includes(subject)) {
      setSubject("");
    }
  };

  const askQuestion = async (
    qText: string,
    cls: number,
    subj: string,
    med: "bangla_version" | "english_version" = textbookMedium,
    ansLang: "bn" | "en" = answerLanguage
  ) => {
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
        session_id: sessionIdRef.current,
        curriculum_id: "nctb",
        textbook_medium: med,
        answer_language: ansLang,
      });
      let res = await fetchWithRetry(
        `${API_BASE}/ask/stream`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: payload,
        },
        30000,
        1
      );
      if (res.status === 404 || res.status === 405) {
        res = await fetchWithRetry(
          `${API_BASE}/ask`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: payload,
          },
          30000,
          1
        );
      }
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
      setTurns((prev) =>
        [
          ...prev,
          {
            id,
            question: cleanQ,
            classLevel: cls,
            subject: subj,
            textbookMedium: med,
            answerLanguage: ansLang,
            response: data,
          },
        ].slice(-20)
      );
    } catch (err: unknown) {
      if (err instanceof Error && err.name === "AbortError") {
        setErrorMsg("সার্ভার থেকে উত্তর আসতে বেশি সময় লাগছে। আবার চেষ্টা করুন।");
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

  const handleStartConceptCheck = async (turn: ChatTurn) => {
    if (turn.diagnosticLoading) return;
    setTurns((prev) =>
      prev.map((t) =>
        t.id === turn.id
          ? { ...t, diagnosticLoading: true, diagnostic: null, diagnosticResult: null, followUpResult: null }
          : t
      )
    );
    try {
      const topCite = turn.response.citations?.[0];
      const res = await fetch(`${API_BASE}/concept-rescue/check`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: turn.question,
          answer: turn.response.answer,
          class_level: turn.classLevel,
          subject: turn.subject.trim() || topCite?.subject || null,
          curriculum_id: "nctb",
          textbook_medium: turn.textbookMedium,
          answer_language: turn.answerLanguage,
          chunk_id: topCite?.chunk_id ?? null,
        }),
      });
      if (!res.ok) throw new Error(`HTTP_${res.status}`);
      const diag: DiagnosticCheck = await res.json();
      setTurns((prev) =>
        prev.map((t) => (t.id === turn.id ? { ...t, diagnostic: diag, diagnosticLoading: false } : t))
      );
    } catch {
      setErrorMsg("ধারণা যাচাই প্রশ্ন তৈরি করা যায়নি। আবার চেষ্টা করুন।");
      setTurns((prev) => prev.map((t) => (t.id === turn.id ? { ...t, diagnosticLoading: false } : t)));
    }
  };

  const handleSubmitDiagnostic = async (
    turn: ChatTurn,
    diag: DiagnosticCheck,
    optionId: "A" | "B" | "C" | "D",
    isFollowUp = false
  ) => {
    if (isFollowUp ? turn.followUpSubmitting : turn.diagnosticSubmitting) return;
    setTurns((prev) =>
      prev.map((t) =>
        t.id === turn.id
          ? isFollowUp
            ? { ...t, followUpSubmitting: true }
            : { ...t, diagnosticSubmitting: true }
          : t
      )
    );
    try {
      const eventKey = `${sessionIdRef.current}:${turn.id}:${diag.question_id}:${optionId}`;
      const res = await fetch(`${API_BASE}/concept-rescue/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionIdRef.current,
          diagnostic: diag,
          selected_option: optionId,
          event_key: eventKey,
          answer_language: turn.answerLanguage,
        }),
      });
      if (!res.ok) throw new Error(`HTTP_${res.status}`);
      const result: ConceptSubmitResult = await res.json();
      setRecommendedChapter(result?.mastery?.recommended_chapter || null);
      setWeakCount((result?.mastery?.weak_chapters || []).length);
      setTurns((prev) =>
        prev.map((t) =>
          t.id === turn.id
            ? isFollowUp
              ? { ...t, followUpResult: result, followUpSubmitting: false }
              : { ...t, diagnosticResult: result, diagnosticSubmitting: false }
            : t
        )
      );
    } catch {
      setErrorMsg("উত্তর মূল্যায়ন করা যায়নি। আবার চেষ্টা করুন।");
      setTurns((prev) =>
        prev.map((t) =>
          t.id === turn.id
            ? isFollowUp
              ? { ...t, followUpSubmitting: false }
              : { ...t, diagnosticSubmitting: false }
            : t
        )
      );
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
          curriculum_id: "nctb",
          textbook_medium: turn.textbookMedium,
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

  const handleResetSession = async () => {
    const oldSid = sessionIdRef.current;
    try {
      await fetch(`${API_BASE}/session/${encodeURIComponent(oldSid)}`, { method: "DELETE" });
    } catch {
      // best-effort deletion
    }
    if (typeof window !== "undefined") {
      const newSid = `anon-${Math.random().toString(36).slice(2, 10)}`;
      window.localStorage.setItem("pathshala_session_id", newSid);
      sessionIdRef.current = newSid;
    }
    setTurns([]);
    setRecommendedChapter(null);
    setWeakCount(0);
    setErrorMsg(null);
  };

  const handleExplainEnglish = async (turn: ChatTurn) => {
    if (turn.englishLoading || turn.englishExplain) return;
    setTurns((prev) => prev.map((t) => (t.id === turn.id ? { ...t, englishLoading: true } : t)));
    try {
      const res = await fetch(`${API_BASE}/explain-en`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: turn.question, answer: turn.response.answer }),
      });
      if (!res.ok) throw new Error("fail");
      const data = await res.json();
      setTurns((prev) =>
        prev.map((t) => (t.id === turn.id ? { ...t, englishExplain: data.english || "", englishLoading: false } : t))
      );
    } catch {
      setTurns((prev) => prev.map((t) => (t.id === turn.id ? { ...t, englishLoading: false } : t)));
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    askQuestion(question, classLevel, subject, textbookMedium, answerLanguage);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      askQuestion(question, classLevel, subject, textbookMedium, answerLanguage);
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
        recognitionRef.current.lang = answerLanguage === "en" ? "en-US" : "bn-BD";
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
            session_id: sessionIdRef.current,
            curriculum_id: "nctb",
            textbook_medium: textbookMedium,
            answer_language: answerLanguage,
          }),
        });
        if (!res.ok) {
          throw new Error(`সার্ভার ত্রুটি: ${res.statusText} (${res.status})`);
        }
        const data: AnswerResponse = await res.json();
        turnSeqRef.current += 1;
        const id = `t-${turnSeqRef.current}`;
        const qText = data.transcribed_question || "📷 ছবির প্রশ্ন";
        setTurns((prev) =>
          [
            ...prev,
            {
              id,
              question: qText,
              classLevel,
              subject,
              textbookMedium,
              answerLanguage,
              response: data,
            },
          ].slice(-20)
        );
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
          curriculum_id: "nctb",
          textbook_medium: turn.textbookMedium,
          answer_language: turn.answerLanguage,
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

  const handleSpeech = (text: string, lang: "bn" | "en") => {
    if (!text || typeof window === "undefined" || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang === "en" ? "en-US" : "bn-BD";
    window.speechSynthesis.speak(utterance);
  };

  const subjectLabel = subject ? subjectName(subject, uiLang) : uiLang === "bn" ? "সকল বিষয়" : "All Subjects";
  const mediumLabel =
    textbookMedium === "english_version"
      ? uiLang === "bn"
        ? "English Version"
        : "NCTB English Version"
      : uiLang === "bn"
        ? "বাংলা ভার্সন"
        : "NCTB Bangla Version";

  return (
    <div className="flex h-screen w-full overflow-hidden bg-[#08080d] text-[#eef2f3]">
      {sidebarOpen && (
        <button
          type="button"
          aria-label="সাইডবার বন্ধ করুন"
          onClick={() => setSidebarOpen(false)}
          className="fixed inset-0 z-30 bg-black/60 backdrop-blur-xs md:hidden"
        />
      )}

      {/* Left Sidebar */}
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
                NCTB · CLASSES 1–10
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

        <div className="space-y-2 p-3">
          <button
            type="button"
            onClick={() => {
              setTurns([]);
              setErrorMsg(null);
              setSidebarOpen(false);
            }}
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-[#00e5ff]/35 bg-[#00e5ff]/10 px-3 py-2.5 text-sm font-medium text-[#00e5ff] transition hover:bg-[#00e5ff]/20"
          >
            <span>＋</span> {uiLang === "bn" ? "নতুন আলোচনা" : "New Topic"}
          </button>
          <button
            type="button"
            onClick={handleResetSession}
            className="flex w-full items-center justify-center gap-1.5 rounded-xl border border-white/10 bg-white/[0.02] px-3 py-1.5 text-xs text-slate-400 transition hover:border-rose-400/40 hover:text-rose-200"
          >
            🗑 {uiLang === "bn" ? "সেশন ডেটা মুছুন" : "Clear Session Progress"}
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-3 py-2">
          <div className="mb-2 px-2 font-mono-code text-[10px] uppercase tracking-widest text-slate-500">
            {uiLang === "bn" ? `সাম্প্রতিক প্রশ্ন (${turns.length})` : `Recent Questions (${turns.length})`}
          </div>
          {turns.length === 0 ? (
            <p className="px-2 text-xs text-slate-500">
              {uiLang === "bn" ? "তোমার করা প্রশ্নগুলো এখানে দেখা যাবে।" : "Your questions will appear here."}
            </p>
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
                    <span className="mr-1.5 font-mono-code text-[10px] text-[#00e5ff]">
                      {t.textbookMedium === "english_version" ? "EN" : "BN"}·C{t.classLevel}
                    </span>
                    {t.question}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="space-y-2 border-t border-white/10 p-3">
          <Link
            href="/teacher"
            className="flex items-center justify-between rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2.5 text-xs font-medium text-slate-200 transition hover:border-[#00e5ff]/40 hover:bg-[#00e5ff]/10 hover:text-[#00e5ff]"
          >
            <span>📊 {uiLang === "bn" ? "শিক্ষক ড্যাশবোর্ড" : "Teacher Dashboard"}</span>
            <span className="font-mono-code text-[10px] text-slate-400">→</span>
          </Link>
          <div className="flex items-center justify-between px-2 font-mono-code text-[10px] text-slate-500">
            <span className="flex items-center gap-1.5">
              <span className={`h-1.5 w-1.5 rounded-full ${isOffline ? "bg-amber-400" : "bg-[#00e5ff]"}`} />
              {isOffline ? "OFFLINE SHELL" : "CONCEPT RESCUE"}
            </span>
            <span>CC BY 4.0</span>
          </div>
        </div>
      </aside>

      {/* Main Chat Area */}
      <div className="ambient-glow flex flex-1 flex-col overflow-hidden">
        <header className="flex items-center justify-between border-b border-white/10 bg-[#08080d]/80 px-4 py-3 backdrop-blur-md">
          <div className="flex items-center gap-3 min-w-0">
            <button
              type="button"
              onClick={() => setSidebarOpen(true)}
              aria-label="সাইডবার খুলুন"
              className="rounded-lg border border-white/10 bg-white/5 px-2.5 py-1.5 text-sm text-slate-200 hover:bg-white/10 md:hidden"
            >
              ☰
            </button>
            <div className="flex flex-wrap items-center gap-2 min-w-0">
              <span className="font-display text-sm font-semibold text-white">PathShalaAI</span>
              <span className="truncate rounded-full border border-[#00e5ff]/30 bg-[#00e5ff]/10 px-2.5 py-0.5 font-mono-code text-[11px] text-[#00e5ff]">
                {mediumLabel} · {uiLang === "bn" ? `শ্রেণি ${classLevel}` : `Class ${classLevel}`} · {subjectLabel}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={() => setUiLang((l) => (l === "bn" ? "en" : "bn"))}
              aria-label="Toggle UI language"
              className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 font-mono-code text-[11px] text-slate-200 transition hover:border-[#00e5ff]/40 hover:text-[#00e5ff]"
            >
              {uiLang === "bn" ? "UI: EN" : "UI: বাংলা"}
            </button>
            <Link
              href="/teacher"
              className="hidden rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs text-slate-300 transition hover:border-[#00e5ff]/40 hover:text-[#00e5ff] sm:inline-block"
            >
              {uiLang === "bn" ? "শিক্ষক ড্যাশবোর্ড" : "Teacher Dashboard"}
            </Link>
          </div>
        </header>

        {isOffline && (
          <div role="alert" className="border-b border-amber-500/30 bg-amber-500/10 px-4 py-2 text-center text-xs text-amber-200">
            ইন্টারনেট সংযোগ বিচ্ছিন্ন রয়েছে (Offline App Shell)। নতুন AI উত্তরের জন্য অনলাইন সংযোগ প্রয়োজন—আগের উত্তরগুলো নিচে দেখা যাবে।
          </div>
        )}

        {!isOffline && apiStatus === "waking" && (
          <div role="status" aria-live="polite" className="border-b border-[#00e5ff]/25 bg-[#00e5ff]/10 px-4 py-2 text-center text-xs text-[#a5f3fc]">
            সার্ভার চালু হচ্ছে... প্রথমবার উত্তর আসতে কয়েক সেকেন্ড লাগতে পারে।
          </div>
        )}

        {!isOffline && apiStatus === "degraded" && (
          <div role="status" aria-live="polite" className="border-b border-amber-500/30 bg-amber-500/10 px-4 py-2 text-center text-xs text-amber-200">
            সার্ভার এখন ব্যস্ত বা জেগে উঠছে—প্রশ্ন করলে স্বয়ংক্রিয়ভাবে আবার চেষ্টা করা হবে।
          </div>
        )}

        {recommendedChapter && (
          <div className="border-b border-[#00e5ff]/20 bg-[#0d1117] px-4 py-2 text-center text-xs text-slate-200">
            অনুশীলন অগ্রগতি: <span className="font-semibold text-[#00e5ff]">{recommendedChapter.chapter}</span> ·{" "}
            আনুমানিক অনুশীলন দক্ষতা (EWMA): <span className="font-bold text-white">{Math.round(recommendedChapter.mastery * 100)}%</span>{" "}
            ({recommendedChapter.correct}/{recommendedChapter.attempts} সঠিক · ধাপ: {recommendedChapter.difficulty}
            {weakCount > 0 ? ` · পুনরায় চর্চা প্রয়োজন: ${weakCount}টি অধ্যায়` : ""})
          </div>
        )}

        {/* Scrollable Chat Thread */}
        <main className="flex-1 overflow-y-auto px-4 py-6">
          <div className="mx-auto max-w-3xl space-y-6">
            {turns.length === 0 && !loading ? (
              <div className="flex flex-col items-center justify-center py-8 text-center md:py-14">
                <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-[#00e5ff]/30 bg-[#00e5ff]/10 px-3.5 py-1 font-mono-code text-[11px] uppercase tracking-widest text-[#00e5ff]">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#00e5ff]" />
                  Concept Rescue · NCTB Grounded Tutor
                </div>
                <h1 className="font-display text-3xl font-bold tracking-tight text-white md:text-5xl">
                  {uiLang === "bn" ? "সঠিক পাঠ্যবই থেকে ধারণা উদ্ধার করো" : "Learn the concept, not just the answer"}
                </h1>
                <p className="mt-3 max-w-xl text-sm leading-relaxed text-[#8b94a3] md:text-base">
                  {uiLang === "bn"
                    ? "NCTB বাংলা বা English Version পাঠ্যবই বেছে নাও, নিজের পছন্দের ভাষায় ব্যাখ্যা পড়ো, এবং Concept Rescue কুইজের মাধ্যমে ভুল ধারণা শনাক্ত করে তা ঠিক করো।"
                    : "Choose your exact NCTB Bangla or English Version textbook, get explanations in your preferred language, and fix likely misconceptions with Concept Rescue."}
                </p>
                <div className="mt-4 flex flex-wrap items-center justify-center gap-2 font-mono-code text-[11px] text-slate-300">
                  <span className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1">
                    {catalog.length} NCTB Books (Bangla + English Version)
                  </span>
                  <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-emerald-300">
                    Strict Version Isolation
                  </span>
                  <span className="rounded-full border border-[#00e5ff]/30 bg-[#00e5ff]/10 px-3 py-1 text-[#00e5ff]">
                    Concept Rescue Loop
                  </span>
                </div>

                <div className="mt-8 grid w-full grid-cols-1 gap-3 sm:grid-cols-2">
                  {STARTER_PROMPTS.map((item, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => {
                        setTextbookMedium(item.medium);
                        setAnswerLanguage(item.answerLang);
                        setClassLevel(item.classLevel);
                        setSubject(item.subject);
                        askQuestion(item.question, item.classLevel, item.subject, item.medium, item.answerLang);
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
                const diag = turn.diagnostic;
                const dRes = turn.diagnosticResult;
                const fuQ = dRes?.follow_up_question;
                const fuRes = turn.followUpResult;
                return (
                  <article key={turn.id} id={`turn-${turn.id}`} className="space-y-4">
                    {/* User Bubble */}
                    <div className="flex justify-end">
                      <div className="max-w-[85%] rounded-2xl rounded-tr-sm border border-white/10 bg-[#161d2b] px-4 py-3 text-sm text-white shadow-sm">
                        <div className="mb-1 font-mono-code text-[10px] text-[#00e5ff]">
                          {turn.textbookMedium === "english_version" ? "NCTB EN Version" : "NCTB বাংলা ভার্সন"} · শ্রেণি{" "}
                          {turn.classLevel}
                          {turn.subject ? ` · ${subjectName(turn.subject, uiLang)}` : ""} ·{" "}
                          {turn.answerLanguage === "en" ? "Answer: EN" : "ব্যাখ্যা: বাংলা"}
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
                              {resp.reason === "unavailable_curriculum"
                                ? "নির্বাচিত পাঠ্যবই উপলব্ধ নয়"
                                : "পাঠ্যবইয়ে পাওয়া যায়নি"}
                            </div>
                            <p className="text-sm text-amber-100/90">
                              {resp.answer || "এই প্রশ্নের উত্তর পাঠ্যবইয়ে খুঁজে পাইনি।"}
                            </p>
                            <p className="mt-2 text-xs text-amber-200/70">
                              পরামর্শ: সঠিক ভার্সন, শ্রেণি ও বিষয় নির্বাচন করে পুনরায় জিজ্ঞাসা করো।
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
                                  যাচাইকৃত পাঠ্যবই উৎস (Verified Citations)
                                </div>
                                <div className="flex flex-wrap gap-2">
                                  {resp.citations.map((c) => {
                                    const isOpen = activeCiteId === c.chunk_id;
                                    const medTag = c.textbook_medium === "english_version" ? "EN" : "BN";
                                    const pgTag =
                                      c.page_start !== null && c.page_start !== undefined
                                        ? ` · p.${c.page_start}${c.page_end && c.page_end !== c.page_start ? `-${c.page_end}` : ""}`
                                        : "";
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
                                        [{medTag}] {c.class_level ? `Class ${c.class_level}` : ""}
                                        {c.subject ? ` · ${c.subject}` : ""}
                                        {c.chapter_no ? ` · Ch ${c.chapter_no}` : ""}
                                        {c.chapter ? `: ${c.chapter}` : ""}
                                        {pgTag}
                                      </button>
                                    );
                                  })}
                                </div>

                                {activeCiteId !== null && (
                                  <div className="mt-3 rounded-xl border border-[#00e5ff]/30 bg-[#00e5ff]/[0.06] p-3.5 text-xs text-slate-200">
                                    {(() => {
                                      const activeC = resp.citations.find((c) => c.chunk_id === activeCiteId);
                                      return (
                                        <>
                                          <div className="mb-1 flex flex-wrap items-center justify-between gap-2 font-mono-code text-[10px] uppercase tracking-wider text-[#00e5ff]">
                                            <span>
                                              {activeC?.book || "NCTB"} ({activeC?.chunk_ref || `#${activeCiteId}`})
                                            </span>
                                            <span>{activeC ? formatPageLabel(activeC, uiLang) : ""}</span>
                                          </div>
                                          <p className="whitespace-pre-line leading-relaxed text-slate-200">
                                            {activeC?.snippet || "উদ্ধৃতি পাওয়া যায়নি"}
                                          </p>
                                        </>
                                      );
                                    })()}
                                  </div>
                                )}
                              </div>
                            )}

                            {/* Concept Rescue Interactive Card */}
                            <div className="mt-3 rounded-xl border border-[#00e5ff]/25 bg-[#08080d]/85 p-4 space-y-3">
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <div>
                                  <div className="font-mono-code text-[11px] uppercase tracking-wider text-[#00e5ff]">
                                    Concept Rescue · ধারণা যাচাই ও উদ্ধার
                                  </div>
                                  <p className="text-xs text-slate-400">
                                    {uiLang === "bn"
                                      ? "বিষয়টি সত্যি বুঝেছ কি না তা যাচাই করো—ভুল হলে সহজ ভাষায় নতুন উদাহরণ পাবে।"
                                      : "Check your understanding—if missed, get a likely misconception diagnosis and simpler re-explanation."}
                                  </p>
                                </div>
                                {!diag && (
                                  <button
                                    type="button"
                                    onClick={() => handleStartConceptCheck(turn)}
                                    disabled={turn.diagnosticLoading}
                                    className="rounded-xl bg-[#00e5ff] px-3.5 py-2 font-display text-xs font-bold text-[#001318] transition hover:bg-[#33ecff] disabled:opacity-50"
                                  >
                                    {turn.diagnosticLoading
                                      ? "প্রশ্ন তৈরি হচ্ছে..."
                                      : "🎯 ধারণা যাচাই করো (Concept Check)"}
                                  </button>
                                )}
                              </div>

                              {diag && diag.refused && (
                                <p className="text-xs text-amber-300">
                                  {diag.message || "এই অংশের জন্য যাচাই প্রশ্ন তৈরি করা যায়নি।"}
                                </p>
                              )}

                              {diag && !diag.refused && (
                                <div className="space-y-3 border-t border-white/10 pt-3">
                                  <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] font-mono-code text-slate-400">
                                    <span>Objective: {diag.learning_objective}</span>
                                    <span>{formatPageLabel(diag.source, uiLang)}</span>
                                  </div>
                                  <div className="text-sm font-medium text-white">{diag.question_text}</div>
                                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                                    {diag.options.map((opt) => {
                                      const picked = dRes?.selected_option === opt.id;
                                      const isRight = dRes && opt.id === dRes.correct_option;
                                      let cls =
                                        "border-white/10 bg-[#0d1117] text-slate-200 hover:border-[#00e5ff]/50";
                                      if (dRes) {
                                        if (isRight) {
                                          cls = "border-emerald-400/60 bg-emerald-500/15 text-emerald-200";
                                        } else if (picked && !dRes.is_correct) {
                                          cls = "border-rose-400/60 bg-rose-500/15 text-rose-200";
                                        } else {
                                          cls = "border-white/5 bg-[#0d1117]/50 text-slate-500";
                                        }
                                      }
                                      return (
                                        <button
                                          key={opt.id}
                                          type="button"
                                          disabled={Boolean(dRes) || Boolean(turn.diagnosticSubmitting)}
                                          onClick={() => handleSubmitDiagnostic(turn, diag, opt.id, false)}
                                          className={`rounded-xl border px-3 py-2.5 text-left text-xs transition ${cls}`}
                                        >
                                          <span className="mr-2 font-mono-code font-bold text-[#00e5ff]">
                                            {opt.id}.
                                          </span>
                                          {opt.text}
                                        </button>
                                      );
                                    })}
                                  </div>

                                  {turn.diagnosticSubmitting && (
                                    <p className="text-xs text-[#00e5ff]">উত্তর যাচাই ও বিশ্লেষণ করা হচ্ছে...</p>
                                  )}

                                  {dRes && (
                                    <div className="space-y-3 rounded-xl border border-white/10 bg-[#0d1117] p-3.5 text-xs">
                                      <div
                                        className={`font-semibold ${
                                          dRes.is_correct ? "text-emerald-300" : "text-amber-300"
                                        }`}
                                      >
                                        {dRes.feedback}
                                      </div>

                                      {!dRes.is_correct && dRes.likely_misconception && (
                                        <div className="rounded-lg border border-amber-400/30 bg-amber-500/10 p-3 text-amber-100">
                                          <div className="mb-1 font-mono-code text-[10px] uppercase tracking-wider text-amber-300">
                                            সম্ভাব্য ভুল ধারণা (Likely Misconception
                                            {dRes.confidence ? ` · ~${Math.round(dRes.confidence * 100)}%` : ""})
                                          </div>
                                          <p>{dRes.likely_misconception}</p>
                                        </div>
                                      )}

                                      {!dRes.is_correct && dRes.reteach_explanation && (
                                        <div className="rounded-lg border border-[#00e5ff]/30 bg-[#00e5ff]/[0.07] p-3 text-slate-100">
                                          <div className="mb-1 font-mono-code text-[10px] uppercase tracking-wider text-[#00e5ff]">
                                            সহজ ভাষায় পুনরায় ব্যাখ্যা (Grounded Re-teach ·{" "}
                                            {formatPageLabel(dRes.source, uiLang)})
                                          </div>
                                          <p className="leading-relaxed">{dRes.reteach_explanation}</p>
                                        </div>
                                      )}

                                      <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-white/10 bg-[#08080d]/70 px-3 py-2">
                                        <span className="text-slate-300">
                                          আনুমানিক অনুশীলন দক্ষতা (Estimated Practice Mastery):
                                        </span>
                                        <span className="font-mono-code font-bold text-[#00e5ff]">
                                          {Math.round(dRes.attempt.mastery * 100)}% ({dRes.attempt.correct}/
                                          {dRes.attempt.attempts} · {dRes.attempt.difficulty})
                                        </span>
                                      </div>

                                      {fuQ && (
                                        <div className="space-y-2 border-t border-white/10 pt-3">
                                          <div className="font-mono-code text-[10px] uppercase tracking-wider text-[#00e5ff]">
                                            নতুন অনুশীলন প্রশ্ন (Fresh Practice · Same Objective)
                                          </div>
                                          <div className="text-sm font-medium text-white">{fuQ.question_text}</div>
                                          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                                            {fuQ.options.map((opt) => {
                                              const picked = fuRes?.selected_option === opt.id;
                                              const isRight = fuRes && opt.id === fuRes.correct_option;
                                              let cls =
                                                "border-white/10 bg-[#08080d] text-slate-200 hover:border-[#00e5ff]/50";
                                              if (fuRes) {
                                                if (isRight) {
                                                  cls = "border-emerald-400/60 bg-emerald-500/15 text-emerald-200";
                                                } else if (picked && !fuRes.is_correct) {
                                                  cls = "border-rose-400/60 bg-rose-500/15 text-rose-200";
                                                } else {
                                                  cls = "border-white/5 bg-[#08080d]/40 text-slate-500";
                                                }
                                              }
                                              return (
                                                <button
                                                  key={opt.id}
                                                  type="button"
                                                  disabled={Boolean(fuRes) || Boolean(turn.followUpSubmitting)}
                                                  onClick={() => handleSubmitDiagnostic(turn, fuQ, opt.id, true)}
                                                  className={`rounded-xl border px-3 py-2 text-left text-xs transition ${cls}`}
                                                >
                                                  <span className="mr-2 font-mono-code font-bold text-[#00e5ff]">
                                                    {opt.id}.
                                                  </span>
                                                  {opt.text}
                                                </button>
                                              );
                                            })}
                                          </div>
                                          {fuRes && (
                                            <div className="rounded-lg border border-emerald-400/30 bg-emerald-500/10 p-2.5 text-emerald-100">
                                              <p className="font-medium">{fuRes.feedback}</p>
                                              <p className="mt-1 font-mono-code text-[11px] text-[#00e5ff]">
                                                নতুন আনুমানিক অনুশীলন দক্ষতা:{" "}
                                                {Math.round(fuRes.attempt.mastery * 100)}% ({fuRes.attempt.correct}/
                                                {fuRes.attempt.attempts})
                                              </p>
                                            </div>
                                          )}
                                        </div>
                                      )}
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>

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

                            {turn.englishExplain && (
                              <div className="rounded-xl border border-[#00e5ff]/25 bg-[#00e5ff]/5 p-3 text-xs leading-relaxed text-slate-200">
                                <div className="mb-1 font-mono-code text-[10px] uppercase tracking-wider text-[#00e5ff]">
                                  English Explanation (Same Grounded Context)
                                </div>
                                {turn.englishExplain}
                              </div>
                            )}

                            {/* Action Toolbar */}
                            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-white/10 pt-3 text-xs text-slate-400">
                              <div className="flex flex-wrap items-center gap-2">
                                <button
                                  type="button"
                                  onClick={() => handleSpeech(resp.answer, turn.answerLanguage)}
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
                                  {turn.practiceLoading ? "তৈরি হচ্ছে..." : "📝 অতিরিক্ত প্রশ্ন"}
                                </button>
                                {turn.answerLanguage === "bn" && (
                                  <button
                                    type="button"
                                    onClick={() => handleExplainEnglish(turn)}
                                    disabled={turn.englishLoading || Boolean(turn.englishExplain)}
                                    aria-label="Explain in English"
                                    className="rounded-lg border border-white/10 bg-white/[0.03] px-2.5 py-1 transition hover:border-[#00e5ff]/40 hover:text-[#00e5ff] disabled:opacity-50"
                                  >
                                    {turn.englishLoading ? "Translating..." : "🌐 Explain in English"}
                                  </button>
                                )}
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
                  aria-label="পাঠ্যবইয়ের মাধ্যম নির্বাচন করুন"
                  value={textbookMedium}
                  onChange={(e) => handleMediumChange(e.target.value as "bangla_version" | "english_version")}
                  className="rounded-lg border border-[#00e5ff]/30 bg-[#111827] px-2.5 py-1 text-xs font-medium text-[#00e5ff] focus:border-[#00e5ff] focus:outline-none"
                >
                  <option value="bangla_version">পাঠ্যবই: বাংলা ভার্সন</option>
                  <option value="english_version">Textbook: English Version</option>
                </select>
                <select
                  aria-label="শ্রেণি নির্বাচন করুন"
                  value={classLevel}
                  onChange={(e) => handleClassChange(Number(e.target.value))}
                  className="rounded-lg border border-white/10 bg-[#111827] px-2.5 py-1 text-xs font-medium text-slate-200 focus:border-[#00e5ff] focus:outline-none"
                >
                  {availableClasses.map((c) => (
                    <option key={c} value={c}>
                      {c === 9 ? "শ্রেণি ৯–১০ (SSC)" : `শ্রেণি ${c}`}
                    </option>
                  ))}
                </select>
                <select
                  aria-label="বিষয় নির্বাচন করুন"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  className="rounded-lg border border-white/10 bg-[#111827] px-2.5 py-1 text-xs font-medium text-slate-200 focus:border-[#00e5ff] focus:outline-none"
                >
                  <option value="">{uiLang === "bn" ? "সকল বিষয়" : "All Subjects"}</option>
                  {availableSubjects.map((slug) => (
                    <option key={slug} value={slug}>
                      {subjectName(slug, uiLang)}
                    </option>
                  ))}
                </select>
                <select
                  aria-label="ব্যাখ্যার ভাষা নির্বাচন করুন"
                  value={answerLanguage}
                  onChange={(e) => setAnswerLanguage(e.target.value as "bn" | "en")}
                  className="rounded-lg border border-white/10 bg-[#111827] px-2.5 py-1 text-xs font-medium text-emerald-300 focus:border-[#00e5ff] focus:outline-none"
                >
                  <option value="bn">ব্যাখ্যার ভাষা: বাংলা</option>
                  <option value="en">Answer Lang: English</option>
                </select>
              </div>

              <div className="flex items-end gap-2">
                <textarea
                  id="question-input"
                  rows={2}
                  placeholder={
                    answerLanguage === "en"
                      ? "Ask a question from your selected NCTB textbook... (Press Enter)"
                      : "নির্বাচিত পাঠ্যবই থেকে যেকোনো প্রশ্ন লিখো (বাংলা, English বা Banglish)... Enter চাপো"
                  }
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
                    title="মুখে বলো"
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
              কোনো অ্যাকাউন্ট বা ব্যক্তিগত তথ্য (নাম/ফোন) নেওয়া হয় না · আপলোড ছবি সংরক্ষিত হয় না · এআই শুধু সহায়ক, চূড়ান্ত কর্তৃপক্ষ NCTB পাঠ্যবই
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}
