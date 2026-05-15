function createLegalStore() {
	let hasImprint = $state(false);
	let hasPrivacy = $state(false);

	async function fileExists(url: string): Promise<boolean> {
		const res = await fetch(url, { method: 'HEAD' });
		if (!res.ok) return false;
		const ct = res.headers.get('content-type') ?? '';
		return !ct.includes('text/html');
	}

	async function init() {
		[hasImprint, hasPrivacy] = await Promise.all([
			fileExists('/legal/imprint.md'),
			fileExists('/legal/privacy.md')
		]);
	}

	return {
		get hasImprint() { return hasImprint; },
		get hasPrivacy() { return hasPrivacy; },
		init
	};
}

export const legalStore = createLegalStore();
