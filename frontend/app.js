/* ═══════════════════════════════════════════════════════
   PaperMind AI — SaaS Frontend
   ════════════════════════════════════════════════════ */

'use strict';

// ─────────────────────────────────────────────────────
// API Base URL — works whether opened via file:// or http://
// ─────────────────────────────────────────────────────
const API_BASE = window.location.protocol === 'file:'
  ? 'http://127.0.0.1:7860'
  : '';

// ─────────────────────────────────────────────────────
// Session ID  (persisted for this browser tab)
// ─────────────────────────────────────────────────────
let sessionId = sessionStorage.getItem('pm_session_id');
let sessionPromise = null;

async function ensureSession() {
  if (sessionId) return sessionId;
  if (sessionPromise) return sessionPromise;

  sessionPromise = (async () => {
    try {
      const res = await fetch(API_BASE + '/api/session', { method: 'POST' });
      const data = await res.json();
      sessionId = data.session_id;
      sessionStorage.setItem('pm_session_id', sessionId);
    } catch {
      sessionId = crypto.randomUUID(); // fallback
    }
    sessionPromise = null;
    return sessionId;
  })();
  return sessionPromise;
}

// ─────────────────────────────────────────────────────
// State
// ─────────────────────────────────────────────────────
let lastResult = null;
let abortController = null;

// ─────────────────────────────────────────────────────
// Navbar
// ─────────────────────────────────────────────────────
const navbar   = document.getElementById('navbar');
const hamburger= document.getElementById('hamburger');
const navMenu  = document.getElementById('navMenu');

window.addEventListener('scroll', () => {
  navbar.classList.toggle('scrolled', window.scrollY > 60);
  scrollTopBtn.classList.toggle('visible', window.scrollY > 500);
  triggerCounters();
}, { passive: true });

hamburger.addEventListener('click', () => {
  hamburger.classList.toggle('active');
  navMenu.classList.toggle('open');
});
navMenu.querySelectorAll('.nav-link').forEach(link => {
  link.addEventListener('click', () => {
    hamburger.classList.remove('active');
    navMenu.classList.remove('open');
  });
});

// ─────────────────────────────────────────────────────
// Scroll to Top
// ─────────────────────────────────────────────────────
const scrollTopBtn = document.getElementById('scrollTopBtn');
scrollTopBtn.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));

