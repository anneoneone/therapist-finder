/**
 * Therapist Finder - Multi-step hash-routed flow.
 * @module app
 */

import {
    APIError,
    downloadFile,
    generateEmails,
    getTemplate,
    parseFile,
    parseUrl,
} from './api.js';

// ============================================
// Constants
// ============================================

const STATE_STORAGE_KEY = 'therapist-finder:state';
const CONTACTED_STORAGE_KEY = 'therapist-finder:contacted-emails';
const MAILTO_MAX_LENGTH = 1900;
const TRUNCATION_MARKER = '\n\n[… truncated — use "Copy body" to paste full text]';

const STEPS = ['url', 'overview', 'me', 'template', 'send'];

// ============================================
// State (persisted to sessionStorage, except `file`)
// ============================================

const defaultState = () => ({
    pdfUrl: '',
    therapists: [],
    userInfo: {},
    templateBody: '',
    results: null,
    queue: { items: [], index: 0 },
});

const state = (() => {
    try {
        const raw = sessionStorage.getItem(STATE_STORAGE_KEY);
        if (!raw) return defaultState();
        return { ...defaultState(), ...JSON.parse(raw) };
    } catch {
        return defaultState();
    }
})();

// `file` is not persistable across refresh; keep it in memory only.
let selectedFile = null;

function persistState() {
    try {
        sessionStorage.setItem(STATE_STORAGE_KEY, JSON.stringify(state));
    } catch (error) {
        console.warn('Failed to persist state:', error);
    }
}

// ============================================
// DOM Elements
// ============================================

const $ = (id) => document.getElementById(id);

const elements = {
    // Step 1
    viewUrl: $('view-url'),
    searchSection: $('search-section'),
    searchForm: $('search-form'),
    searchBtn: $('search-btn'),
    searchStatus: $('search-status'),
    searchPdfUrl: $('search-pdf-url'),
    toggleUpload: $('toggle-upload'),
    toggleSearch: $('toggle-search'),
    uploadSection: $('upload-section'),
    dropzone: $('dropzone'),
    fileInput: $('file-input'),
    selectedFile: $('selected-file'),
    fileName: $('file-name'),
    removeFile: $('remove-file'),
    uploadBtn: $('upload-btn'),
    uploadStatus: $('upload-status'),

    // Step 2
    viewOverview: $('view-overview'),
    resultsSummary: $('results-summary'),
    therapistsTbody: $('therapists-tbody'),
    downloadTable: $('download-table'),

    // Step 3
    viewMe: $('view-me'),
    userinfoForm: $('userinfo-form'),
    generateStatus: $('generate-status'),

    // Step 4
    viewTemplate: $('view-template'),
    templateForm: $('template-form'),
    templateBody: $('template-body'),
    templateContinue: $('template-continue'),
    templateStatus: $('template-status'),
    templatePreviewTarget: $('template-preview-target'),
    templatePreviewBody: $('template-preview-body'),

    // Step 5
    viewSend: $('view-send'),
    queuePosition: $('queue-position'),
    queueTotal: $('queue-total'),
    queueTherapist: $('queue-therapist'),
    queueSubject: $('queue-subject'),
    queueBodyPreview: $('queue-body-preview'),
    queueTruncationWarning: $('queue-truncation-warning'),
    queueStatus: $('queue-status'),
    queueCopyBody: $('queue-copy-body'),
    queueSkip: $('queue-skip'),
    queueOpen: $('queue-open'),
    queueNext: $('queue-next'),

    // Stepper
    stepperItems: document.querySelectorAll('.stepper-item'),
    views: document.querySelectorAll('.view'),
};

// ============================================
// Utility Functions
// ============================================

function showStatus(element, message, type = 'info') {
    if (!element) return;
    element.textContent = message;
    element.className = `status ${type}`;
    element.hidden = false;
}

function hideStatus(element) {
    if (element) element.hidden = true;
}

