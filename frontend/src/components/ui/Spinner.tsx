import { LoaderCircle } from "lucide-react";

import { cn } from "@/lib/cn";

export default function Spinner({ size = 16, className }: { size?: number; className?: string }) {
  return <LoaderCircle size={size} aria-hidden className={cn("shrink-0 animate-spin", className)} />;
}
