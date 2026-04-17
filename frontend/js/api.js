/**
 * API client for Therapist Finder backend.
 * @module api
 */

// Override via `window.API_BASE = 'https://your-api.onrender.com/api'` before
// this module loads (e.g. in a <script> tag in index.html) when the frontend
// is hosted on a different origin than the backend.
const API_BASE = (typeof window !== 'undefined' && window.API_BASE) || '/api';

/**
 * Custom error class for API errors.
 */
export class APIError extends Error {
    constructor(message, status, code = null) {
        super(message);
        this.name = 'APIError';
        this.status = status;
        this.code = code;
    }
}

/**
 * Make an API request with error handling.
 * @param {string} endpoint - API endpoint
 * @param {RequestInit} options - Fetch options
 * @returns {Promise<any>} - Response data
 */
async function request(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;

    try {
        const response = await fetch(url, {
            ...options,
            headers: {
                ...options.headers,
            },
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
            throw new APIError(
                error.detail || `Request failed with status ${response.status}`,
                response.status,
                error.code
            );
        }

        // Handle empty responses
        const contentType = response.headers.get('content-type');
        if (contentType?.includes('application/json')) {
            return response.json();
        }

        return response;
    } catch (error) {
        if (error instanceof APIError) {
            throw error;
        }
        throw new APIError(
            error.message || 'Network error',
            0,
            'NETWORK_ERROR'
        );
    }
}

/**
 * Parse a PDF or text file to extract therapist data.
 * @param {File} file - The file to parse
 * @returns {Promise<Object>} - Parsed therapist data
 */
export async function parseFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    return request('/therapists/parse', {
        method: 'POST',
        body: formData,
    });
}

/**
 * Generate email drafts for therapists.
 * @param {Array} therapists - List of therapist objects
 * @param {Object} userInfo - User information
 * @returns {Promise<Object>} - Generated emails and files
 */
export async function generateEmails(therapists, userInfo) {
    return request('/emails/generate', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            therapists,
            user_info: userInfo,
        }),
    });
}

/**
 * Download a file from a blob URL.
 * @param {Blob} blob - File blob
 * @param {string} filename - Download filename
 */
export function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

/**
 * Download content as a file.
 * @param {string} content - File content
 * @param {string} filename - Download filename
 * @param {string} mimeType - MIME type
 */
export function downloadFile(content, filename, mimeType = 'text/plain') {
    const blob = new Blob([content], { type: mimeType });
    downloadBlob(blob, filename);
}

/**
 * Health check for the API.
 * @returns {Promise<Object>} - Health status
 */
export async function healthCheck() {
    return request('/health');
}
