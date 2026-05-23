/** Normalize whitespace-separated recovery words from user input. */
export function parseRecoveryWords(raw: string): string[] {
	return raw
		.trim()
		.split(/\s+/)
		.filter((w) => w.length > 0);
}
