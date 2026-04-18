/**
 * Therapist Finder - Main Application
 * @module app
 */

import {
    APIError,
    downloadFile,
    generateEmails,
    listSpecialties,
    parseFile,
    searchByAddress,
} from './api.js';

// ============================================
// State
// ============================================

const state = {
    file: null,
    therapists: [],
    userInfo: {},
    results: null,
    queue: { items: [], index: 0 },
};

const CONTACTED_STORAGE_KEY = 'therapist-finder:contacted-emails';
const MAILTO_MAX_LENGTH = 1900;
const TRUNCATION_MARKER = '\n\n[… truncated — use "Copy body" to paste full text]';

// ============================================
// DOM Elements
// ============================================

const elements = {
    // Address search section (default)
    searchSection: document.getElementById('search-section'),
    searchForm: document.getElementById('search-form'),
    searchBtn: document.getElementById('search-btn'),
    searchStatus: document.getElementById('search-status'),
    searchAddress: document.getElementById('search-address'),
    searchMax: document.getElementById('search-max'),
    searchRadius: document.getElementById('search-radius'),
    searchSpecialty: document.getElementById('search-specialty'),
    toggleUpload: document.getElementById('toggle-upload'),
    toggleSearch: document.getElementById('toggle-search'),

    // Upload section (legacy fallback)
    uploadSection: document.getElementById('upload-section'),
    dropzone: document.getElementById('dropzone'),
    fileInput: document.getElementById('file-input'),
    selectedFile: document.getElementById('selected-file'),
    fileName: document.getElementById('file-name'),
    removeFile: document.getElementById('remove-file'),
    uploadBtn: document.getElementById('upload-btn'),
    uploadStatus: document.getElementById('upload-status'),

    // User info section
    userinfoSection: document.getElementById('userinfo-section'),
    userinfoForm: document.getElementById('userinfo-form'),
    generateStatus: document.getElementById('generate-status'),

    // Results section
    resultsSection: document.getElementById('results-section'),
    resultsSummary: document.getElementById('results-summary'),
    therapistsTbody: document.getElementById('therapists-tbody'),
    downloadTable: document.getElementById('download-table'),
    openQueue: document.getElementById('open-queue'),

    // Queue modal
    queueOverlay: document.getElementById('queue-overlay'),
    queueClose: document.getElementById('queue-close'),
    queuePosition: document.getElementById('queue-position'),
    queueTotal: document.getElementById('queue-total'),
    queueTherapist: document.getElementById('queue-therapist'),
    queueSubject: document.getElementById('queue-subject'),
    queueBodyPreview: document.getElementById('queue-body-preview'),
    queueTruncationWarning: document.getElementById('queue-truncation-warning'),
    queueStatus: document.getElementById('queue-status'),
    queueCopyBody: document.getElementById('queue-copy-body'),
    queueSkip: document.getElementById('queue-skip'),
    queueOpen: document.getElementById('queue-open'),
    queueNext: document.getElementById('queue-next'),
};

// ============================================
// Utility Functions
// ============================================

/**
 * Show a status message.
 * @param {HTMLElement} element - Status element
 * @param {string} message - Message to display
 * @param {'success'|'error'|'info'|'warning'} type - Message type
 */
function showStatus(element, message, type = 'info') {
    element.textContent = message;
    element.className = `status ${type}`;
    element.hidden = false;
}

/**
 * Hide a status message.
 * @param {HTMLElement} element - Status element
 */
function hideStatus(element) {
    element.hidden = true;
}

/**
 * Set loading state on a button.
 * @param {HTMLButtonElement} button - Button element
 * @param {boolean} loading - Loading state
 */
function setButtonLoading(button, loading) {
    const text = button.querySelector('.btn-text');
    const loader = button.querySelector('.btn-loader');

    if (loading) {
        button.disabled = true;
        if (text) text.hidden = true;
        if (loader) loader.hidden = false;
    } else {
        button.disabled = false;
        if (text) text.hidden = false;
        if (loader) loader.hidden = true;
    }
}

/**
 * Escape HTML to prevent XSS.
 * @param {string} text - Raw text
 * @returns {string} - Escaped HTML
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Format a date string for display.
 * @param {string} dateStr - Date string
 * @returns {string} - Formatted date
 */
function formatDate(dateStr) {
    if (!dateStr) return '-';
    return dateStr;
}

// ============================================
// Address search (default flow)
// ============================================

/**
 * Handle the "Find therapists" form submission.
 * Calls the backend crawl pipeline with an address and populates the same
 * state that the PDF-upload path fills, so the downstream email-draft
 * queue just works.
 * @param {Event} event - Form submit event
 */
