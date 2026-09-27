const cfg = window.LEGAL_AI_CONFIG;
const supabaseClient = window.supabase.createClient(cfg.SUPABASE_URL, cfg.SUPABASE_ANON_KEY);

const state = {
  session: null,
  documents: [],
  selectedDocumentId: null,
};

function byId(id) {
  return document.getElementById(id);
}

function escapeHtml(value) {
  if (value === null || value === undefined) return '';
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function renderMarkdown(text) {
  const html = typeof marked !== 'undefined' ? marked.parse(text || '') : `<p>${escapeHtml(text)}</p>`;
  return typeof DOMPurify !== 'undefined' ? DOMPurify.sanitize(html) : escapeHtml(text);
}

function showStatus(id, message, type = 'loading') {
  const el = byId(id);
  if (el) {
    el.textContent = message;
    el.className = `form-status visible ${type}`;
  }
}

function hideStatus(id) {
  const el = byId(id);
  if (el) el.className = 'form-status';
}

// ---------------------------------------------------------------------------
// Auth — Supabase Auth. Every API call below sends the Supabase access token
// as `Authorization: Bearer <token>`; the backend verifies it and Postgres
// row-level security enforces that a user only ever sees their own data.
// ---------------------------------------------------------------------------

async function getAccessToken() {
  const { data } = await supabaseClient.auth.getSession();
  return data.session ? data.session.access_token : null;
}

async function api(path, options = {}) {
  const token = await getAccessToken();
  if (!token) {
    throw new Error('Please sign in first.');
  }
  const headers = {
    ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
    Authorization: `Bearer ${token}`,
    ...(options.headers || {}),
  };
  const response = await fetch(`${cfg.API_BASE_URL}${path}`, { ...options, headers });
  if (!response.ok) {
    const data = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(data.detail || 'Request failed');
  }
  const contentType = response.headers.get('content-type') || '';
  return contentType.includes('application/json') ? response.json() : response;
}

function updateAuthUI(session) {
  document.querySelectorAll('[data-auth-name]').forEach((el) => {
    el.textContent = session?.user?.email ?? 'Guest';
  });
  document.querySelectorAll('[data-requires-auth]').forEach((el) => {
    el.style.display = session ? '' : 'none';
  });
  document.querySelectorAll('[data-requires-guest]').forEach((el) => {
    el.style.display = session ? 'none' : '';
  });
}

async function handleSignUp(event) {
  event.preventDefault();
  const email = byId('auth-email').value.trim();
  const password = byId('auth-password').value;
  showStatus('auth-status', 'Creating account...', 'loading');
  const { data, error } = await supabaseClient.auth.signUp({ email, password });
  if (error) {
    showStatus('auth-status', error.message, 'error');
    return;
  }
  if (data.session) {
    // Email confirmation is disabled, so sign-up returns a live session —
    // the user is already logged in; take them straight to the dashboard.
    state.session = data.session;
    showStatus('auth-status', 'Account created — taking you in...', 'success');
    const modal = byId('auth-modal');
    if (modal) modal.classList.remove('open');
    window.location.href = '/dashboard';
    return;
  }
  // Email confirmation is enabled — no session yet; prompt the user to sign in.
  showStatus('auth-status', 'Account created. Now sign in with the same email and password.', 'success');
}

async function handleSignIn(event) {
  event.preventDefault();
  const email = byId('auth-email').value.trim();
  const password = byId('auth-password').value;
  showStatus('auth-status', 'Signing in...', 'loading');
  const { data, error } = await supabaseClient.auth.signInWithPassword({ email, password });
  if (error) {
    showStatus('auth-status', error.message, 'error');
    return;
  }
  state.session = data.session;
  hideStatus('auth-status');
  const modal = byId('auth-modal');
  if (modal) modal.classList.remove('open');
  window.location.href = '/dashboard';
}

async function handleSignOut() {
  await supabaseClient.auth.signOut();
  window.location.href = '/';
}

function requireAuthOrRedirect() {
  supabaseClient.auth.getSession().then(({ data }) => {
    if (!data.session) window.location.href = '/?auth=1';
  });
}

function openAuthModal() {
  const modal = byId('auth-modal');
  if (modal) modal.classList.add('open');
}

// ---------------------------------------------------------------------------
// Documents
// ---------------------------------------------------------------------------

async function loadDocuments(selectId) {
  try {
    const data = await api('/api/documents');
    state.documents = data.documents;
    const container = byId('document-list');
    if (container) {
      container.innerHTML = state.documents.length
        ? state.documents.map((doc) => `
            <div class="doc-list-item" data-doc-id="${doc.id}">
              <span>${escapeHtml(doc.filename)}</span>
              <span class="doc-status doc-status-${doc.upload_status}">${escapeHtml(doc.upload_status)}</span>
              <button type="button" class="btn-icon" data-delete-doc="${doc.id}" aria-label="Delete ${escapeHtml(doc.filename)}">✕</button>
            </div>
          `).join('')
        : '<div class="text-muted">No documents uploaded yet.</div>';
    }
    const select = selectId ? byId(selectId) : null;
    if (select) {
      select.innerHTML = '<option value="">No document — ask about Indian law</option>'
        + state.documents.map((doc) => `<option value="${doc.id}">${escapeHtml(doc.filename)}</option>`).join('');
    }
  } catch (error) {
    console.error('Failed to load documents', error);
  }
}

async function pollDocumentReady(documentId, statusId, maxAttempts = 40, intervalMs = 2000) {
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
    const data = await api(`/api/documents/${documentId}`);
    const status = data.document.upload_status;
    if (status === 'ready') return data.document;
    if (status === 'error') throw new Error('Document processing failed. Please try uploading again.');
    if (statusId) showStatus(statusId, `Processing document${'.'.repeat((i % 3) + 1)}`, 'loading');
  }
  throw new Error('Document processing timed out. Please refresh and try again.');
}

