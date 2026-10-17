'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const region = $('auth-controls');
  if (!region) return;
  const buttonHost = $('google-signin-button');
  const retry = $('google-signin-retry');
  const logout = $('google-logout');
  const status = $('auth-status');
  let state = {authenticated: false, enabled: false};
  let csrf = '';
  let nonce = '';
  let sdkPromise = null;
  let busy = false;
  let initializedNonce = '';

  async function api(path, payload) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch(path, {
        method: payload === undefined ? 'GET' : 'POST',
        headers: payload === undefined ? {} : {'Content-Type': 'application/json', 'X-CSRF-Token': csrf},
        body: payload === undefined ? undefined : JSON.stringify(payload), signal: controller.signal
      });
      const result = await response.json();
      if (!response.ok) { const error = Error(result.error || 'Sign-in is unavailable. Please try again.'); error.status = response.status; throw error; }
      return result;
    } catch (error) {
      if (error.name === 'AbortError') throw Error('Sign-in took too long. Please try again.');
      throw error;
    } finally { clearTimeout(timeout); }
  }

  function rememberLogout(value) {
    try {
      if (value) sessionStorage.setItem('tmrceo-google-logout', '1');
      else sessionStorage.removeItem('tmrceo-google-logout');
    } catch {}
  }
  function promptAllowed() {
    try { return !sessionStorage.getItem('tmrceo-google-logout'); } catch { return true; }
  }
  function emit(action) {
    document.dispatchEvent(new CustomEvent('tmrceo:auth-change', {detail: {authenticated: state.authenticated, user: state.user || null, action}}));
  }
  function publish(action) {
    try { localStorage.setItem('tmrceo-auth-change', JSON.stringify({action, at: Date.now()})); } catch {}
  }
  function render() {
    logout.hidden = !state.authenticated;
    buttonHost.hidden = state.authenticated || !state.enabled;
    retry.hidden = true;
    status.textContent = '';
  }
  function loadGoogle() {
    if (window.google?.accounts?.id) return Promise.resolve(window.google.accounts.id);
    if (sdkPromise) return sdkPromise;
    sdkPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      const timeout = setTimeout(() => {script.remove(); sdkPromise = null; reject(Error('Google sign-in could not load. You can still play as a guest.'));}, 10000);
      script.src = 'https://accounts.google.com/gsi/client';
      script.async = true;
      script.onload = () => {
        clearTimeout(timeout);
        if (window.google?.accounts?.id) resolve(window.google.accounts.id);
        else {sdkPromise = null; reject(Error('Google sign-in is unavailable. Please try again.'));}
      };
      script.onerror = () => {clearTimeout(timeout); script.remove(); sdkPromise = null; reject(Error('Google sign-in could not load. You can still play as a guest.'));};
      document.head.appendChild(script);
    });
    return sdkPromise;
  }

  async function credentialReceived(response) {
    if (busy || state.authenticated || !response?.credential) return;
    busy = true;
    document.dispatchEvent(new Event('snake:name-edit'));
    status.textContent = 'Checking your Google sign-in…';
    try {
      const result = await api('/api/auth/google', {credential: response.credential});
      state = {...state, ...result};
      csrf = result.csrf_token;
      rememberLogout(false);
      window.google?.accounts?.id.cancel();
      render();
      status.textContent = '';
      emit('login');
      publish('login');
    } catch (error) {
      status.textContent = error.message || 'Sign-in failed. Please try again.';
      if ([400, 401, 403, 409].includes(error.status)) {
        retry.textContent = 'Refresh sign-in';
        retry.dataset.refresh = 'true';
        retry.hidden = false;
      }
    } finally { busy = false; }
  }

  async function setupGoogle(allowPrompt) {
    if (state.authenticated || !state.enabled) return;
    try {
      const gis = await loadGoogle();
      if (state.authenticated) return;
      if (!promptAllowed()) gis.disableAutoSelect();
      if (initializedNonce !== nonce) {
        gis.initialize({client_id: state.client_id, callback: credentialReceived, nonce, auto_select: false, use_fedcm_for_button: true, context: 'signin'});
        initializedNonce = nonce;
      }
      buttonHost.replaceChildren();
      gis.renderButton(buttonHost, {type: 'standard', theme: 'outline', size: 'medium', text: 'signin_with', shape: 'pill', width: 220});
      if (allowPrompt && promptAllowed()) gis.prompt();
    } catch (error) {
      status.textContent = error.message || 'Google sign-in could not load. Guest play still works.';
      retry.textContent = 'Retry Google sign-in';
      delete retry.dataset.refresh;
      retry.hidden = false;
    }
  }

  async function loadSession(action) {
    const previous = state.authenticated;
    try {
      const result = await api('/api/auth/session');
      state = result;
      csrf = result.csrf_token || '';
      nonce = result.nonce || '';
      render();
      if (!result.enabled) status.textContent = 'Google sign-in is unavailable right now. Guest play still works.';
      if (previous && !state.authenticated) {
        rememberLogout(true);
        window.google?.accounts?.id.disableAutoSelect();
        window.google?.accounts?.id.cancel();
      }
      if (action) emit(previous && !state.authenticated ? 'logout' : action);
      if (!state.authenticated && state.enabled) setupGoogle(!action);
      return state;
    } catch {
      status.textContent = 'Sign-in could not be reached. You can still play as a guest.';
      retry.hidden = false;
      retry.textContent = 'Retry Google sign-in';
      return state;
    }
  }

  retry.addEventListener('click', () => {
    if (retry.dataset.refresh) { location.reload(); return; }
    if (!state.enabled || !nonce) loadSession();
    else setupGoogle(false);
  });
  logout.addEventListener('click', async () => {
    if (busy) return;
    busy = true;
    logout.disabled = true;
    try {
      await api('/api/auth/logout', {});
      rememberLogout(true);
      window.google?.accounts?.id.disableAutoSelect();
      window.google?.accounts?.id.cancel();
      state = {authenticated: false, enabled: state.enabled};
      render();
      emit('logout');
      publish('logout');
      status.textContent = 'You’re logged out. You can keep playing as a guest.';
      await loadSession();
    } catch (error) {
      status.textContent = error.message || 'Logout failed. Please try again.';
      if (error.status === 401) await loadSession('logout');
    } finally { busy = false; logout.disabled = false; }
  });
  window.addEventListener('storage', event => {
    if (event.key === 'tmrceo-auth-change') loadSession('sync');
  });
  const ready = loadSession();
  window.tmrceoAuth = {ready, get authenticated() {return state.authenticated;}, get csrfToken() {return csrf;}};
})();
