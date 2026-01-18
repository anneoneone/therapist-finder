/**
 * Therapist Finder - Main Application
 * @module app
 */

import { parseFile, generateEmails, downloadFile, APIError } from './api.js';

// ============================================
// State
// ============================================

const state = {
    file: null,
    therapists: [],
    userInfo: {},
    results: null,
};

// ============================================
// DOM Elements
// ============================================

const elements = {
    // Upload section
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
    downloadApplescript: document.getElementById('download-applescript'),
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

        const count = state.therapists.length;
        const withEmail = state.therapists.filter(t => t.email).length;

        showStatus(
            elements.uploadStatus,
            `✓ Found ${count} therapists (${withEmail} with email)`,
            'success'
        );

        // Show user info section
        elements.userinfoSection.hidden = false;
        elements.userinfoSection.scrollIntoView({ behavior: 'smooth' });

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
 * Display results in the table and summary.
 */
function displayResults() {
    const { therapists } = state;
    const { drafts = [], applescript = '' } = state.results || {};

    // Summary
    const totalCount = therapists.length;
    const emailCount = drafts.length;

    elements.resultsSummary.innerHTML = `
        <div class="summary-item">
            <div class="summary-value">${totalCount}</div>
            <div class="summary-label">Total Therapists</div>
        </div>
        <div class="summary-item">
            <div class="summary-value">${emailCount}</div>
            <div class="summary-label">Emails Generated</div>
        </div>
    `;

    // Table
    elements.therapistsTbody.innerHTML = therapists.map(therapist => {
        const hasEmail = !!therapist.email;
        const statusClass = hasEmail ? 'ready' : 'no-email';
        const statusText = hasEmail ? 'Ready' : 'No Email';

        return `
            <tr>
                <td>${escapeHtml(therapist.name)}</td>
                <td>${escapeHtml(therapist.email) || '<span class="text-muted">—</span>'}</td>
                <td>${escapeHtml(therapist.phone) || '<span class="text-muted">—</span>'}</td>
                <td>${escapeHtml(therapist.address) || '<span class="text-muted">—</span>'}</td>
                <td><span class="status-badge ${statusClass}">${statusText}</span></td>
            </tr>
        `;
    }).join('');
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
        const headers = ['Name', 'Email', 'Phone', 'Address'];
        const rows = therapists.map(t => [
            t.name || '',
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

/**
 * Download AppleScript file.
 */
function handleDownloadApplescript() {
    const { applescript = '' } = state.results || {};

    if (!applescript) {
        showStatus(elements.generateStatus, 'No AppleScript available', 'warning');
        return;
    }

    const filename = `mail_drafts_${new Date().toISOString().split('T')[0]}.applescript`;
    downloadFile(applescript, filename, 'text/plain');
}

// ============================================
// Event Listeners
// ============================================

function initEventListeners() {
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

    // Download buttons
    elements.downloadTable.addEventListener('click', handleDownloadTable);
    elements.downloadApplescript.addEventListener('click', handleDownloadApplescript);
}

// ============================================
// Initialize
// ============================================

function init() {
    initEventListeners();
    console.log('Therapist Finder initialized');
}

// Start the app
init();
