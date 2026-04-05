// src/utils/index.ts
import { clsx, type ClassValue } from "clsx";

export function cn(...inputs: ClassValue[]) { return clsx(inputs); }

export function formatBDT(amount: number): string {
  return "৳" + amount.toLocaleString("en-BD");
}

export function truncate(str: string, maxLen = 80): string {
  return str.length > maxLen ? str.slice(0, maxLen).trimEnd() + "…" : str;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function debounce<T extends (...args: any[]) => void>(fn: T, delay: number) {
  let timer: ReturnType<typeof setTimeout>;
  return (...args: Parameters<T>) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}
