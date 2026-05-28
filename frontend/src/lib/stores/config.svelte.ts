type Provider = 'llm' | 'deepl' | null;

function createConfigStore() {
	let provider = $state<Provider>(null);

	async function load(baseUrl: string) {
		try {
			const res = await fetch(`${baseUrl}/api/config`);
			if (res.ok) {
				const data = await res.json();
				provider = data.provider ?? null;
			}
		} catch {
			// Network error — leave defaults (features hidden)
		}
	}

	return {
		get provider() {
			return provider;
		},
		get aiEnabled() {
			return provider !== null;
		},
		/** Human-readable label for the active provider: "DeepL" or "AI" */
		get providerLabel() {
			return provider === 'deepl' ? 'DeepL' : 'AI';
		},
		load
	};
}

export const configStore = createConfigStore();