async function handleAddressSearch(event) {
    event.preventDefault();
    const address = elements.searchAddress.value.trim();
    if (!address) return;

    const maxResults = Number(elements.searchMax.value) || 20;
    const radiusKm = Number(elements.searchRadius.value) || 15;
    const specialty = elements.searchSpecialty?.value || 'psychotherapie';
    const specialtyLabel =
        elements.searchSpecialty?.selectedOptions?.[0]?.textContent?.trim()
        || specialty;

    setButtonLoading(elements.searchBtn, true);
    showStatus(
        elements.searchStatus,
        `Crawling public directories near ${address} for ${specialtyLabel}…`,
        'info'
    );

    try {
        const result = await searchByAddress({
            address,
            max_results: maxResults,
            radius_km: radiusKm,
            specialty,
        });
        state.therapists = result.therapists || [];
        state.results = null;

        const total = state.therapists.length;
        const withEmail = state.therapists.filter((t) => t.email).length;
        const originLabel = result.origin_address || address;
        const specLabel = result.specialty_label || specialtyLabel;
        showStatus(
            elements.searchStatus,
            `✓ ${total} ${specLabel} provider${total === 1 ? '' : 's'} `
                + `near ${originLabel} (${withEmail} with email; only those `
                + `can receive a mailto draft)`,
            'success'
        );

        // Render the ranked list right away so the user can see results
        // before filling in personal info.
        renderTherapists();
        elements.resultsSection.hidden = false;
        elements.userinfoSection.hidden = false;
        elements.resultsSection.scrollIntoView({ behavior: 'smooth' });
    } catch (error) {
        console.error('Search error:', error);
        showStatus(
            elements.searchStatus,
            error instanceof APIError
                ? error.message
                : 'Search failed. Please try again.',
            'error'
        );
    } finally {
        setButtonLoading(elements.searchBtn, false);
    }
}

/**
 * Swap between the address-search and file-upload sections.
 * @param {'search' | 'upload'} target
 */
function setEntrySection(target) {
    const showSearch = target === 'search';
    elements.searchSection.hidden = !showSearch;
    elements.uploadSection.hidden = showSearch;
}

// ============================================
// File Handling
// ============================================

/**
 * Handle file selection.
 * @param {File} file - Selected file
 */
function handleFileSelect(file) {
    if (!file) return;

    // Validate file type
    const validTypes = ['application/pdf', 'text/plain'];
    const validExtensions = ['.pdf', '.txt'];
    const hasValidType = validTypes.includes(file.type);
    const hasValidExtension = validExtensions.some(ext =>
        file.name.toLowerCase().endsWith(ext)
    );

    if (!hasValidType && !hasValidExtension) {
        showStatus(elements.uploadStatus, 'Please select a PDF or text file', 'error');
        return;
    }

    state.file = file;
    elements.fileName.textContent = file.name;
    elements.selectedFile.hidden = false;
    elements.dropzone.querySelector('.dropzone-content').hidden = true;
    elements.uploadBtn.disabled = false;
    hideStatus(elements.uploadStatus);
}

/**
 * Remove selected file.
 */
function handleFileRemove() {
    state.file = null;
    elements.fileInput.value = '';
    elements.selectedFile.hidden = true;
    elements.dropzone.querySelector('.dropzone-content').hidden = false;
    elements.uploadBtn.disabled = true;
    hideStatus(elements.uploadStatus);
}

// ============================================
// Upload & Parse
// ============================================

/**
 * Upload and parse the selected file.
 */
