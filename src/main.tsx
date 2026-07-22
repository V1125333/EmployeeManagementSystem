import React from 'react';
import ReactDOM from 'react-dom/client';
import { PublicClientApplication } from '@azure/msal-browser';
import { MsalProvider } from '@azure/msal-react';
import App from './App';
import { msalConfig } from './authConfig';
import './index.css';
import './styles/theme.css';

const msalInstance = new PublicClientApplication(msalConfig);
const root = ReactDOM.createRoot(document.getElementById('root')!);

function MsalStartupError() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-warm-bg px-4">
      <div className="rounded-xl border border-status-error/20 bg-warm-card p-6 text-center shadow-card-md">
        <h1 className="text-lg font-bold text-[var(--color-brand-navy)]">Microsoft authentication unavailable</h1>
        <p className="mt-2 text-sm text-status-error">MSAL could not initialize. Check the browser console and reload the page.</p>
      </div>
    </div>
  );
}

async function startApp() {
  try {
    await msalInstance.initialize();
  } catch (error) {
    console.error('Could not initialize Microsoft authentication.', error);
    root.render(<MsalStartupError />);
    return;
  }

  try {
    const redirectResult = await msalInstance.handleRedirectPromise();
    const account = redirectResult?.account ?? msalInstance.getAllAccounts()[0];
    if (account) msalInstance.setActiveAccount(account);
    if (redirectResult?.account && window.location.pathname === '/auth/callback') {
      window.history.replaceState(null, '', '/settings');
    }
  } catch (error) {
    // A stale redirect response must not trigger another login or block the app.
    console.error('Could not process the Microsoft redirect response.', error);
  }

  root.render(
    <React.StrictMode>
      <MsalProvider instance={msalInstance}>
        <App />
      </MsalProvider>
    </React.StrictMode>
  );
}

void startApp();
