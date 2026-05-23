/** iOS-style format placeholders: %@, %d, %1$@, %lld, etc. */
export const PLACEHOLDER_RE = /%(?:\d+\$)?(?:@|lld|ld|d|f|s)/;

export type PlaceholderSegment = { type: 'text' | 'placeholder'; value: string };

export function parseSegments(text: string): PlaceholderSegment[] {
	const parts = text.split(new RegExp(`(${PLACEHOLDER_RE.source})`));
	return parts
		.map((value, i) => ({
			type: (i % 2 === 1 ? 'placeholder' : 'text') as PlaceholderSegment['type'],
			value
		}))
		.filter((s) => s.value !== '');
}

export function extractPlaceholders(text: string): string[] {
	return [...new Set(text.match(new RegExp(PLACEHOLDER_RE.source, 'g')) ?? [])];
}

export function placeholderLabel(ph: string): string {
	if (ph.endsWith('@') || ph.endsWith('s')) return 'string';
	if (ph.endsWith('f')) return 'decimal';
	return 'number';
}
