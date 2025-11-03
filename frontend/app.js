// ============================================
// NAVIGATION
// ============================================
const hamburger = document.querySelector('.hamburger');
const navMenu = document.querySelector('.nav-menu');
const navLinks = document.querySelectorAll('.nav-link');
const navbar = document.querySelector('.navbar');

// Toggle mobile menu
hamburger.addEventListener('click', () => {
  hamburger.classList.toggle('active');
  navMenu.classList.toggle('active');
});

// Close mobile menu when clicking on a link
navLinks.forEach(link => {
  link.addEventListener('click', () => {
    hamburger.classList.remove('active');
    navMenu.classList.remove('active');
  });
});

// Navbar scroll effect
window.addEventListener('scroll', () => {
  if (window.scrollY > 100) {
    navbar.classList.add('scrolled');
  } else {
    navbar.classList.remove('scrolled');
  }
});

// ============================================
// SCROLL TO TOP BUTTON
// ============================================
const scrollTopBtn = document.getElementById('scrollTop');

window.addEventListener('scroll', () => {
  if (window.scrollY > 500) {
    scrollTopBtn.classList.add('visible');
  } else {
    scrollTopBtn.classList.remove('visible');
  }
});

scrollTopBtn.addEventListener('click', () => {
  window.scrollTo({
    top: 0,
    behavior: 'smooth'
  });
});

// ============================================
// FORM HANDLING
// ============================================
const form = document.getElementById('uploadForm');
const fileInput = document.getElementById('pdfFile');
const loading = document.getElementById('loading');
const results = document.getElementById('results');
const summaryEl = document.getElementById('summary');
const critiqueEl = document.getElementById('critique');
const futureEl = document.getElementById('future');
const excerptsEl = document.getElementById('excerpts');

let lastResult = null;

// File input visual feedback
fileInput.addEventListener('change', (e) => {
  const uploadArea = document.querySelector('.upload-area');
  if (e.target.files.length > 0) {
    const fileName = e.target.files[0].name;
    uploadArea.querySelector('p').textContent = `Selected: ${fileName}`;
    uploadArea.style.borderColor = 'var(--primary)';
    uploadArea.style.background = 'rgba(0, 245, 255, 0.1)';
  }
});

// Form submit handler
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  
  if (!fileInput.files.length) {
    showNotification('Please select a PDF file.', 'error');
    return;
  }
  
  const file = fileInput.files[0];
  
  // Validate file type
  if (file.type !== 'application/pdf') {
    showNotification('Please upload a valid PDF file.', 'error');
    return;
  }
  
  // Validate file size (max 10MB)
  if (file.size > 10 * 1024 * 1024) {
    showNotification('File size must be less than 10MB.', 'error');
    return;
  }
  
  const fd = new FormData();
  fd.append('file', file);

  loading.style.display = 'flex';
  results.style.display = 'none';

  try {
    const resp = await fetch('/api/upload', { 
      method: 'POST', 
      body: fd 
    });
    
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.error || 'Upload failed');
    }
    
    const data = await resp.json();
    lastResult = data;

    // Populate results
    summaryEl.textContent = data.summary || 'No summary returned.';
    critiqueEl.textContent = data.critique || 'No critique returned.';
    futureEl.textContent = data.future_directions || 'No future directions returned.';

    // Populate excerpts
    excerptsEl.innerHTML = '';
    if (data.excerpts && data.excerpts.length > 0) {
      data.excerpts.forEach((ex, index) => {
        const d = document.createElement('div');
        d.className = 'excerpt';
        d.innerHTML = `<strong>Excerpt ${index + 1}:</strong><br>${ex}`;
        excerptsEl.appendChild(d);
      });
    } else {
      excerptsEl.innerHTML = '<p style="color: var(--text-muted);">No excerpts found.</p>';
    }

    // Add download button if it doesn't exist
    let downloadBtn = document.getElementById('downloadReportBtn');
    if (!downloadBtn) {
      downloadBtn = document.createElement('button');
      downloadBtn.id = 'downloadReportBtn';
      downloadBtn.className = 'btn btn-primary';
      downloadBtn.innerHTML = '<i class="fas fa-download"></i> Download PDF Report';
      downloadBtn.addEventListener('click', downloadReport);
      results.appendChild(downloadBtn);
    }

    results.style.display = 'block';
    showNotification('Analysis completed successfully!', 'success');
    
    // Smooth scroll to results
    setTimeout(() => {
      results.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 300);
    
  } catch (err) {
    showNotification('Error: ' + err.message, 'error');
  } finally {
    loading.style.display = 'none';
  }
});