function setButtonLoading(button, loading) {
    if (!button) return;
    const text = button.querySelector('.btn-text');
    const loader = button.querySelector('.btn-loader');
    button.disabled = loading;
    if (text) text.hidden = loading;
    if (loader) loader.hidden = !loading;
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================
// Router
// ============================================

/**
 * Return the earliest step whose prerequisites are unmet, given current state.
 * Used both to guard direct deep-links and to compute stepper "completed" state.
 */
function firstUnsatisfiedStep() {
    if (state.therapists.length === 0) return 'url';
    if (!state.userInfo.first_name) return 'me';
    if (!state.templateBody) return 'template';
    if (!state.results || !state.results.drafts) return 'template';
    return null; // all satisfied
}

function canEnterStep(step) {
    switch (step) {
        case 'url':
            return true;
        case 'overview':
        case 'me':
            return state.therapists.length > 0;
        case 'template':
            return state.therapists.length > 0 && !!state.userInfo.first_name;
        case 'send':
            return !!(state.results && state.results.drafts && state.results.drafts.length);
        default:
            return false;
    }
}

function currentStep() {
    const hash = window.location.hash.replace(/^#\//, '');
    return STEPS.includes(hash) ? hash : 'url';
}

function navigate(step) {
    const target = STEPS.includes(step) ? step : 'url';
    if (window.location.hash !== `#/${target}`) {
        window.location.hash = `#/${target}`;
    } else {
        renderRoute();
    }
}

function renderRoute() {
    let step = currentStep();
    if (!canEnterStep(step)) {
        step = firstUnsatisfiedStep() || 'url';
        if (window.location.hash !== `#/${step}`) {
            window.location.hash = `#/${step}`;
            return; // hashchange will re-trigger renderRoute
        }
    }

    elements.views.forEach((view) => {
        view.classList.toggle('active', view.id === `view-${step}`);
    });

    const stepIndex = STEPS.indexOf(step);
    elements.stepperItems.forEach((item) => {
        const itemStep = item.dataset.step;
        const itemIndex = STEPS.indexOf(itemStep);
        item.classList.toggle('active', itemStep === step);
        item.classList.toggle('completed', itemIndex < stepIndex && canEnterStep(itemStep));
        item.classList.toggle('disabled', !canEnterStep(itemStep));
    });

    onEnterStep(step);
}

function onEnterStep(step) {
    switch (step) {
        case 'url':
            if (state.pdfUrl) elements.searchPdfUrl.value = state.pdfUrl;
            break;
        case 'overview':
            renderTherapists();
            break;
        case 'me':
            hydrateUserInfoForm();
            break;
        case 'template':
            initTemplateView();
            break;
        case 'send':
            initSendView();
            break;
    }
}

// ============================================
// Step 1: PDF URL + upload fallback
// ============================================

function setEntrySection(target) {
    const showSearch = target === 'search';
    elements.searchSection.hidden = !showSearch;
    elements.uploadSection.hidden = showSearch;
}

async function handlePdfUrlSubmit(event) {
    event.preventDefault();
    const url = elements.searchPdfUrl.value.trim();
    if (!url) return;

    setButtonLoading(elements.searchBtn, true);
    showStatus(elements.searchStatus, 'Fetching and parsing PDF…', 'info');

    try {
        const result = await parseUrl(url);
        state.pdfUrl = url;
        state.therapists = result.therapists || [];
        state.results = null;
        persistState();

        const total = state.therapists.length;
        const withEmail = state.therapists.filter((t) => t.email).length;
        showStatus(
            elements.searchStatus,
            `✓ ${total} therapist${total === 1 ? '' : 's'} parsed `
                + `(${withEmail} with email)`,
            'success'
        );

        navigate('overview');
    } catch (error) {
        console.error('Parse URL error:', error);
        showStatus(
            elements.searchStatus,
            error instanceof APIError
                ? error.message
                : 'Failed to load PDF. Please check the URL and try again.',
            'error'
        );
    } finally {
        setButtonLoading(elements.searchBtn, false);
    }
}

function handleFileSelect(file) {
    if (!file) return;
    const validTypes = ['application/pdf', 'text/plain'];
    const validExtensions = ['.pdf', '.txt'];
    const hasValidType = validTypes.includes(file.type);
    const hasValidExtension = validExtensions.some((ext) =>
        file.name.toLowerCase().endsWith(ext)
    );

    if (!hasValidType && !hasValidExtension) {
        showStatus(elements.uploadStatus, 'Please select a PDF or text file', 'error');
        return;
    }

    selectedFile = file;
    elements.fileName.textContent = file.name;
    elements.selectedFile.hidden = false;
    elements.dropzone.querySelector('.dropzone-content').hidden = true;
    elements.uploadBtn.disabled = false;
    hideStatus(elements.uploadStatus);
}

function handleFileRemove() {
    selectedFile = null;
    elements.fileInput.value = '';
    elements.selectedFile.hidden = true;
    elements.dropzone.querySelector('.dropzone-content').hidden = false;
    elements.uploadBtn.disabled = true;
    hideStatus(elements.uploadStatus);
}

async function handleUpload() {
    if (!selectedFile) return;

    setButtonLoading(elements.uploadBtn, true);
    showStatus(elements.uploadStatus, 'Parsing file...', 'info');

    try {
        const result = await parseFile(selectedFile);
        state.therapists = result.therapists || result;
        state.pdfUrl = '';
        state.results = null;
        persistState();

        const total = state.therapists.length;
        const withEmail = state.therapists.filter((t) => t.email).length;
        showStatus(
            elements.uploadStatus,
            `✓ ${withEmail} contactable therapist${withEmail === 1 ? '' : 's'} `
                + `(of ${total} parsed)`,
            'success'
        );

        navigate('overview');
    } catch (error) {
        console.error('Upload error:', error);
        showStatus(
            elements.uploadStatus,
            error instanceof APIError
                ? error.message
                : 'Failed to parse file. Please try again.',
            'error'
        );
    } finally {
        setButtonLoading(elements.uploadBtn, false);
    }
}

// ============================================
// Step 2: Overview
// ============================================

function renderTherapists() {
    const { therapists } = state;
    const contactable = therapists.filter((t) => !!t.email).length;

    elements.resultsSummary.innerHTML = `
        <div class="summary-item">
            <div class="summary-value">${therapists.length}</div>
            <div class="summary-label">Total Therapists</div>
        </div>
        <div class="summary-item">
            <div class="summary-value">${contactable}</div>
            <div class="summary-label">Contactable (have email)</div>
        </div>
    `;

    elements.therapistsTbody.innerHTML = therapists
        .map((therapist) => {
            const hasEmail = !!therapist.email;
            const statusClass = hasEmail ? 'ready' : 'no-email';
            const statusText = hasEmail ? 'Ready' : 'No Email';
            const specialty = therapist.specialty_label || therapist.specialty || '';
            return `
                <tr>
                    <td>${escapeHtml(therapist.name)}</td>
                    <td>${escapeHtml(specialty) || '<span class="text-muted">—</span>'}</td>
                    <td>${escapeHtml(therapist.email) || '<span class="text-muted">—</span>'}</td>
                    <td>${escapeHtml(therapist.phone) || '<span class="text-muted">—</span>'}</td>
                    <td>${escapeHtml(therapist.address) || '<span class="text-muted">—</span>'}</td>
                    <td><span class="status-badge ${statusClass}">${statusText}</span></td>
                </tr>
            `;
        })
        .join('');
}

function handleDownloadTable() {
    const { table_csv = '' } = state.results || {};
    let csvContent;
    if (table_csv) {
        csvContent = table_csv;
    } else {
        const { therapists } = state;
        const headers = ['Name', 'Specialty', 'Email', 'Phone', 'Address'];
        const rows = therapists.map((t) => [
            t.name || '',
            t.specialty_label || t.specialty || '',
            t.email || '',
            t.phone || '',
            t.address || '',
        ]);
        csvContent = [
            headers.join(','),
            ...rows.map((row) =>
                row.map((cell) => `"${cell.replace(/"/g, '""')}"`).join(',')
            ),
        ].join('\n');
    }
    const filename = `therapists_${new Date().toISOString().split('T')[0]}.csv`;
    downloadFile(csvContent, filename, 'text/csv');
}

// ============================================
// Step 3: My info
// ============================================

function hydrateUserInfoForm() {
    const ui = state.userInfo || {};
    const form = elements.userinfoForm;
    if (!form) return;
    form.first_name.value = ui.first_name || '';
    form.last_name.value = ui.last_name || '';
    form.birth_date.value = ui.birth_date || '';
    form.insurance.value = ui.insurance || '';
    form.email.value = ui.email || '';
    form.phone.value = ui.phone || '';
}

function handleUserInfoSubmit(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);

    state.userInfo = {
        first_name: formData.get('first_name'),
        last_name: formData.get('last_name'),
        birth_date: formData.get('birth_date') || null,
        insurance: formData.get('insurance') || null,
        email: formData.get('email') || null,
        phone: formData.get('phone') || null,
    };
    // Editing user info invalidates previously generated drafts.
    state.results = null;
    persistState();

    navigate('template');
}

// ============================================
// Step 4: Mail template body
// ============================================

/**
 * Client-side mirror of EmailGenerator._generate_salutation in
 * therapist_finder/email/generator.py — preview only; the backend still
 * generates the real drafts.
 */
function generateSalutation(name) {
    if (!name) return 'Sehr geehrte/r';
    const titleMatch = name.match(/(Dr\.|Dipl\.-Psych\.)/);
    const title = titleMatch ? titleMatch[0] : '';
    const parts = name.trim().split(/\s+/);
    const lastName = parts[parts.length - 1] || '';
    if (name.includes('Frau')) {
        return `Sehr geehrte Frau ${title} ${lastName}`.replace(/\s+/g, ' ').trim();
    }
    if (name.includes('Herr')) {
        return `Sehr geehrter Herr ${title} ${lastName}`.replace(/\s+/g, ' ').trim();
    }
    return `Sehr geehrte/r ${title} ${lastName}`.replace(/\s+/g, ' ').trim();
}

function renderTemplatePreview() {
    const body = elements.templateBody.value || '';
    const therapist = state.therapists.find((t) => !!t.email) || state.therapists[0];

    if (!therapist) {
        elements.templatePreviewTarget.textContent = '';
        elements.templatePreviewBody.textContent = '(No therapist to preview against.)';
        return;
    }

    const ui = state.userInfo || {};
    const salutation = therapist.salutation || generateSalutation(therapist.name);

    let rendered = body.replace(/<ANREDE>/g, salutation);
    // Mirror server-side str.format replacement for the small set of fields used.
    const fullName = `${ui.first_name || ''} ${ui.last_name || ''}`.trim();
    rendered = rendered
        .replace(/\{name\}/g, fullName)
        .replace(/\{address\}/g, '')
        .replace(/\{telefon\}/g, ui.phone || '')
        .replace(/\{email\}/g, ui.email || '')
        .replace(/\{vermittlungscode\}/g, '');

    elements.templatePreviewTarget.textContent = `for: ${therapist.name}`;
    elements.templatePreviewBody.textContent = rendered;
}

async function initTemplateView() {
    if (!state.templateBody) {
        showStatus(elements.templateStatus, 'Loading default template…', 'info');
        try {
            const result = await getTemplate();
            state.templateBody = result.body || '';
            persistState();
            hideStatus(elements.templateStatus);
        } catch (error) {
            console.error('Load template error:', error);
            showStatus(
                elements.templateStatus,
                error instanceof APIError
                    ? error.message
                    : 'Failed to load default template.',
                'error'
            );
        }
    }
    elements.templateBody.value = state.templateBody;
    renderTemplatePreview();
}

async function handleTemplateSubmit(event) {
    event.preventDefault();
    const body = elements.templateBody.value;
    if (!body.trim()) return;

    state.templateBody = body;
    persistState();

    setButtonLoading(elements.templateContinue, true);
    showStatus(elements.templateStatus, 'Generating emails…', 'info');

    try {
        const result = await generateEmails(state.therapists, state.userInfo, body);
        state.results = result;
        // Reset queue position on fresh generation.
        state.queue = { items: [], index: 0 };
        persistState();
        hideStatus(elements.templateStatus);
        navigate('send');
    } catch (error) {
        console.error('Generation error:', error);
        showStatus(
            elements.templateStatus,
            error instanceof APIError
                ? error.message
                : 'Failed to generate emails. Please try again.',
            'error'
        );
    } finally {
        setButtonLoading(elements.templateContinue, false);
    }
}

// ============================================
// Step 5: Send mails (queue)
// ============================================

function loadContactedEmails() {
    try {
        const raw = localStorage.getItem(CONTACTED_STORAGE_KEY);
        if (!raw) return new Set();
        const parsed = JSON.parse(raw);
        return new Set(Array.isArray(parsed) ? parsed : []);
    } catch (error) {
        console.warn('Failed to load contacted emails:', error);
        return new Set();
    }
}

function saveContactedEmails(set) {
    try {
        localStorage.setItem(CONTACTED_STORAGE_KEY, JSON.stringify([...set]));
    } catch (error) {
        console.warn('Failed to save contacted emails:', error);
    }
}

function markEmailContacted(email) {
    if (!email) return;
    const set = loadContactedEmails();
    set.add(email.toLowerCase());
    saveContactedEmails(set);
}

function buildMailtoUrl({ to, subject, body }) {
    const encodedTo = encodeURIComponent(to || '');
    const encodedSubject = encodeURIComponent(subject || '');
    const baseLength = `mailto:${encodedTo}?subject=${encodedSubject}&body=`.length;
    const budget = MAILTO_MAX_LENGTH - baseLength;

    let bodyToEncode = body || '';
    let truncated = false;
    let encodedBody = encodeURIComponent(bodyToEncode);

    if (encodedBody.length > budget) {
        truncated = true;
        const markerLength = encodeURIComponent(TRUNCATION_MARKER).length;
        let low = 0;
        let high = bodyToEncode.length;
        while (low < high) {
            const mid = Math.ceil((low + high) / 2);
            const candidate = encodeURIComponent(bodyToEncode.slice(0, mid)).length;
            if (candidate + markerLength <= budget) low = mid;
            else high = mid - 1;
        }
        bodyToEncode = bodyToEncode.slice(0, low) + TRUNCATION_MARKER;
        encodedBody = encodeURIComponent(bodyToEncode);
    }

    return {
        url: `mailto:${encodedTo}?subject=${encodedSubject}&body=${encodedBody}`,
        truncated,
    };
}

function currentQueueDraft() {
    const { items, index } = state.queue;
    return items[index] || null;
}

function initSendView() {
    const drafts = (state.results && state.results.drafts) || [];
    if (drafts.length === 0) {
        showStatus(
            elements.queueStatus,
            'No drafts available. Go back and generate emails first.',
            'warning'
        );
        return;
    }

    // Build the queue once per session unless drafts changed length.
    const needsRebuild =
        !state.queue ||
        !Array.isArray(state.queue.items) ||
        state.queue.items.length === 0 ||
        state.queue.index >= state.queue.items.length;

    if (needsRebuild) {
        const contacted = loadContactedEmails();
        const items = drafts.filter((d) => d.to && !contacted.has(d.to.toLowerCase()));
        state.queue = { items, index: 0 };
        persistState();
    }

    if (state.queue.items.length === 0) {
        showStatus(
            elements.queueStatus,
            'All therapists from this list were already contacted. Clear your browser storage to start over.',
            'info'
        );
        elements.queueTherapist.innerHTML = '';
        elements.queueSubject.textContent = '';
        elements.queueBodyPreview.textContent = '';
        elements.queueOpen.disabled = true;
        elements.queueNext.disabled = true;
        return;
    }

    renderQueueItem();
}

function renderQueueItem() {
    const draft = currentQueueDraft();
    if (!draft) {
        showStatus(elements.queueStatus, '✓ Queue complete.', 'success');
        elements.queueTherapist.innerHTML = '';
        elements.queueSubject.textContent = '';
        elements.queueBodyPreview.textContent = '';
        elements.queueOpen.disabled = true;
        elements.queueNext.disabled = true;
        return;
    }

    const { items, index } = state.queue;
    elements.queuePosition.textContent = String(index + 1);
    elements.queueTotal.textContent = String(items.length);

    elements.queueTherapist.innerHTML = `
        <span class="queue-therapist-name">${escapeHtml(draft.therapist_name || draft.to)}</span>
        <span class="queue-therapist-email">${escapeHtml(draft.to)}</span>
    `;
    elements.queueSubject.textContent = draft.subject || '';
    elements.queueBodyPreview.textContent = draft.body || '';

    const { truncated } = buildMailtoUrl(draft);
    elements.queueTruncationWarning.hidden = !truncated;

    elements.queueNext.disabled = true;
    elements.queueOpen.disabled = false;
    hideStatus(elements.queueStatus);
}

function handleQueueOpen() {
    const draft = currentQueueDraft();
    if (!draft) return;
    const { url } = buildMailtoUrl(draft);

    const link = document.createElement('a');
    link.href = url;
    link.rel = 'noopener';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    markEmailContacted(draft.to);
    elements.queueNext.disabled = false;
    elements.queueOpen.disabled = true;
    showStatus(
        elements.queueStatus,
        'Mail app opened. Click Next when ready for the next therapist.',
        'info'
    );
}

function handleQueueNext() {
    state.queue.index += 1;
    persistState();
    renderQueueItem();
}

function handleQueueSkip() {
    state.queue.index += 1;
    persistState();
    renderQueueItem();
}

async function handleQueueCopyBody() {
    const draft = currentQueueDraft();
    if (!draft) return;
    try {
        await navigator.clipboard.writeText(draft.body || '');
        showStatus(elements.queueStatus, '✓ Email body copied to clipboard.', 'success');
    } catch (error) {
        console.warn('Clipboard write failed:', error);
        showStatus(
            elements.queueStatus,
            'Could not access clipboard. Select the text in the preview and copy manually.',
            'warning'
        );
    }
}

// ============================================
// Event Listeners
// ============================================

function initEventListeners() {
    // Step 1
    elements.searchForm.addEventListener('submit', handlePdfUrlSubmit);
    elements.toggleUpload.addEventListener('click', (e) => {
        e.preventDefault();
        setEntrySection('upload');
    });
    elements.toggleSearch.addEventListener('click', (e) => {
        e.preventDefault();
        setEntrySection('search');
    });

    elements.dropzone.addEventListener('click', (e) => {
        if (e.target !== elements.removeFile && !elements.removeFile.contains(e.target)) {
            elements.fileInput.click();
        }
    });
    elements.fileInput.addEventListener('change', (e) => {
        handleFileSelect(e.target.files[0]);
    });
    elements.dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        elements.dropzone.classList.add('dragover');
    });
    elements.dropzone.addEventListener('dragleave', () => {
        elements.dropzone.classList.remove('dragover');
    });
    elements.dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        elements.dropzone.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        handleFileSelect(file);
    });
    elements.removeFile.addEventListener('click', (e) => {
        e.stopPropagation();
        handleFileRemove();
    });
    elements.uploadBtn.addEventListener('click', handleUpload);

    // Step 2
    elements.downloadTable.addEventListener('click', handleDownloadTable);

    // Step 3
    elements.userinfoForm.addEventListener('submit', handleUserInfoSubmit);

    // Step 4
    elements.templateForm.addEventListener('submit', handleTemplateSubmit);
    elements.templateBody.addEventListener('input', () => {
        state.templateBody = elements.templateBody.value;
        renderTemplatePreview();
    });

    // Step 5
    elements.queueOpen.addEventListener('click', handleQueueOpen);
    elements.queueNext.addEventListener('click', handleQueueNext);
    elements.queueSkip.addEventListener('click', handleQueueSkip);
    elements.queueCopyBody.addEventListener('click', handleQueueCopyBody);

    // Router
    window.addEventListener('hashchange', renderRoute);
}

// ============================================
// Init
// ============================================

function init() {
    initEventListeners();
    if (!window.location.hash) {
        window.location.hash = '#/url';
    } else {
        renderRoute();
    }
    console.log('Therapist Finder initialized');
}

init();
