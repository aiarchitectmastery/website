/* AI Architect Mastery — main.js
   Minimal vanilla JS:
   - Mobile nav toggle
   - Smooth scroll offset for sticky header
   - YouTube facade (lazy load player on click)
   - Footer year
    - GA4 conversion and outbound link tracking
*/

(function () {
  'use strict';

  // ----- Mobile nav -----
  const toggle = document.querySelector('.nav-toggle');
  const nav = document.getElementById('primary-nav');
  if (toggle && nav) {
    toggle.addEventListener('click', function () {
      const open = nav.classList.toggle('open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    nav.querySelectorAll('a').forEach(function (a) {
      a.addEventListener('click', function () {
        nav.classList.remove('open');
        toggle.setAttribute('aria-expanded', 'false');
      });
    });
  }

  // ----- Footer year -----
  const yearEl = document.getElementById('year');
  if (yearEl) yearEl.textContent = String(new Date().getFullYear());

  // ----- YouTube facade (privacy + perf) -----
  document.querySelectorAll('.video-facade').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const id = btn.getAttribute('data-video-id');
      if (!id) return;
      if (btn.getAttribute('data-track') === 'video-play-intro' && typeof window.gtag === 'function') {
        window.gtag('event', 'video_play_intro', {
          video_id: id,
          video_title: 'AI Driven Development Methodology introduction'
        });
      }
      const iframe = document.createElement('iframe');
      iframe.className = 'video-iframe';
      iframe.setAttribute('src', 'https://www.youtube-nocookie.com/embed/' + encodeURIComponent(id) + '?autoplay=1&rel=0');
      iframe.setAttribute('title', 'AI Architect Mastery introduction video');
      iframe.setAttribute('allow', 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture');
      iframe.setAttribute('allowfullscreen', '');
      iframe.setAttribute('loading', 'lazy');
      btn.replaceWith(iframe);
    });
  });

  // ----- Outbound / CTA tracking -----
  document.addEventListener('click', function (e) {
    const target = e.target.closest('[data-track], a[href^="mailto:"], a[href^="http"]:not([href*="aiarchitectmastery.com"])');
    if (!target) return;
    const trackId = target.getAttribute('data-track');
    if (target.classList.contains('video-facade') && trackId === 'video-play-intro') return;
    const href = target.getAttribute('href') || '';
    const isUdemy = href.includes('udemy.com');
    const isMailto = href.startsWith('mailto:');
    let name = trackId || (isMailto ? 'contact-email' : 'outbound-link');
    const params = { link_url: target.href || '' };

    if (isUdemy) {
      name = 'udemy_course_click';
      params.cta_id = trackId || 'unknown';
    }

    if (typeof window.gtag === 'function') {
      window.gtag('event', name, params);
    }
    if (window.console) console.debug('[track]', name, params);
  });

  // ----- MailerLite lead tracking -----
  // MailerLite renders this callback for the embedded form after a successful
  // subscription. A DOM observer is also used because MailerLite loads
  // asynchronously and can define its callback after this script runs.
  let mailerLiteLeadTracked = false;
  function trackMailerLiteLead() {
    if (mailerLiteLeadTracked) return;
    mailerLiteLeadTracked = true;
    if (typeof window.gtag === 'function') {
      window.gtag('event', 'generate_lead', {
        method: 'mailerlite',
        form_id: '4TDpWG'
      });
    }
    if (window.console) console.debug('[track]', 'generate_lead', { method: 'mailerlite', form_id: '4TDpWG' });
  }

  const mailerLiteSuccess = window.ml_webform_success_41342389;
  window.ml_webform_success_41342389 = function () {
    if (typeof mailerLiteSuccess === 'function') {
      mailerLiteSuccess.apply(this, arguments);
    }
    trackMailerLiteLead();
  };

  const mailerLiteObserver = new MutationObserver(function () {
    const success = document.querySelector('.ml-subscribe-form-41342389 .ml-form-successBody');
    if (!success || window.getComputedStyle(success).display === 'none') return;
    trackMailerLiteLead();
    mailerLiteObserver.disconnect();
  });
  mailerLiteObserver.observe(document.body, {
    attributes: true,
    attributeFilter: ['class', 'style'],
    childList: true,
    subtree: true
  });
})();
