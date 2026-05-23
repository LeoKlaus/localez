import { describe, expect, it } from 'vitest';
import { parseRecoveryWords } from './recovery-words';

describe('parseRecoveryWords', () => {
	it('splits on whitespace', () => {
		expect(parseRecoveryWords('one two three')).toEqual(['one', 'two', 'three']);
	});

	it('trims leading and trailing whitespace', () => {
		expect(parseRecoveryWords('  one two  ')).toEqual(['one', 'two']);
	});

	it('collapses multiple spaces and newlines', () => {
		expect(parseRecoveryWords('one  two\nthree\tfour')).toEqual(['one', 'two', 'three', 'four']);
	});

	it('filters empty tokens', () => {
		expect(parseRecoveryWords('one   two')).toEqual(['one', 'two']);
	});
});
