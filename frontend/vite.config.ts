import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import tailwindcss from '@tailwindcss/vite';
import { SvelteKitPWA } from '@vite-pwa/sveltekit';
import { existsSync } from 'fs';
import { resolve } from 'path';

function requireLegalFiles(): import('vite').Plugin {
	return {
		name: 'require-legal-files',
		buildStart() {
			const privacy = resolve('static/legal/privacy.md');
			if (!existsSync(privacy)) {
				throw new Error(
					'[localez] Missing required file: static/legal/privacy.md\n' +
					'Create this file with your privacy policy before starting the server.'
				);
			}
		}
	};
}

export default defineConfig({
	server: {
		proxy: {
			'/api': { target: process.env.VITE_API_URL ?? 'http://localhost:8000', changeOrigin: true }
		}
	},
	plugins: [
		requireLegalFiles(),
		tailwindcss(),
		sveltekit(),
		SvelteKitPWA({
			registerType: 'autoUpdate',
			manifest: {
				name: 'Localez',
				short_name: 'Localez',
				description: 'Localization management platform',
				theme_color: '#18181b',
				background_color: '#09090b',
				display: 'standalone',
				start_url: '/',
				icons: [
					{ src: '/icons/icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any maskable' }
				]
			},
			workbox: {
				globPatterns: ['**/*.{js,css,html,svg,png,ico,woff2}'],
				navigateFallback: 'index.html',
				navigateFallbackAllowlist: [/^(?!\/(api|auth\/passkey))/]
			},
			devOptions: { enabled: false }
		})
	]
});
