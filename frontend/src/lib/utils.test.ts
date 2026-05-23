import { describe, expect, it } from 'vitest';
import { formatDate, initials } from './utils';

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
