import { describe, expect, it } from 'vitest';
import { formatDate, initials, languageName, COMMON_LANGUAGE_CODES } from './utils';

describe('initials', () => {
	it('returns first two characters uppercased', () => {
		expect(initials('alice')).toBe('AL');
	});

	it('handles short usernames', () => {
		expect(initials('a')).toBe('A');
	});
});

describe('formatDate', () => {
	it('formats a valid ISO timestamp', () => {
		const formatted = formatDate('2024-06-15T14:30:00.000Z');
		expect(formatted).toMatch(/2024/);
		expect(formatted.length).toBeGreaterThan(0);
	});
});

describe('languageName', () => {
	it('resolves common language codes to English names', () => {
		expect(languageName('en')).toBe('English');
		expect(languageName('de')).toBe('German');
		expect(languageName('fr')).toBe('French');
		expect(languageName('es')).toBe('Spanish');
		expect(languageName('ja')).toBe('Japanese');
		expect(languageName('zh')).toBe('Chinese');
		expect(languageName('ar')).toBe('Arabic');
		expect(languageName('pt')).toBe('Portuguese');
		expect(languageName('ru')).toBe('Russian');
		expect(languageName('ko')).toBe('Korean');
	});

	it('resolves regional variants', () => {
		// Regional variants must mention the base language — the exact format
		// ("X (Y)", "X, Y", "British X", etc.) is ICU-data-dependent so we
		// check only for the language name.
		expect(languageName('pt-BR')).toMatch(/Portuguese/i);
		expect(languageName('en-GB')).toMatch(/English/i);
		expect(languageName('fr-CA')).toMatch(/French/i);
		expect(languageName('zh-Hans')).toMatch(/Chinese/i);
		expect(languageName('zh-Hant')).toMatch(/Chinese/i);
		// Regional variants must resolve to something different from the bare base code.
		expect(languageName('pt-BR')).not.toBe(languageName('pt-PT'));
		expect(languageName('en-GB')).not.toBe(languageName('en-US'));
	});

	it('returns a non-empty string for unrecognised but structurally valid tags', () => {
		// Intl.DisplayNames formats unknown-but-valid tags rather than throwing;
		// the function should still return a non-empty, non-null string.
		const result = languageName('xyz-UNKNOWN');
		expect(typeof result).toBe('string');
		expect(result.length).toBeGreaterThan(0);
	});

	it('falls back to the raw code when Intl throws (structurally invalid input)', () => {
		// Structurally invalid BCP 47 — Intl.DisplayNames.of() throws a RangeError.
		expect(languageName('!@#invalid')).toBe('!@#invalid');
	});

	it('returns a non-empty string for every code in COMMON_LANGUAGE_CODES', () => {
		for (const code of COMMON_LANGUAGE_CODES) {
			const name = languageName(code);
			expect(name.length, `languageName('${code}') should be non-empty`).toBeGreaterThan(0);
		}
	});

	it('never returns undefined or null', () => {
		expect(languageName('en')).toBeTruthy();
		expect(languageName('zz-invalid')).toBeTruthy();
	});
});

describe('COMMON_LANGUAGE_CODES', () => {
	it('is a non-empty array of strings', () => {
		expect(Array.isArray(COMMON_LANGUAGE_CODES)).toBe(true);
		expect(COMMON_LANGUAGE_CODES.length).toBeGreaterThan(0);
		for (const code of COMMON_LANGUAGE_CODES) {
			expect(typeof code).toBe('string');
			expect(code.length).toBeGreaterThan(0);
		}
	});

	it('contains the most widely-used language codes', () => {
		const must = ['en', 'de', 'fr', 'es', 'ja', 'zh', 'ar', 'pt', 'ru', 'ko'];
		for (const code of must) {
			expect(COMMON_LANGUAGE_CODES, `should include '${code}'`).toContain(code);
		}
	});

	it('contains useful regional variants', () => {
		expect(COMMON_LANGUAGE_CODES).toContain('pt-BR');
		expect(COMMON_LANGUAGE_CODES).toContain('zh-Hans');
		expect(COMMON_LANGUAGE_CODES).toContain('zh-Hant');
		expect(COMMON_LANGUAGE_CODES).toContain('en-GB');
	});

	it('has no duplicate codes', () => {
		const unique = new Set(COMMON_LANGUAGE_CODES);
		expect(unique.size).toBe(COMMON_LANGUAGE_CODES.length);
	});

	it('every code is resolvable without throwing', () => {
		expect(() => {
			for (const code of COMMON_LANGUAGE_CODES) {
				languageName(code);
			}
		}).not.toThrow();
	});
});