async function handleUpload(event, statusId, selectId) {
  event.preventDefault();
  const fileInput = event.target.querySelector('input[type="file"]');
  const file = fileInput.files[0];
  if (!file) return;

  const validTypes = ['.pdf', '.docx'];
  const ext = file.name.toLowerCase().slice(file.name.lastIndexOf('.'));
  if (!validTypes.includes(ext)) {
    showStatus(statusId, 'Only PDF and DOCX files are supported', 'error');
    return;
  }
  if (file.size > 10 * 1024 * 1024) {
    showStatus(statusId, 'File is too large — max 10MB', 'error');
    return;
  }

  try {
    showStatus(statusId, `Uploading ${file.name}...`, 'loading');
    const formData = new FormData();
    formData.append('file', file);
    const data = await api('/api/documents/upload', { method: 'POST', body: formData });
    state.selectedDocumentId = data.document.id;

    if (data.document.upload_status === 'processing') {
      await pollDocumentReady(data.document.id, statusId);
    }
    showStatus(statusId, `Ready: ${data.document.filename}`, 'success');
    setTimeout(() => hideStatus(statusId), 3000);
    await loadDocuments(selectId);
    fileInput.value = '';
  } catch (error) {
    showStatus(statusId, error.message, 'error');
  }
}

async function deleteDocument(documentId) {
  await api(`/api/documents/${documentId}`, { method: 'DELETE' });
  await loadDocuments('chat-document-select');
}

// ---------------------------------------------------------------------------
// Chat (streaming with a non-streaming fallback)
// ---------------------------------------------------------------------------

