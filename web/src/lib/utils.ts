import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * 合并 Tailwind className。
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
