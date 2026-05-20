function createLegalStore() {
	let hasImprint = $state(false);
	let hasPrivacy = $state(false);
	let hasContributions = $state(false);

	async function fileExists(url: string): Promise<boolean> {
		const res = await fetch(url, { method: 'HEAD' });
		if (!res.ok) return false;
		const ct = res.headers.get('content-type') ?? '';
		return !ct.includes('text/html');
	}

	async function init() {
		[hasImprint, hasPrivacy, hasContributions] = await Promise.all([
			fileExists('/legal/imprint.md'),
			fileExists('/legal/privacy.md'),
			fileExists('/legal/contributions.md')
		]);
	}

	return {
		get hasImprint() { return hasImprint; },
		get hasPrivacy() { return hasPrivacy; },
		get hasContributions() { return hasContributions; },
		init
	};
}

export const legalStore = createLegalStore();
