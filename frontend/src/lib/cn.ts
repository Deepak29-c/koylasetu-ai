import { type ClassValue, clsx } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

// The app's own radius and shadow tokens (globals.css @theme), so a later
// `rounded-card` replaces an earlier `rounded-control` instead of both being kept.
const twMerge = extendTailwindMerge({
  extend: {
    theme: {
      radius: ["control", "card", "panel"],
      shadow: ["card", "pill", "pop", "float"],
    },
  },
});

/** Join class names; later Tailwind utilities win over earlier conflicting ones. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
