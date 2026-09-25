"use client";

import { useEffect } from "react";

import { useT } from "@/lib/i18n";

/**
 * Keeps <html lang> in step with the chosen language.
 *
 * The root layout is a server component and can only ever render one value, so a
 * reader switching to Hindi was left with lang="en" and a screen reader saying
 * Devanagari in an English voice.
 */
export default function HtmlLang() {
  const { lang } = useT();
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);
  return null;
}
