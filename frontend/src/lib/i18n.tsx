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
  backToDocuments: "Back to documents",
  page: "Page",
  ofPages: "of",
  previousPage: "Previous",
  nextPage: "Next",
  jumpToPage: "Go to page",
  processingInProgress: "Still processing — this page isn't ready yet.",
  notProcessedYet: "This document hasn't been processed yet.",
  documentFailed: "Processing failed",
  noPagesYet: "No pages processed yet.",
  extractedText: "Text found on this page",
  extractedTables: "Tables found on this page",
  noTextOnPage: "No text was extracted from this page.",
  noTablesOnPage: "No tables were found on this page.",
  ocrUsedLabel: "Read with OCR",
  textLayerLabel: "Native text",
  ocrConfidence: "OCR confidence",
  factsComingSoon: "Pulling out verified numbers from this page isn't built yet — for now, here's the raw text and tables the system found.",
  noPageImage: "No preview available for this file type.",
  sourceLabel: "Source",
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
  "doc.annual_report": "वार्षिक रिपोर्ट",
  "doc.coal_inventory": "कोयला भंडार सूची",
  "doc.monthly_stats": "मासिक आँकड़े",
  "doc.pq_answer": "संसदीय प्रश्न का उत्तर",
  "doc.other": "अन्य",
  "lang.en": "अंग्रेज़ी",
  "lang.hi": "हिंदी",
  "lang.mixed": "हिंदी + अंग्रेज़ी",
  backToDocuments: "दस्तावेज़ों पर वापस जाएं",
  page: "पृष्ठ",
  previousPage: "पिछला",
  nextPage: "अगला",
  processingInProgress: "अभी भी प्रोसेस हो रहा है — यह पृष्ठ अभी तैयार नहीं है।",
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
