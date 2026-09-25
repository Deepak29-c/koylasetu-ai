"use client";

// Minimal English / Hindi labels. Add every new UI string here, never inline.
// Hindi strings are a first draft: have a native speaker check them before the demo.

import { useSyncExternalStore } from "react";

const en = {
  appName: "KoylaSetu AI",
  tagline: "Verified AI Reporting & Parliamentary-Reply Assistant for CMPDI / CIL",
  signIn: "Sign in",
  signingIn: "Signing in…",
  email: "Email",
  password: "Password",
  logout: "Log out",
  home: "Home",
  upload: "Upload",
  documents: "Documents",
  welcome: "Welcome",
  yourRoles: "Your roles",
  yourUnit: "Your unit",
  uploadTitle: "Upload documents",
  uploadHelp: "PDF, Excel (XLSX/XLS/CSV), images (PNG/JPG/TIFF) or Word (DOCX). Up to 100 MB each.",
  dropHere: "Drag files here, or click to choose",
  filesChosen: "files chosen",
  docType: "Document type",
  fy: "Financial year (e.g. FY 2023-24)",
  language: "Language",
  markPublic: "Shared public document (visible to all units)",
  sourceUrl: "Source URL (optional)",
  uploadButton: "Upload",
  uploading: "Uploading…",
  created: "Uploaded",
  duplicate: "Already uploaded",
  rejected: "Rejected",
  notQueued: "Saved, but the processing queue is offline. Use Retry later.",
  noPermission: "Your role does not allow this.",
  title: "Title",
  type: "Type",
  status: "Status",
  pages: "Pages",
  uploadedOn: "Uploaded",
  retry: "Retry",
  noDocuments: "No documents yet.",
  loading: "Loading…",
  ask: "Ask",
  askTitle: "Ask a question",
  askHelp:
    "Answers come only from uploaded documents. Every figure links to its source page; numbers not found in the sources are marked red.",
  askPlaceholder: "e.g. What steps were taken to meet the coal shortage at power plants?",
  askButton: "Ask",
  thinking: "Searching documents and writing the answer…",
  sources: "Sources",
  openPage: "Open page",
  "conf.high": "Grounded: every figure is in the sources",
  "conf.medium": "Check the sources",
  "conf.low": "Needs verification: a figure is not in the sources",
  unmatched: "Not found in sources",
  helpful: "Helpful",
  notHelpful: "Not helpful",
  thanks: "Thanks for the feedback",
  page: "Page",
  of: "of",
  prev: "Previous",
  next: "Next",
  ocrPage: "Scanned page (OCR)",
  ocrConfidence: "OCR confidence",
  pageText: "Text on this page",
  tablesOnPage: "Tables on this page",
  open: "Open",
  review: "Review",
  reviewTitle: "Review queue",
  reviewHelp:
    "Figures the system is not sure about. Check each against the highlighted source cell, then accept, correct or reject it. Every decision is logged.",
  totalFacts: "Figures extracted",
  autoVerified: "Accepted automatically",
  flaggedFacts: "Waiting for review",
  automation: "Automation",
  nothingToReview: "Nothing to review. All extracted figures are verified.",
  selectItem: "Select a figure on the left.",
  value: "Value",
  asPrinted: "As printed",
  standard: "Standard",
  metric: "Metric",
  who: "Company / state",
  category: "Category",
  period: "Period",
  confidence: "Confidence",
  why: "Why it was flagged",
  otherSource: "Other source",
  accept: "Accept",
  edit: "Correct value",
  reject: "Reject",
  correctValue: "Correct value",
  comment: "Comment",
  commentRequired: "A comment is required to correct or reject.",
  saving: "Saving…",
  "sev.high": "High",
  "sev.medium": "Medium",
  "sev.low": "Low",
  "doc.annual_report": "Annual report",
  "doc.coal_inventory": "Coal inventory",
  "doc.monthly_stats": "Monthly statistics",
  "doc.pq_answer": "Parliamentary question answer",
  "doc.other": "Other",
  "lang.en": "English",
  "lang.hi": "Hindi",
  "lang.mixed": "Hindi + English",
  "status.UPLOADED": "Uploaded",
  "status.PROCESSING": "Processing",
  "status.PROCESSED": "Done",
  "status.NEEDS_REVIEW": "Needs review",
  "status.FAILED": "Failed",
};

export type LabelKey = keyof typeof en;

const hi: Partial<Record<LabelKey, string>> = {
  appName: "कोयलासेतु AI",
  signIn: "लॉग इन करें",
  signingIn: "लॉग इन हो रहा है…",
  email: "ईमेल",
  password: "पासवर्ड",
  logout: "लॉग आउट",
  home: "मुख्य पृष्ठ",
  upload: "अपलोड",
  documents: "दस्तावेज़",
  welcome: "स्वागत है",
  yourRoles: "आपकी भूमिकाएँ",
  yourUnit: "आपकी इकाई",
  uploadTitle: "दस्तावेज़ अपलोड करें",
  dropHere: "फ़ाइलें यहाँ खींचें, या चुनने के लिए क्लिक करें",
  docType: "दस्तावेज़ का प्रकार",
  fy: "वित्तीय वर्ष (जैसे FY 2023-24)",
  language: "भाषा",
  uploadButton: "अपलोड करें",
  uploading: "अपलोड हो रहा है…",
  title: "शीर्षक",
  type: "प्रकार",
  status: "स्थिति",
  pages: "पृष्ठ",
  retry: "फिर से प्रयास करें",
  loading: "लोड हो रहा है…",
  ask: "प्रश्न पूछें",
  review: "समीक्षा",
  reviewTitle: "समीक्षा सूची",
  accept: "स्वीकार करें",
  reject: "अस्वीकार करें",
  comment: "टिप्पणी",
  askTitle: "प्रश्न पूछें",
  askButton: "पूछें",
  sources: "स्रोत",
  openPage: "पृष्ठ खोलें",
  page: "पृष्ठ",
  prev: "पिछला",
  next: "अगला",
  "doc.annual_report": "वार्षिक रिपोर्ट",
  "doc.coal_inventory": "कोयला भंडार सूची",
  "doc.monthly_stats": "मासिक आँकड़े",
  "doc.pq_answer": "संसदीय प्रश्न का उत्तर",
  "doc.other": "अन्य",
  "lang.en": "अंग्रेज़ी",
  "lang.hi": "हिंदी",
  "lang.mixed": "हिंदी + अंग्रेज़ी",
};

export type Lang = "en" | "hi";
const KEY = "ks_lang";
const EVENT = "ks-lang-change";

function subscribe(cb: () => void) {
  window.addEventListener(EVENT, cb);
  window.addEventListener("storage", cb);
  return () => {
    window.removeEventListener(EVENT, cb);
    window.removeEventListener("storage", cb);
  };
}

function getLang(): Lang {
  try {
    return localStorage.getItem(KEY) === "hi" ? "hi" : "en";
  } catch {
    return "en";
  }
}

export function setLang(lang: Lang) {
  try {
    localStorage.setItem(KEY, lang);
  } catch {}
  window.dispatchEvent(new Event(EVENT));
}

export function useT() {
  const lang = useSyncExternalStore(subscribe, getLang, () => "en" as Lang);
  const t = (key: LabelKey): string => (lang === "hi" && hi[key]) || en[key];
  return { t, lang };
}
