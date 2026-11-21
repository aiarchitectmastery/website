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
    document.documentElement.classList.add('nav-ready');
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
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && nav.classList.contains('open')) {
        nav.classList.remove('open');
        toggle.setAttribute('aria-expanded', 'false');
        toggle.focus();
      }
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
      iframe.setAttribute('title', btn.getAttribute('aria-label') || 'AI Architect Mastery video');
      iframe.setAttribute('allow', 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture');
      iframe.setAttribute('allowfullscreen', '');
      iframe.setAttribute('loading', 'lazy');
      btn.replaceWith(iframe);
    });
  });

  // ----- Outbound / CTA tracking -----
  // Fixed labels only; never turn arbitrary DOM text or URL values into events.
  const trackingLabels = new Set([
    'cta-gh300-bestprice-inline', 'cta-gh300-bestprice', 'cta-gh300-udemy',
    'cta-gh300-docs', 'social-linkedin', 'social-youtube',
    'social-instagram', 'contact-email'
  ]);
  const udemyCoursePath = '/course/github-copilot-gh-300-certification-prep/';
  document.addEventListener('click', function (e) {
    if (!(e.target instanceof Element)) return;
    const target = e.target.closest('[data-track], a[href^="mailto:"], a[href^="http"]:not([href*="aiarchitectmastery.com"])');
    if (!target) return;
    const trackId = target.getAttribute('data-track');
    if (target.classList.contains('video-facade') && trackId === 'video-play-intro') return;
    const href = target.getAttribute('href') || '';
    const isMailto = href.startsWith('mailto:');
    let url;
    try { url = new URL(href, document.baseURI); } catch (_) { /* no URL telemetry */ }
    const isHttp = url && (url.protocol === 'https:' || url.protocol === 'http:');
    const isUdemy = isHttp && url.protocol === 'https:' &&
      (url.hostname === 'www.udemy.com' || url.hostname === 'udemy.com') &&
      url.pathname === udemyCoursePath;
    let name = trackingLabels.has(trackId) ? trackId : (isMailto ? 'contact-email' : 'outbound-link');
    // Origins only, except the fixed public course path. No arbitrary paths,
    // userinfo, query, fragment, mailto recipient or form value is collected.
    const params = {};
    if (isHttp) params.link_url = url.origin + (isUdemy ? udemyCoursePath : '/');

    if (isUdemy) {
      name = 'udemy_course_click';
      params.cta_id = trackingLabels.has(trackId) ? trackId : 'unknown';
    }

    if (typeof window.gtag === 'function') {
      window.gtag('event', name, params);
    }
  });

  // ----- MailerLite lead tracking (form registry) -----
  // Registry: MailerLite webform numeric id -> fixed GA4 form label.
  // Adding a form = one entry here + one test fixture (tools/aam_website).
  // Labels are fixed strings; no email, field value or DOM text is ever sent.
  const leadForms = {
    '41342389': 'lm002_form' // MailerLite form 4TDpWG (AAM Agent Workflow, LM-002)
    // LM-FORM (label 'lm_form'): webform id comes from TASK-04; added in TASK-06.
    // Reserved: 'c_form' (course lead PRD).
  };

  function isVisibleSuccess(success) {
    if (!success || !success.isConnected || success.getClientRects().length === 0) return false;
    for (let element = success; element; element = element.parentElement) {
      const style = window.getComputedStyle(element);
      if (element.hidden || style.display === 'none' ||
          style.visibility === 'hidden' || style.visibility === 'collapse' ||
          style.opacity === '0' || element.getAttribute('aria-hidden') === 'true') return false;
    }
    return true;
  }

  // Each form has its own success-callback wrapper, success-view observer and
  // once-only flag. MailerLite renders ml_webform_success_<id> after a
  // successful subscription; the observer covers the case where MailerLite
  // loads asynchronously and defines its callback after this script runs.
  function registerLeadForm(webformId, label) {
    if (!/^[0-9]+$/.test(webformId)) return;
    let tracked = false;
    function trackLead() {
      if (tracked) return;
      tracked = true;
      if (typeof window.gtag === 'function') {
        window.gtag('event', 'generate_lead', {
          method: 'mailerlite',
          form_id: label
        });
      }
    }

    const callbackName = 'ml_webform_success_' + webformId;
    const original = window[callbackName];
    window[callbackName] = function () {
      if (typeof original === 'function') {
        original.apply(this, arguments);
      }
      trackLead();
    };

    const selector = '.ml-subscribe-form-' + webformId + ' .ml-form-successBody';
    const observer = new MutationObserver(function () {
      if (!isVisibleSuccess(document.querySelector(selector))) return;
      trackLead();
      observer.disconnect();
    });
    observer.observe(document.body, {
      attributes: true,
      attributeFilter: ['class', 'style', 'hidden', 'aria-hidden'],
      childList: true,
      subtree: true
    });
  }

  Object.keys(leadForms).forEach(function (webformId) {
    registerLeadForm(webformId, leadForms[webformId]);
  });
})();
