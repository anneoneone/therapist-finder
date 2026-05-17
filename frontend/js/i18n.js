/**
 * Lightweight i18n runtime.
 *
 * Translation files live in `frontend/js/i18n/<lang>.json` and are
 * pre-translated at build time by `scripts/translate_ui.py` (DeepL).
 * English is the source language.
 *
 * Usage:
 *   - In HTML: `<button data-i18n="step1.loadBtn"></button>`
 *     Variants: `data-i18n-placeholder`, `data-i18n-title`,
 *               `data-i18n-aria-label`, `data-i18n-html` (allows markup).
 *   - In JS: `t('step1.statusParsedPlural', { total: 12, withEmail: 8 })`.
 */

const STORAGE_KEY = 'therapist-finder:lang';
const DEFAULT_LANG = 'en';

export const SUPPORTED_LANGS = [
    { code: 'de', name: 'German', nativeName: 'Deutsch', dir: 'ltr' },
    { code: 'en', name: 'English', nativeName: 'English', dir: 'ltr' },
    { code: 'fr', name: 'French', nativeName: 'Français', dir: 'ltr' },
    { code: 'ar', name: 'Arabic', nativeName: 'العربية', dir: 'rtl' },
    { code: 'tr', name: 'Turkish', nativeName: 'Türkçe', dir: 'ltr' },
    { code: 'es', name: 'Spanish', nativeName: 'Español', dir: 'ltr' },
    { code: 'it', name: 'Italian', nativeName: 'Italiano', dir: 'ltr' },
    { code: 'ru', name: 'Russian', nativeName: 'Русский', dir: 'ltr' },
];

const SUPPORTED_CODES = new Set(SUPPORTED_LANGS.map((l) => l.code));

let currentLang = DEFAULT_LANG;
let currentDict = {};
const listeners = new Set();

function pickInitialLang() {
    try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored && SUPPORTED_CODES.has(stored)) return stored;
    } catch {
        /* ignore */
    }
    const nav = (navigator.language || '').toLowerCase().split('-')[0];
    if (SUPPORTED_CODES.has(nav)) return nav;
    return DEFAULT_LANG;
}

async function loadDict(lang) {
    const url = new URL(`./i18n/${lang}.json`, import.meta.url);
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Failed to load ${lang}.json (HTTP ${res.status})`);
    return res.json();
}

function interpolate(template, vars) {
    if (!vars) return template;
    return template.replace(/\{(\w+)\}/g, (match, key) =>
        Object.prototype.hasOwnProperty.call(vars, key) ? String(vars[key]) : match
    );
}

export function t(key, vars) {
    const value = currentDict[key];
    if (typeof value !== 'string') return key;
    return interpolate(value, vars);
}

export function currentLanguage() {
    return currentLang;
}

export function onLanguageChange(fn) {
    listeners.add(fn);
    return () => listeners.delete(fn);
}

function applyToDom() {
    const meta = currentDict._meta || {};
    const dir = meta.dir === 'rtl' ? 'rtl' : 'ltr';
    document.documentElement.lang = currentLang;
    document.documentElement.dir = dir;
    document.body?.classList.toggle('rtl', dir === 'rtl');

    document.querySelectorAll('[data-i18n]').forEach((el) => {
        const key = el.getAttribute('data-i18n');
        el.textContent = t(key);
    });
    document.querySelectorAll('[data-i18n-html]').forEach((el) => {
        const key = el.getAttribute('data-i18n-html');
        el.innerHTML = t(key);
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
        const key = el.getAttribute('data-i18n-placeholder');
        el.setAttribute('placeholder', t(key));
    });
    document.querySelectorAll('[data-i18n-title]').forEach((el) => {
        const key = el.getAttribute('data-i18n-title');
        el.setAttribute('title', t(key));
    });
    document.querySelectorAll('[data-i18n-aria-label]').forEach((el) => {
        const key = el.getAttribute('data-i18n-aria-label');
        el.setAttribute('aria-label', t(key));
    });

    if (currentDict['app.title']) document.title = t('app.title');
}

export async function setLanguage(lang) {
    const target = SUPPORTED_CODES.has(lang) ? lang : DEFAULT_LANG;
    try {
        currentDict = await loadDict(target);
        currentLang = target;
        try {
            localStorage.setItem(STORAGE_KEY, target);
        } catch {
            /* ignore */
        }
        applyToDom();
        listeners.forEach((fn) => {
            try {
                fn(target);
            } catch (e) {
                console.error('Language listener failed:', e);
            }
        });
    } catch (error) {
        console.error('Failed to set language:', error);
        if (target !== DEFAULT_LANG) await setLanguage(DEFAULT_LANG);
    }
}

export async function initI18n() {
    await setLanguage(pickInitialLang());
}
