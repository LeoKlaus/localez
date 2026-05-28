import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

// Re-exported for shadcn-svelte component compatibility
export type WithElementRef<T, U extends HTMLElement = HTMLElement> = T & { ref?: U | null };
export type WithoutChild<T> = T extends { child?: unknown } ? Omit<T, 'child'> : T;
export type WithoutChildren<T> = T extends { children?: unknown } ? Omit<T, 'children'> : T;
export type WithoutChildrenOrChild<T> = WithoutChildren<WithoutChild<T>>;

export function cn(...inputs: ClassValue[]) {
	return twMerge(clsx(inputs));
}

export function formatDate(iso: string): string {
	return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(
		new Date(iso)
	);
}

export function initials(username: string): string {
	return username.slice(0, 2).toUpperCase();
}

// ── Language display ──────────────────────────────────────────────────────────

const _langNames = new Intl.DisplayNames(['en'], { type: 'language' });

/** Resolve a BCP 47 code to its English display name, falling back to the code itself. */
export function languageName(code: string): string {
	try {
		return _langNames.of(code) ?? code;
	} catch {
		return code;
	}
}

/** Common BCP 47 codes offered as datalist suggestions for language inputs. */
export const COMMON_LANGUAGE_CODES: string[] = [
	'af', 'sq', 'am', 'ar', 'hy', 'az', 'eu', 'be', 'bn', 'bs', 'bg',
	'my', 'ca', 'zh', 'zh-Hans', 'zh-Hant', 'hr', 'cs', 'da', 'nl',
	'en', 'en-AU', 'en-CA', 'en-GB', 'en-US', 'et', 'fi',
	'fr', 'fr-CA', 'fr-FR', 'gl', 'ka', 'de', 'el', 'gu', 'he', 'hi',
	'hu', 'is', 'id', 'ga', 'it', 'ja', 'kn', 'kk', 'km', 'ko', 'lo',
	'lv', 'lt', 'mk', 'ms', 'ml', 'mt', 'mr', 'mn', 'ne', 'nb', 'nn',
	'or', 'ps', 'fa', 'pl', 'pt', 'pt-BR', 'pt-PT', 'pa', 'ro', 'ru',
	'sr', 'si', 'sk', 'sl', 'es', 'es-419', 'es-MX', 'es-ES', 'sw', 'sv',
	'ta', 'te', 'th', 'tr', 'tk', 'uk', 'ur', 'uz', 'vi', 'cy', 'yo', 'zu'
];