// ─────────────────────────────────────────────────────
// Smooth scroll for anchor links
// ─────────────────────────────────────────────────────
document.querySelectorAll('a[href^="#"]').forEach(a => {
  a.addEventListener('click', e => {
    const target = document.querySelector(a.getAttribute('href'));
    if (!target) return;
    e.preventDefault();
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
});

// ─────────────────────────────────────────────────────
// Stats Counter Animation
// ─────────────────────────────────────────────────────
let countersTriggered = false;

function triggerCounters() {
  if (countersTriggered) return;
  const statsSection = document.querySelector('.hero-stats');
  if (!statsSection) return;
  const rect = statsSection.getBoundingClientRect();
  if (rect.top < window.innerHeight - 50) {
    countersTriggered = true;
    document.querySelectorAll('.stat-num').forEach(el => {
      const target = parseInt(el.dataset.target, 10);
      animateCounter(el, target);
    });
  }
}

function animateCounter(el, target) {
  const duration = 1800;
  const start    = performance.now();
  const easeOut  = t => 1 - Math.pow(1 - t, 3);

  function update(now) {
    const elapsed  = Math.min(now - start, duration);
    const progress = easeOut(elapsed / duration);
    el.textContent = Math.round(progress * target).toLocaleString();
    if (elapsed < duration) requestAnimationFrame(update);
    else el.textContent = target.toLocaleString();
  }
  requestAnimationFrame(update);
}
triggerCounters(); // immediate check

// ─────────────────────────────────────────────────────
// Pricing — Monthly / Annual Toggle
// ─────────────────────────────────────────────────────
const billingToggle  = document.getElementById('billingToggle');
const toggleMonthly  = document.getElementById('toggle-monthly');
const toggleAnnual   = document.getElementById('toggle-annual');

if (billingToggle) {
  billingToggle.addEventListener('change', () => {
    const isAnnual = billingToggle.checked;
    toggleMonthly.classList.toggle('active', !isAnnual);
    toggleAnnual.classList.toggle('active', isAnnual);

    document.querySelectorAll('.price-amount').forEach(el => {
      const val = isAnnual ? el.dataset.annual : el.dataset.monthly;
      el.textContent = val;
    });
  });
}

// ─────────────────────────────────────────────────────
// Testimonials Carousel
// ─────────────────────────────────────────────────────
const track     = document.getElementById('testimonialTrack');
const dotsWrap  = document.getElementById('carouselDots');
const prevBtn   = document.getElementById('prevBtn');
const nextBtn   = document.getElementById('nextBtn');

if (track) {
  const cards       = track.querySelectorAll('.testimonial-card');
  let   carouselIdx = 0;
  let   autoTimer;

  // Build dots
  cards.forEach((_, i) => {
    const dot = document.createElement('button');
    dot.className = 'carousel-dot' + (i === 0 ? ' active' : '');
    dot.setAttribute('aria-label', `Testimonial ${i + 1}`);
    dot.addEventListener('click', () => goTo(i));
    dotsWrap.appendChild(dot);
  });

  function getVisible() {
    const w = window.innerWidth;
    if (w >= 1024) return 3;
    if (w >= 640)  return 2;
    return 1;
  }

  function goTo(idx) {
    const visible = getVisible();
    const max     = Math.max(0, cards.length - visible);
    carouselIdx   = Math.max(0, Math.min(idx, max));

    const cardW   = cards[0].offsetWidth + 24; // gap
    track.style.transform = `translateX(-${carouselIdx * cardW}px)`;

    dotsWrap.querySelectorAll('.carousel-dot').forEach((d, i) => {
      d.classList.toggle('active', i === carouselIdx);
    });
  }

  function next() { goTo(carouselIdx + 1 > cards.length - getVisible() ? 0 : carouselIdx + 1); }
  function prev() { goTo(carouselIdx - 1 < 0 ? Math.max(0, cards.length - getVisible()) : carouselIdx - 1); }

  nextBtn.addEventListener('click', () => { next(); resetAuto(); });
  prevBtn.addEventListener('click', () => { prev(); resetAuto(); });

  function startAuto() { autoTimer = setInterval(next, 5000); }
  function resetAuto() { clearInterval(autoTimer); startAuto(); }
  startAuto();
  window.addEventListener('resize', () => goTo(carouselIdx));
}

// ─────────────────────────────────────────────────────
// Intersection Observer — fade-in animations
// ─────────────────────────────────────────────────────
const observer = new IntersectionObserver(entries => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.style.animation = 'fadeUp 0.6s ease-out forwards';
      observer.unobserve(entry.target);
    }
  });
}, { threshold: 0.1, rootMargin: '0px 0px -60px 0px' });

document.querySelectorAll('.feature-card, .step-item, .price-card, .testimonial-card').forEach(el => {
  el.style.opacity = '0';
  observer.observe(el);
});

// ─────────────────────────────────────────────────────
// Upload / Drag-Drop
// ─────────────────────────────────────────────────────
const uploadForm  = document.getElementById('uploadForm');
const dropZone    = document.getElementById('dropZone');
const pdfFileInput= document.getElementById('pdfFile');
const analyzeBtn  = document.getElementById('analyzeBtn');
const fileInfo    = document.getElementById('fileInfo');
const fileNameEl  = document.getElementById('fileName');
const fileSizeEl  = document.getElementById('fileSize');

// Drag & drop
['dragenter','dragover'].forEach(e => {
  dropZone.addEventListener(e, ev => { ev.preventDefault(); dropZone.classList.add('dragover'); });
});
['dragleave','drop'].forEach(e => {
  dropZone.addEventListener(e, ev => {
    ev.preventDefault();
    dropZone.classList.remove('dragover');
    if (ev.type === 'drop') handleFileSelect(ev.dataTransfer.files[0]);
  });
});

pdfFileInput.addEventListener('change', () => {
  if (pdfFileInput.files.length) handleFileSelect(pdfFileInput.files[0]);
});

function handleFileSelect(file) {
  if (!file) return;
  if (file.type !== 'application/pdf') { showToast('Only PDF files are accepted.', 'error'); return; }
  if (file.size > 10 * 1024 * 1024)    { showToast('File must be under 10 MB.', 'error');     return; }

  // Update UI
  fileNameEl.textContent = file.name;
  fileSizeEl.textContent = '(' + (file.size / 1024 / 1024).toFixed(2) + ' MB)';
  fileInfo.style.display = 'flex';
  dropZone.querySelector('h3').textContent = 'PDF selected';
  dropZone.style.borderColor = 'var(--purple)';
  analyzeBtn.disabled = false;
}