async function handleUpload() {
    if (!state.file) return;

    setButtonLoading(elements.uploadBtn, true);
    showStatus(elements.uploadStatus, 'Parsing file...', 'info');

    try {
        const result = await parseFile(state.file);
        state.therapists = result.therapists || result;
        state.results = null;

        const total = state.therapists.length;
        const withEmail = state.therapists.filter((t) => t.email).length;

        showStatus(
            elements.uploadStatus,
            `✓ ${withEmail} contactable therapist${withEmail === 1 ? '' : 's'} `
                + `(of ${total} parsed; only those with an email can receive a `
                + `mailto draft)`,
            'success'
        );

        renderTherapists();
        elements.resultsSection.hidden = false;
        elements.userinfoSection.hidden = false;
        elements.resultsSection.scrollIntoView({ behavior: 'smooth' });

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
// Email Generation
// ============================================

/**
 * Handle user info form submission.
 * @param {Event} event - Form submit event
 */
async function handleGenerateEmails(event) {
    event.preventDefault();

    const form = event.target;
    const formData = new FormData(form);
    const submitBtn = form.querySelector('button[type="submit"]');

    // Collect user info
    state.userInfo = {
        first_name: formData.get('first_name'),
        last_name: formData.get('last_name'),
        birth_date: formData.get('birth_date') || null,
        insurance: formData.get('insurance') || null,
        email: formData.get('email') || null,
        phone: formData.get('phone') || null,
    };

    setButtonLoading(submitBtn, true);
    showStatus(elements.generateStatus, 'Generating emails...', 'info');

    try {
        const result = await generateEmails(state.therapists, state.userInfo);
        state.results = result;

        showStatus(elements.generateStatus, '✓ Emails generated successfully!', 'success');

        // Show results section
        displayResults();
        elements.resultsSection.hidden = false;
        elements.resultsSection.scrollIntoView({ behavior: 'smooth' });

    } catch (error) {
        console.error('Generation error:', error);
        showStatus(
            elements.generateStatus,
            error instanceof APIError
                ? error.message
                : 'Failed to generate emails. Please try again.',
            'error'
        );
    } finally {
        setButtonLoading(submitBtn, false);
    }
}

// ============================================
// Results Display
// ============================================

/**
 * Render the therapist list into the results table.
 * Safe to call after an address search (no drafts yet) or after email
 * generation (drafts populated) — the summary adapts to what's available.
 */
function renderTherapists() {
    const { therapists } = state;
    const drafts = state.results?.drafts;
    const contactable = therapists.filter((t) => !!t.email).length;

    const contactableLabel = drafts
        ? `${drafts.length}`
        : `${contactable}`;
    const contactableHeader = drafts
        ? 'Emails Generated'
        : 'Contactable (have email)';

    elements.resultsSummary.innerHTML = `
        <div class="summary-item">
            <div class="summary-value">${therapists.length}</div>
            <div class="summary-label">Total Therapists</div>
        </div>
        <div class="summary-item">
            <div class="summary-value">${contactableLabel}</div>
            <div class="summary-label">${contactableHeader}</div>
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

/**
 * Populate the specialty dropdown from the backend catalog. Falls back
 * silently to the static options baked into index.html if the API is
 * unreachable (e.g. during local file:// testing).
 */
async function loadSpecialtyOptions() {
    const select = elements.searchSpecialty;
    if (!select) return;
    try {
        const { specialties = [], default: defaultKey } = await listSpecialties();
        if (!specialties.length) return;
        const previous = select.value;
        select.innerHTML = specialties
            .map(
                (s) =>
                    `<option value="${escapeHtml(s.key)}">${escapeHtml(s.label)}</option>`,
            )
            .join('');
        const desired = previous && specialties.some((s) => s.key === previous)
            ? previous
            : defaultKey;
        if (desired) select.value = desired;
    } catch (error) {
        console.warn('Failed to load specialties, keeping static options:', error);
    }
}

/**
 * Update the results after email generation so the summary shows drafts.
 */
function displayResults() {
    renderTherapists();
}

// ============================================
// Downloads
// ============================================

/**
 * Download therapist table as CSV.
 */
function handleDownloadTable() {
    // Use server-generated CSV if available
    const { table_csv = '' } = state.results || {};

    let csvContent;
    if (table_csv) {
        csvContent = table_csv;
    } else {
        // Fallback: generate client-side
        const { therapists } = state;
        const headers = ['Name', 'Specialty', 'Email', 'Phone', 'Address'];
        const rows = therapists.map(t => [
            t.name || '',
            t.specialty_label || t.specialty || '',
            t.email || '',
            t.phone || '',
            t.address || '',
        ]);

        csvContent = [
            headers.join(','),
            ...rows.map(row =>
                row.map(cell => `"${cell.replace(/"/g, '""')}"`).join(',')
            ),
        ].join('\n');
    }

    const filename = `therapists_${new Date().toISOString().split('T')[0]}.csv`;
    downloadFile(csvContent, filename, 'text/csv');
}

// ============================================
// Email Draft Queue
// ============================================

/**
 * Load the set of previously-contacted email addresses from localStorage.
 * @returns {Set<string>}
 */
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

/**
 * Persist the set of contacted email addresses.
 * @param {Set<string>} set
 */
function saveContactedEmails(set) {
    try {
        localStorage.setItem(CONTACTED_STORAGE_KEY, JSON.stringify([...set]));
    } catch (error) {
        console.warn('Failed to save contacted emails:', error);
    }
}

/**
 * Mark a single email address as contacted.
 * @param {string} email
 */
function markEmailContacted(email) {
    if (!email) return;
    const set = loadContactedEmails();
    set.add(email.toLowerCase());
    saveContactedEmails(set);
}

