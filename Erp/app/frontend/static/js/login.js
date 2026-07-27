'use strict';

const HOME = { SUPER_ADMIN: '/admin', STAFF: '/staff', PATIENT: '/portal' };

/* already signed in? go straight home */
api('/api/auth/me').then(me => { location.href = HOME[me.role] || '/'; }).catch(() => {});

$('#login-form').addEventListener('submit', async e => {
  e.preventDefault();
  const btn = $('#login-btn');
  btn.disabled = true; btn.textContent = 'Signing in…';
  try {
    const data = await api('/api/auth/login', { method: 'POST', body: formData(e.target) });
    SFX.success();
    location.href = HOME[data.user.role] || '/';
  } catch (err) {
    toast(err.message, 'err');
    btn.disabled = false; btn.textContent = 'Sign in';
  }
});
