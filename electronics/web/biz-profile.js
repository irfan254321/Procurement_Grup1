const motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)');

if (!motionPreference.matches && 'IntersectionObserver' in window && typeof Element.prototype.animate === 'function') {
  const reveal = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      reveal.unobserve(entry.target);
      if (motionPreference.matches || entry.target.contains(document.activeElement)) continue;
      entry.target.animate(
        [{ opacity: 0.55, transform: 'translateY(18px)' }, { opacity: 1, transform: 'translateY(0)' }],
        { duration: 500, easing: 'cubic-bezier(.2,.65,.3,1)' },
      );
    }
  }, { threshold: 0.18 });
  document.querySelectorAll('[data-reveal]').forEach(section => reveal.observe(section));
}

const chapters = [...document.querySelectorAll('.chapter-nav a')].map(link => ({
  link,
  section: document.getElementById(link.hash.slice(1)),
}));
const header = document.querySelector('.site-header');
let activeChapter = chapters[0];
let scrollFrame = 0;

function updateChapter() {
  scrollFrame = 0;
  if (document.getElementById('profil').hidden) return;
  const readingLine = Math.max(window.innerHeight * 0.4, header.offsetHeight + 48);
  const chapter = chapters.findLast(item => item.section.getBoundingClientRect().top < readingLine) ?? chapters[0];
  if (chapter === activeChapter) return;
  activeChapter.link.removeAttribute('aria-current');
  chapter.link.setAttribute('aria-current', 'location');
  activeChapter = chapter;
}

function scheduleChapterUpdate() {
  if (!scrollFrame) scrollFrame = requestAnimationFrame(updateChapter);
}

window.addEventListener('scroll', scheduleChapterUpdate, { passive: true });
window.addEventListener('resize', scheduleChapterUpdate);
window.addEventListener('hashchange', scheduleChapterUpdate);
window.addEventListener('load', scheduleChapterUpdate);
scheduleChapterUpdate();