// ─────────────────────────────────────────────────────
// Form Submit → SSE streaming analysis
// ─────────────────────────────────────────────────────
const uploadPanel   = document.getElementById('uploadPanel');
const progressPanel = document.getElementById('progressPanel');
const progressFill  = document.getElementById('progressFill');
const progressMsg   = document.getElementById('progressMsg');
const resultsPanel  = document.getElementById('resultsPanel');
const chatPanel     = document.getElementById('chatPanel');

const STEPS = [
  { pct: 5,  label: 'Extracting text' },
  { pct: 40, label: 'Building semantic index' },
  { pct: 65, label: 'Extracting metadata' },
  { pct: 80, label: 'Analysis (Gemini 1.5 Pro)' },
  { pct: 100,label: 'Analysis complete' },
];

function getStepIndex(pct) {
  if (pct <= 20)  return 0;
  if (pct <= 55)  return 1;
  if (pct <= 70)  return 2;
  if (pct <= 95)  return 3;
  return 4;
}

function updateProgressUI(pct, msg) {
  progressFill.style.width = pct + '%';
  progressMsg.textContent  = msg;

  const stepIdx = getStepIndex(pct);
  document.querySelectorAll('.prog-step').forEach((s, i) => {
    s.classList.remove('active', 'done');
    if (i < stepIdx)       s.classList.add('done');
    else if (i === stepIdx) s.classList.add('active');

    const status = s.querySelector('.prog-status');
    if (i < stepIdx)        status.textContent = '✓';
    else if (i === stepIdx) status.textContent = '…';
    else                    status.textContent = '';
  });
}

uploadForm.addEventListener('submit', async e => {
  e.preventDefault();
  if (!pdfFileInput.files.length) { showToast('Please select a PDF file.', 'error'); return; }

  const sid = await ensureSession();
  const fd  = new FormData();
  fd.append('file', pdfFileInput.files[0]);
  fd.append('session_id', sid);

  // Switch panels
  uploadPanel.style.display   = 'none';
  progressPanel.style.display = 'block';
  resultsPanel.style.display  = 'none';
  chatPanel.style.display     = 'none';
  document.getElementById('errorBox').style.display = 'none';
  progressMsg.style.display = 'block';
  updateProgressUI(0, 'Connecting…');

  // Inject skeleton loaders
  const skeletonHtml = document.getElementById('skeletonTemplate').innerHTML;
  document.getElementById('summaryText').innerHTML = skeletonHtml;
  document.getElementById('critiqueText').innerHTML = skeletonHtml;
  document.getElementById('futureText').innerHTML = skeletonHtml;

  if (abortController) abortController.abort();
  abortController = new AbortController();

  try {
    // Use fetch-based SSE  (EventSource can't do POST, so we stream via fetch)
    const response = await fetch(API_BASE + '/api/stream-upload', { 
      method: 'POST', 
      body: fd,
      signal: abortController.signal
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({ error: 'Upload failed' }));
      throw new Error(escapeHtml(err.error || 'Upload failed'));
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let   buffer  = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop(); // keep incomplete line

      for (const line of lines) {
        if (!line.startsWith('data:')) continue;
        const raw  = line.slice(5).trim();
        if (!raw)   continue;

        try {
          const data = JSON.parse(raw);
          if (data.error) throw new Error(escapeHtml(data.error));

          updateProgressUI(data.pct || 0, data.step || '');

          if (data.done && data.result) {
            lastResult = data.result;
            showResults(lastResult);
          }
        } catch (parseErr) {
          if (parseErr instanceof SyntaxError) {
            console.warn('SSE parse error:', parseErr);
          } else {
            throw parseErr;
          }
        }
      }
    }

  } catch (err) {
    if (err.name === 'AbortError') return;
    showToast('Analysis failed.', 'error');
    progressMsg.style.display = 'none';
    const errorBox = document.getElementById('errorBox');
    const errorBoxMsg = document.getElementById('errorBoxMsg');
    errorBox.style.display = 'flex';
    errorBoxMsg.textContent = err.message;
    progressFill.style.width = '0%';
    document.querySelectorAll('.prog-step').forEach(s => s.classList.remove('active', 'done'));
  }
});