// ============================================
// DOWNLOAD REPORT
// ============================================
async function downloadReport() {
  if (!lastResult) {
    showNotification('No result to export.', 'error');
    return;
  }

  try {
    const resp = await fetch('/api/report', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(lastResult)
    });

    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.error || 'PDF generation failed');
    }

    const blob = await resp.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const filename = (lastResult.meta && lastResult.meta.filename) 
      ? lastResult.meta.filename.replace('.pdf', '') + '_ai_report.pdf' 
      : 'ai_report.pdf';
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
    
    showNotification('Report downloaded successfully!', 'success');
  } catch (err) {
    showNotification('Download Error: ' + err.message, 'error');
  }
}

// ============================================
// CONTACT FORM
// ============================================
const contactForm = document.querySelector('.contact-form');
if (contactForm) {
  contactForm.addEventListener('submit', (e) => {
    e.preventDefault();
    showNotification('Thank you for your message! We\'ll get back to you soon.', 'success');
    contactForm.reset();
  });
}

// ============================================
// NOTIFICATION SYSTEM
// ============================================
function showNotification(message, type = 'info') {
  // Remove existing notifications
  const existing = document.querySelector('.notification');
  if (existing) existing.remove();
  
  const notification = document.createElement('div');
  notification.className = `notification ${type}`;
  notification.innerHTML = `
    <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
    <span>${message}</span>
  `;
  
  document.body.appendChild(notification);
  
  // Trigger animation
  setTimeout(() => notification.classList.add('show'), 10);
  
  // Auto remove after 4 seconds
  setTimeout(() => {
    notification.classList.remove('show');
    setTimeout(() => notification.remove(), 300);
  }, 4000);
}

// Add notification styles
const notificationStyles = `
  .notification {
    position: fixed;
    top: 100px;
    right: 20px;
    background: var(--card-bg);
    backdrop-filter: blur(20px);
    padding: 1rem 1.5rem;
    border-radius: 10px;
    border: 1px solid rgba(0, 245, 255, 0.3);
    display: flex;
    align-items: center;
    gap: 1rem;
    z-index: 10000;
    transform: translateX(400px);
    transition: transform 0.3s ease;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
    max-width: 400px;
  }
  
  .notification.show {
    transform: translateX(0);
  }
  
  .notification.success {
    border-color: #00ff88;
  }
  
  .notification.error {
    border-color: #ff0055;
  }
  
  .notification i {
    font-size: 1.5rem;
  }
  
  .notification.success i {
    color: #00ff88;
  }
  
  .notification.error i {
    color: #ff0055;
  }
  
  .notification.info i {
    color: var(--primary);
  }
  
  .notification span {
    color: var(--text-light);
    font-size: 0.95rem;
  }
  
  @media (max-width: 768px) {
    .notification {
      right: 10px;
      left: 10px;
      max-width: none;
    }
  }
`;

const styleSheet = document.createElement('style');
styleSheet.textContent = notificationStyles;
document.head.appendChild(styleSheet);

// ============================================
// SMOOTH SCROLL FOR ALL ANCHOR LINKS
// ============================================
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener('click', function (e) {
    const href = this.getAttribute('href');
    if (href !== '#' && document.querySelector(href)) {
      e.preventDefault();
      const target = document.querySelector(href);
      const offsetTop = target.offsetTop - 80;
      
      window.scrollTo({
        top: offsetTop,
        behavior: 'smooth'
      });
    }
  });
});

// ============================================
// INTERSECTION OBSERVER FOR ANIMATIONS
// ============================================
const observerOptions = {
  threshold: 0.1,
  rootMargin: '0px 0px -100px 0px'
};

const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.style.animation = 'fadeInUp 0.6s ease-out forwards';
      observer.unobserve(entry.target);
    }
  });
}, observerOptions);

// Observe all feature cards and sections
document.querySelectorAll('.feature-card, .step, .contact-item').forEach(el => {
  el.style.opacity = '0';
  observer.observe(el);
});