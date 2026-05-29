type Provider = 'llm' | 'deepl' | null;
type Channel = 'stable' | 'preview';

function createConfigStore() {
	let provider = $state<Provider>(null);
	let version = $state<string | null>(null);
	let channel = $state<Channel>('stable');

	async function load(baseUrl: string) {
		try {
			const res = await fetch(`${baseUrl}/api/config`);
			if (res.ok) {
				const data = await res.json();
				provider = data.provider ?? null;
				version = data.version ?? null;
				channel = data.channel ?? 'stable';
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
		get version() {
			return version;
		},
		get channel() {
			return channel;
		},
		load
	};
}

export const configStore = createConfigStore();