// ─────────────────────────────────────────────────────
// Show Results
// ─────────────────────────────────────────────────────
function showResults(data) {
  progressPanel.style.display = 'none';
  resultsPanel.style.display  = 'block';
  chatPanel.style.display     = 'flex';

  // Populate metadata card
  const meta    = data.meta || {};
  document.getElementById('metaTitle').textContent   = meta.title    || meta.filename || 'Research Paper';
  document.getElementById('metaAuthors').textContent = meta.authors  || 'Authors not detected';

  if (meta.year)  {
    const el = document.getElementById('metaYear');
    el.querySelector('span').textContent = meta.year;
    el.style.display = 'inline-flex';
  }
  if (meta.doi)   {
    const el = document.getElementById('metaDoi');
    el.querySelector('span').textContent = meta.doi;
    el.style.display = 'inline-flex';
  }
  
  const elWords = document.getElementById('metaWords');
  if (meta.word_count !== undefined && meta.word_count !== null) {
    elWords.querySelector('span').textContent = Number(meta.word_count).toLocaleString() + ' words';
    elWords.style.display = 'inline-flex';
  } else {
    if (elWords) elWords.style.display = 'none';
  }

  // Text panes
  renderMarkdown('summaryText',  data.summary            || 'No summary returned.');
  renderMarkdown('critiqueText', data.critique           || 'No critique returned.');
  renderMarkdown('futureText',   data.future_directions  || 'No future directions returned.');

  // Excerpts
  const excContainer = document.getElementById('excerptsContainer');
  excContainer.innerHTML = '';
  (data.excerpts || []).forEach((ex, i) => {
    const d = document.createElement('div');
    d.className = 'excerpt-item';
    d.innerHTML = `<span class="excerpt-num">Excerpt ${i + 1}</span><br>${escapeHtml(ex)}`;
    excContainer.appendChild(d);
  });
  if (!data.excerpts?.length) excContainer.innerHTML = '<p style="color:var(--text-muted)">No key excerpts extracted.</p>';

  // Citations
  const citeContainer = document.getElementById('citationsContainer');
  citeContainer.innerHTML = '';
  (data.citations || []).forEach(c => {
    const d = document.createElement('div');
    d.className = 'citation-item';
    d.textContent = c;
    citeContainer.appendChild(d);
  });
  if (!data.citations?.length) citeContainer.innerHTML = '<p style="color:var(--text-muted)">No citations detected.</p>';

  // Smooth scroll
  setTimeout(() => resultsPanel.scrollIntoView({ behavior: 'smooth', block: 'start' }), 200);
  showToast('Analysis complete! 🎉', 'success');
}

// Light markdown → HTML for result text
function renderMarkdown(id, text) {
  const el = document.getElementById(id);
  // Bold, bullets, line breaks
  let html = escapeHtml(text)
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/^[•\-\*] (.+)$/gm, '<li>$1</li>')
    .replace(/<\/li>\n<li>/g, '</li><li>')
    .replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>')
    .replace(/\n/g, '<br>');
  el.innerHTML = html;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;');
}

// ─────────────────────────────────────────────────────
// Tab Switching
// ─────────────────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('pane-' + btn.dataset.tab).classList.add('active');
  });
});

// ─────────────────────────────────────────────────────
// Analyze Another Paper
// ─────────────────────────────────────────────────────
document.getElementById('analyzeNewBtn').addEventListener('click', () => {
  if (abortController) {
    abortController.abort();
    abortController = null;
  }

  // Reset form
  uploadForm.reset();
  fileInfo.style.display = 'none';
  analyzeBtn.disabled    = true;
  dropZone.querySelector('h3').textContent = 'Drop your PDF here';
  dropZone.style.borderColor = '';
  lastResult = null;

  // Reset session
  sessionStorage.removeItem('pm_session_id');
  sessionId = null;
  ensureSession();

  // Reset chat
  const chatMessages = document.getElementById('chatMessages');
  chatMessages.innerHTML = `
    <div class="chat-bubble ai">
      <div class="bubble-icon"><i class="fas fa-brain"></i></div>
      <div class="bubble-text">Hi! I've read your paper. Ask me anything — methodology, findings, limitations, or anything else you're curious about.</div>
    </div>`;

  // Switch panels
  resultsPanel.style.display = 'none';
  chatPanel.style.display    = 'none';
  uploadPanel.style.display  = 'block';
  uploadPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
});

