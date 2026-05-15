type PrefillEntry = { running: boolean; message: string };

function createPrefillStore() {
	let state = $state<Record<string, PrefillEntry>>({});

	function key(projectId: string, language: string) {
		return `${projectId}:${language}`;
	}

	return {
		get(projectId: string, language: string): PrefillEntry | undefined {
			return state[key(projectId, language)];
		},
		set(projectId: string, language: string, entry: PrefillEntry) {
			state[key(projectId, language)] = entry;
		},
		clear(projectId: string, language: string) {
			delete state[key(projectId, language)];
		}
	};
}

export const prefillStore = createPrefillStore();