/**
 * Build a mailto: URL, truncating the body if needed to stay within URL limits.
 * @param {{to: string, subject: string, body: string}} draft
 * @returns {{url: string, truncated: boolean}}
 */
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
        // Binary-search for the largest prefix of body whose encoded length
        // plus the encoded truncation marker fits into the budget.
        let low = 0;
        let high = bodyToEncode.length;
        while (low < high) {
            const mid = Math.ceil((low + high) / 2);
            const candidate = encodeURIComponent(bodyToEncode.slice(0, mid)).length;
            if (candidate + markerLength <= budget) {
                low = mid;
            } else {
                high = mid - 1;
            }
        }
        bodyToEncode = bodyToEncode.slice(0, low) + TRUNCATION_MARKER;
        encodedBody = encodeURIComponent(bodyToEncode);
    }

    return {
        url: `mailto:${encodedTo}?subject=${encodedSubject}&body=${encodedBody}`,
        truncated,
    };
}

/**
 * Get the current draft in the queue, or null.
 * @returns {object|null}
 */
function currentQueueDraft() {
    const { items, index } = state.queue;
    return items[index] || null;
}

/**
 * Open the queue modal, populating it with uncontacted drafts.
 */
function openQueue() {
    const drafts = (state.results && state.results.drafts) || [];
    if (drafts.length === 0) {
        showStatus(elements.generateStatus, 'No drafts available. Generate emails first.', 'warning');
        return;
    }

    const contacted = loadContactedEmails();
    const items = drafts.filter(d => d.to && !contacted.has(d.to.toLowerCase()));

    if (items.length === 0) {
        showStatus(
            elements.generateStatus,
            'All therapists from this list were already contacted. Clear your browser storage to start over.',
            'info'
        );
        return;
    }

    state.queue = { items, index: 0 };
    elements.queueOverlay.hidden = false;
    hideStatus(elements.queueStatus);
    renderQueueItem();
}

/**
 * Render the current queue item into the modal.
 */
function renderQueueItem() {
    const draft = currentQueueDraft();
    if (!draft) {
        closeQueue();
        showStatus(elements.generateStatus, '✓ Queue complete.', 'success');
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

/**
 * Trigger the mailto: URL and mark the current email as contacted.
 */
function handleQueueOpen() {
    const draft = currentQueueDraft();
    if (!draft) return;

    const { url } = buildMailtoUrl(draft);

    // Use an anchor click for best cross-browser reliability with mailto:.
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

/**
 * Advance to the next queue item.
 */
function handleQueueNext() {
    state.queue.index += 1;
    renderQueueItem();
}

/**
 * Skip the current therapist without marking them as contacted.
 */
function handleQueueSkip() {
    state.queue.index += 1;
    renderQueueItem();
}

/**
 * Close the queue modal.
 */
function closeQueue() {
    elements.queueOverlay.hidden = true;
    state.queue = { items: [], index: 0 };
}

function handleQueueClose() {
    closeQueue();
}

/**
 * Copy the current draft's body to the clipboard.
 */
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
    // Address search (default flow)
    elements.searchForm.addEventListener('submit', handleAddressSearch);
    elements.toggleUpload.addEventListener('click', (e) => {
        e.preventDefault();
        setEntrySection('upload');
    });
    elements.toggleSearch.addEventListener('click', (e) => {
        e.preventDefault();
        setEntrySection('search');
    });

    // Dropzone click
    elements.dropzone.addEventListener('click', (e) => {
        if (e.target !== elements.removeFile && !elements.removeFile.contains(e.target)) {
            elements.fileInput.click();
        }
    });

    // File input change
    elements.fileInput.addEventListener('change', (e) => {
        handleFileSelect(e.target.files[0]);
    });

    // Drag and drop
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

    // Remove file
    elements.removeFile.addEventListener('click', (e) => {
        e.stopPropagation();
        handleFileRemove();
    });

    // Upload button
    elements.uploadBtn.addEventListener('click', handleUpload);

    // User info form
    elements.userinfoForm.addEventListener('submit', handleGenerateEmails);

    // Download / queue buttons
    elements.downloadTable.addEventListener('click', handleDownloadTable);
    elements.openQueue.addEventListener('click', openQueue);

    // Queue modal
    elements.queueClose.addEventListener('click', handleQueueClose);
    elements.queueOpen.addEventListener('click', handleQueueOpen);
    elements.queueNext.addEventListener('click', handleQueueNext);
    elements.queueSkip.addEventListener('click', handleQueueSkip);
    elements.queueCopyBody.addEventListener('click', handleQueueCopyBody);
    elements.queueOverlay.addEventListener('click', (e) => {
        if (e.target === elements.queueOverlay) handleQueueClose();
    });
}

// ============================================
// Initialize
// ============================================

function init() {
    initEventListeners();
    loadSpecialtyOptions();
    console.log('Therapist Finder initialized');
}

// Start the app
init();
