import { describe, expect, it } from 'vitest';
import {
	extractPlaceholders,
	parseSegments,
	placeholderLabel
} from './placeholders';

describe('parseSegments', () => {
	it('splits plain text', () => {
		expect(parseSegments('Hello')).toEqual([{ type: 'text', value: 'Hello' }]);
	});

	it('splits text around a single placeholder', () => {
		expect(parseSegments('Hello %@')).toEqual([
			{ type: 'text', value: 'Hello ' },
			{ type: 'placeholder', value: '%@' }
		]);
	});

	it('handles positional placeholders', () => {
		expect(parseSegments('%1$@ items, %2$lld left')).toEqual([
			{ type: 'placeholder', value: '%1$@' },
			{ type: 'text', value: ' items, ' },
			{ type: 'placeholder', value: '%2$lld' },
			{ type: 'text', value: ' left' }
		]);
	});

	it('handles long integer placeholder', () => {
		expect(parseSegments('count: %lld')).toEqual([
			{ type: 'text', value: 'count: ' },
			{ type: 'placeholder', value: '%lld' }
		]);
	});
});

describe('extractPlaceholders', () => {
	it('returns unique placeholders in order of first appearance', () => {
		expect(extractPlaceholders('%@ and %lld and %@')).toEqual(['%@', '%lld']);
	});

	it('returns empty array when none present', () => {
		expect(extractPlaceholders('no placeholders')).toEqual([]);
	});

	it('extracts mixed placeholder types', () => {
		expect(extractPlaceholders('%1$@ %f %s %lld')).toEqual(['%1$@', '%f', '%s', '%lld']);
	});
});

describe('placeholderLabel', () => {
	it('labels string placeholders', () => {
		expect(placeholderLabel('%@')).toBe('string');
		expect(placeholderLabel('%1$@')).toBe('string');
		expect(placeholderLabel('%s')).toBe('string');
	});

	it('labels decimal placeholders', () => {
		expect(placeholderLabel('%f')).toBe('decimal');
		expect(placeholderLabel('%1$f')).toBe('decimal');
	});

	it('labels integer placeholders', () => {
		expect(placeholderLabel('%d')).toBe('number');
		expect(placeholderLabel('%lld')).toBe('number');
		expect(placeholderLabel('%ld')).toBe('number');
		expect(placeholderLabel('%2$d')).toBe('number');
	});
});