function appendUserMessage(container, text) {
  if (!container) return;
  const empty = container.querySelector('.chatbot-empty');
  if (empty) empty.remove();
  const div = document.createElement('div');
  div.className = 'chatbot-message chatbot-message-user';
  div.innerHTML = `<div class="chatbot-bubble chatbot-bubble-user"></div>`;
  div.querySelector('.chatbot-bubble').textContent = text;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function appendStreamingMessage(container) {
  if (!container) return { appendToken: () => {}, finalize: () => '' };
  const empty = container.querySelector('.chatbot-empty');
  if (empty) empty.remove();
  const div = document.createElement('div');
  div.className = 'chatbot-message chatbot-message-assistant';
  const bubble = document.createElement('div');
  bubble.className = 'chatbot-bubble chatbot-bubble-assistant';
  const textDiv = document.createElement('div');
  textDiv.className = 'chatbot-text chatbot-streaming';
  bubble.appendChild(textDiv);
  div.appendChild(bubble);
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  let rawText = '';
  return {
    appendToken(token) {
      rawText += token;
      textDiv.textContent = rawText;
      container.scrollTop = container.scrollHeight;
    },
    finalize(sources) {
      textDiv.classList.remove('chatbot-streaming');
      textDiv.classList.add('chatbot-markdown');
      textDiv.innerHTML = renderMarkdown(rawText);
      if (sources && sources.length) {
        const sourcesEl = document.createElement('div');
        sourcesEl.className = 'chatbot-sources';
        sourcesEl.innerHTML = '<div class="chatbot-sources-label">Sources</div>' + sources.map((s) => {
          const meta = s.metadata || {};
          const label = meta.section_heading || (meta.page_number ? `Page ${meta.page_number}` : 'Excerpt');
          return `<div class="chatbot-source-chip" title="${escapeHtml(s.text || '')}">${escapeHtml(label)}</div>`;
        }).join('');
        bubble.appendChild(sourcesEl);
      }
      container.scrollTop = container.scrollHeight;
      return rawText;
    },
  };
}

async function streamChat(endpoint, body, container) {
  const token = await getAccessToken();
  const response = await fetch(`${cfg.API_BASE_URL}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const errData = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(errData.detail || 'Request failed');
  }

  const streaming = appendStreamingMessage(container);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let sources = [];

  function processLines(text) {
    const lines = text.split('\n');
    const remainder = lines.pop();
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      try {
        const event = JSON.parse(line.slice(6));
        if (event.type === 'token') streaming.appendToken(event.content);
        else if (event.type === 'done') sources = event.sources || [];
      } catch (_) {}
    }
    return remainder;
  }

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    buffer = processLines(buffer);
  }
  if (buffer.trim()) processLines(`${buffer}\n`);
  streaming.finalize(sources);
}

async function handleAsk(event, { messagesId, inputId, documentSelectId, lawOnly = false }) {
  event.preventDefault();
  const input = byId(inputId);
  const question = input.value.trim();
  if (!question) return;
  input.value = '';

  const container = byId(messagesId);
  appendUserMessage(container, question);

  const documentId = documentSelectId ? byId(documentSelectId)?.value : null;

  try {
    if (!lawOnly && documentId) {
      await streamChat('/api/chat/stream', { document_id: Number(documentId), question }, container);
    } else {
      await streamChat('/api/law/ask/stream', { question }, container);
    }
  } catch (error) {
    const streaming = appendStreamingMessage(container);
    streaming.appendToken(`Sorry — ${error.message}`);
    streaming.finalize();
  }
}

// ---------------------------------------------------------------------------
// Clause extraction & risk analysis
// ---------------------------------------------------------------------------

async function runClause(documentId, clauseType) {
  const output = byId('analysis-output');
  output.innerHTML = '<div class="text-muted">Analyzing clause...</div>';
  try {
    const data = await api('/api/clauses/extract', {
      method: 'POST',
      body: JSON.stringify({ document_id: documentId, clause_type: clauseType }),
    });
    output.innerHTML = `
      <div class="analysis-result">
        <div class="analysis-risk analysis-risk-${data.risk_level.toLowerCase()}">${escapeHtml(data.risk_level)} risk</div>
        <blockquote>${escapeHtml(data.snippet || 'No matching clause found.')}</blockquote>
        <div class="chatbot-markdown">${renderMarkdown(data.explanation)}</div>
      </div>`;
  } catch (error) {
    output.innerHTML = `<div class="text-error">${escapeHtml(error.message)}</div>`;
  }
}

async function runRisk(documentId) {
  const output = byId('analysis-output');
  output.innerHTML = '<div class="text-muted">Analyzing risk...</div>';
  try {
    const data = await api('/api/risk/analyze', {
      method: 'POST',
      body: JSON.stringify({ document_id: documentId }),
    });
    output.innerHTML = `
      <div class="analysis-result">
        <div class="analysis-score">Risk score: ${data.risk_score}/10</div>
        <p>${escapeHtml(data.summary || '')}</p>
        <ul>${data.findings.map((f) => `<li>${escapeHtml(f)}</li>`).join('')}</ul>
      </div>`;
  } catch (error) {
    output.innerHTML = `<div class="text-error">${escapeHtml(error.message)}</div>`;
  }
}

// ---------------------------------------------------------------------------
// Document generator
// ---------------------------------------------------------------------------

const GENERATOR_COPY = {
  legal_notice: {
    placeholder: 'Example: I paid a ₹50,000 advance to ABC Contractors on 1 March 2026 for renovation work due to finish by 1 April 2026. It is now three weeks overdue and they are not responding to calls. I want to send a formal notice demanding completion within 15 days or a full refund.',
    hint: 'Describe who you’re notifying, what they did or failed to do, and what you’re demanding.',
  },
  complaint_letter: {
    placeholder: 'Example: My mobile phone was stolen from World Trade Park mall on March 24, 2026 at around 10 AM. I was watching a movie and left my phone on the seat during interval. When I returned, it was gone. The phone is an iPhone 16, black color, 128GB. I don’t have the IMEI number. There were no witnesses. I want to file a police complaint for investigation.',
    hint: 'Describe what happened, when, where, and what outcome you want (FIR, refund, resolution).',
  },
  nda: {
    placeholder: 'Example: I’m sharing product designs and pricing with a freelance developer, Priya Verma, before we sign a contract, and want to make sure she doesn’t share or use this information elsewhere.',
    hint: 'Describe what confidential information is being shared, with whom, and for how long it should stay protected.',
  },
  rental_agreement: {
    placeholder: 'Example: Renting a 2BHK flat at 14 MG Road, Pune to Rohan Mehta for ₹22,000/month, ₹44,000 security deposit, 11-month lease starting 1 September 2026, tenant pays electricity and water separately.',
    hint: 'Include property address, monthly rent, deposit, lease dates, and any special terms.',
  },
};

function updateGeneratorCopy(templateType) {
  const copy = GENERATOR_COPY[templateType];
  const textarea = byId('gen-issue');
  const hint = byId('gen-issue-hint');
  if (textarea && copy) textarea.placeholder = copy.placeholder;
  if (hint && copy) hint.textContent = copy.hint;
}

async function handleGenerate(event, forceGenerate = false) {
  event.preventDefault();
  const statusId = 'generator-status';
  try {
    showStatus(statusId, 'Analyzing your request and generating document...', 'loading');
    const payload = {
      template_type: byId('template-type').value,
      name: byId('gen-name').value.trim(),
      address: byId('gen-address').value.trim(),
      issue_description: byId('gen-issue').value.trim(),
      date: byId('gen-date').value,
      force_generate: forceGenerate,
    };
    if (!payload.name || !payload.address || !payload.issue_description || !payload.date) {
      throw new Error('Please fill in all fields');
    }
    const data = await api('/api/generate-document', { method: 'POST', body: JSON.stringify(payload) });

    if (data.status === 'mismatch') {
      showStatus(statusId, `${data.message} Click "Generate Anyway" to proceed regardless.`, 'error');
      byId('generator-force-btn').style.display = '';
      return;
    }
    if (data.status === 'needs_info') {
      showStatus(statusId, data.message, 'error');
      return;
    }

    hideStatus(statusId);
    byId('generator-force-btn').style.display = 'none';
    const preview = byId('generator-preview');
    if (preview) {
      preview.style.display = '';
      preview.querySelector('.generator-preview-text').textContent = data.preview;
      preview.querySelector('[data-download-url]').dataset.downloadUrl = data.download_url;
    }
  } catch (error) {
    showStatus(statusId, error.message, 'error');
  }
}

async function downloadGenerated(downloadPath) {
  const { url } = await api(downloadPath);
  window.open(url, '_blank');
}

// ---------------------------------------------------------------------------
// Bootstrap
// ---------------------------------------------------------------------------

async function bootstrap() {
  const { data } = await supabaseClient.auth.getSession();
  state.session = data.session;
  updateAuthUI(state.session);

  supabaseClient.auth.onAuthStateChange((_event, session) => {
    state.session = session;
    updateAuthUI(session);
  });

  const page = document.body.dataset.page;
  if (['dashboard', 'chat', 'generator'].includes(page)) {
    requireAuthOrRedirect();
  }

  document.getElementById('signup-form')?.addEventListener('submit', handleSignUp);
  document.getElementById('signin-form')?.addEventListener('submit', handleSignIn);
  document.getElementById('nav-logout-btn')?.addEventListener('click', handleSignOut);
  document.querySelectorAll('[data-open-auth]').forEach((el) => el.addEventListener('click', openAuthModal));

  if (page === 'dashboard') {
    await loadDocuments();
    document.getElementById('upload-form')?.addEventListener('submit', (e) => handleUpload(e, 'upload-status'));
    document.getElementById('dashboard-ask-form')?.addEventListener('submit', (e) =>
      handleAsk(e, { messagesId: 'dashboard-chat-messages', inputId: 'dashboard-question', lawOnly: true }));
    document.getElementById('quick-clause-button')?.addEventListener('click', () => {
      const doc = state.documents[0];
      if (!doc) return alert('Upload a document first.');
      runClause(doc.id, byId('clause-type').value);
    });
    document.getElementById('quick-risk-button')?.addEventListener('click', () => {
      const doc = state.documents[0];
      if (!doc) return alert('Upload a document first.');
      runRisk(doc.id);
    });
    document.getElementById('document-list')?.addEventListener('click', (e) => {
      const btn = e.target.closest('[data-delete-doc]');
      if (btn) deleteDocument(Number(btn.dataset.deleteDoc));
    });
  }

  if (page === 'chat') {
    await loadDocuments('chat-document-select');
    document.getElementById('chat-ask-form')?.addEventListener('submit', (e) =>
      handleAsk(e, { messagesId: 'chat-messages', inputId: 'chat-question', documentSelectId: 'chat-document-select' }));
    document.getElementById('chat-upload-form')?.addEventListener('submit', (e) => handleUpload(e, 'chat-upload-status', 'chat-document-select'));
  }

  if (page === 'generator') {
    document.querySelectorAll('.doc-type-card').forEach((card) => {
      card.addEventListener('click', () => {
        document.querySelectorAll('.doc-type-card').forEach((c) => c.classList.remove('active'));
        card.classList.add('active');
        byId('template-type').value = card.dataset.type;
        updateGeneratorCopy(card.dataset.type);
      });
    });
    updateGeneratorCopy(byId('template-type')?.value || 'complaint_letter');
    document.getElementById('generator-form')?.addEventListener('submit', (e) => handleGenerate(e, false));
    document.getElementById('generator-force-btn')?.addEventListener('click', (e) => handleGenerate(e, true));
    document.querySelector('[data-download-url]')?.addEventListener('click', (e) => {
      downloadGenerated(e.currentTarget.dataset.downloadUrl);
    });
  }

  document.querySelectorAll('.suggestion-chip[data-query], .suggestion-card[data-query]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const target = byId('dashboard-question') || byId('landing-question') || byId('chat-question');
      if (target) {
        target.value = btn.dataset.query;
        target.focus();
      }
    });
  });

  document.getElementById('nav-mobile-toggle')?.addEventListener('click', () => {
    document.querySelector('.nav-menu')?.classList.toggle('open');
  });
}

document.addEventListener('DOMContentLoaded', bootstrap);