// ─────────────────────────────────────────────────────
// Download PDF Report
// ─────────────────────────────────────────────────────
document.getElementById('downloadReportBtn').addEventListener('click', async () => {
  if (!lastResult) { showToast('No analysis to export.', 'error'); return; }

  const btn = document.getElementById('downloadReportBtn');
  const orig = btn.innerHTML;
  btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating…';
  btn.disabled  = true;

  try {
    const res = await fetch(API_BASE + '/api/report', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(lastResult),
    });
    if (!res.ok) throw new Error((await res.json()).error || 'Report generation failed');

    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = ((lastResult.meta?.filename || 'paper').replace('.pdf','')) + '_analysis.pdf';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);

    showToast('Report downloaded!', 'success');
  } catch (err) {
    showToast('Export failed: ' + err.message, 'error');
  } finally {
    btn.innerHTML = orig;
    btn.disabled  = false;
  }
});

// ─────────────────────────────────────────────────────
// Q&A Chat
// ─────────────────────────────────────────────────────
const chatMessages = document.getElementById('chatMessages');
const chatInput    = document.getElementById('chatInput');
const chatSendBtn  = document.getElementById('chatSendBtn');
const clearChatBtn = document.getElementById('clearChatBtn');

async function sendChatMessage() {
  const question = chatInput.value.trim();
  if (!question || !sessionId) return;
  chatInput.value = '';

  // User bubble
  appendBubble(question, 'user');

  // Typing indicator
  const typing = appendTyping();

  try {
    const res = await fetch(API_BASE + '/api/chat', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ session_id: sessionId, question }),
    });
    const data = await res.json();
    typing.remove();

    if (!res.ok) throw new Error(data.error || 'Chat failed');
    appendBubble(data.answer, 'ai');
  } catch (err) {
    typing.remove();
    appendBubble('Sorry, I encountered an error: ' + err.message, 'ai');
  }
}

chatSendBtn.addEventListener('click', sendChatMessage);
chatInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChatMessage(); }
});

clearChatBtn.addEventListener('click', () => {
  chatMessages.innerHTML = `
    <div class="chat-bubble ai">
      <div class="bubble-icon"><i class="fas fa-brain"></i></div>
      <div class="bubble-text">Chat cleared. Feel free to ask more questions about your paper!</div>
    </div>`;
});

function appendBubble(text, role) {
  const wrap = document.createElement('div');
  wrap.className = `chat-bubble ${role}`;
  wrap.innerHTML = `
    ${role === 'ai' ? '<div class="bubble-icon"><i class="fas fa-brain"></i></div>' : ''}
    <div class="bubble-text">${renderChatText(text)}</div>
    ${role === 'user' ? '<div class="bubble-icon" style="background:var(--indigo)"><i class="fas fa-user"></i></div>' : ''}
  `;
  chatMessages.appendChild(wrap);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return wrap;
}

function appendTyping() {
  const wrap = document.createElement('div');
  wrap.className = 'chat-bubble ai';
  wrap.innerHTML = `
    <div class="bubble-icon"><i class="fas fa-brain"></i></div>
    <div class="typing-indicator"><span></span><span></span><span></span></div>
  `;
  chatMessages.appendChild(wrap);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return wrap;
}

function renderChatText(text) {
  return escapeHtml(text)
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>');
}

// ─────────────────────────────────────────────────────
// Newsletter (cosmetic)
// ─────────────────────────────────────────────────────
const newsletterBtn   = document.getElementById('newsletterBtn');
const newsletterEmail = document.getElementById('newsletterEmail');
if (newsletterBtn) {
  newsletterBtn.addEventListener('click', () => {
    const email = newsletterEmail.value.trim();
    if (!email || !email.includes('@')) { showToast('Please enter a valid email address.', 'error'); return; }
    newsletterEmail.value = '';
    showToast('You\'re subscribed! 🎉', 'success');
  });
}

// ─────────────────────────────────────────────────────
// Toast Notification System
// ─────────────────────────────────────────────────────
function showToast(message, type = 'info') {
  document.querySelectorAll('.toast').forEach(t => t.remove());

  const icons = { success: 'fa-circle-check', error: 'fa-circle-exclamation', info: 'fa-circle-info' };
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <i class="fas ${icons[type] || icons.info} toast-icon"></i>
    <span class="toast-msg">${escapeHtml(message)}</span>
  `;
  document.body.appendChild(toast);
  requestAnimationFrame(() => {
    requestAnimationFrame(() => toast.classList.add('show'));
  });
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 400);
  }, 4000);
}