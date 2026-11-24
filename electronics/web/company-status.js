(() => {
  const slug = document.body.dataset.companyPath.split('/').filter(Boolean)[0];
  const wasOnline = document.body.dataset.companyOffline !== 'true';
  const button = document.getElementById('company-status-check');
  const message = document.getElementById('company-status-message');
  const checkedAt = document.getElementById('company-status-time');
  let timer, pending = false, stopped = false;

  async function checkStatus() {
    clearTimeout(timer);
    if (pending || stopped || document.hidden) return;
    pending = true;
    if (button) button.disabled = true;
    try {
      const response = await fetch('/api/companies/' + slug + '/status', {
        cache: 'no-store', signal: AbortSignal.timeout(8000),
      });
      if (!response.ok) throw new Error('Status belum tersedia.');
      const data = await response.json();
      if (typeof data.online !== 'boolean') throw new Error('Status belum tersedia.');
      if (stopped) return;
      if (data.online !== wasOnline) {
        stopped = true;
        location.reload();
        return;
      }
      if (message) message.textContent = 'Perusahaan masih offline. Halaman akan terbuka kembali saat perusahaan aktif.';
      if (checkedAt) checkedAt.textContent = 'Diperiksa pukul ' + new Intl.DateTimeFormat('id-ID', {
        hour: '2-digit', minute: '2-digit', second: '2-digit',
      }).format(new Date()) + ' · Hari simulasi ' + data.day;
    } catch {
      if (message && !stopped) message.textContent = 'Status layanan belum dapat diperiksa. Silakan coba kembali beberapa saat lagi.';
    } finally {
      pending = false;
      if (button) button.disabled = false;
      if (!stopped && !document.hidden) timer = setTimeout(checkStatus, 3000);
    }
  }
  button?.addEventListener('click', checkStatus);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) clearTimeout(timer);
    else checkStatus();
  });
  window.addEventListener('pagehide', () => {
    stopped = true;
    clearTimeout(timer);
  });
  window.addEventListener('pageshow', event => {
    if (event.persisted) {
      stopped = false;
      checkStatus();
    }
  });
  checkStatus();
})();
