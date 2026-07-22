import { LogLevel } from '@azure/msal-browser';

const clientId = import.meta.env.VITE_AZURE_CLIENT_ID?.trim() || '';
const tenantId = import.meta.env.VITE_AZURE_TENANT_ID?.trim() || '';
const redirectUri = import.meta.env.VITE_AZURE_REDIRECT_URI?.trim() || '';

export const outlookConfigError = !clientId || !tenantId || !redirectUri
  ? 'Outlook is not configured. Add VITE_AZURE_CLIENT_ID, VITE_AZURE_TENANT_ID, and VITE_AZURE_REDIRECT_URI to the root .env file, then restart Vite.'
  : null;

export const msalConfig = {
  auth: {
    clientId,
    authority: `https://login.microsoftonline.com/${tenantId}`,
    redirectUri,
    navigateToLoginRequestUrl: false,
  },
  cache: {
    cacheLocation: 'sessionStorage',
    storeAuthStateInCookie: false,
  },
  system: {
    windowHashTimeout: 60000,
    iframeHashTimeout: 60000,
    loadFrameTimeout: 60000,
    navigateFrameWait: 500,
    loggerOptions: {
      logLevel: LogLevel.Verbose,
      piiLoggingEnabled: false,
      loggerCallback: (level, message, containsPii) => {
        if (containsPii) return;
        if (level === LogLevel.Error) console.error(`[MSAL] ${message}`);
        else if (level === LogLevel.Warning) console.warn(`[MSAL] ${message}`);
        else if (level === LogLevel.Info) console.info(`[MSAL] ${message}`);
        else console.log(`[MSAL] ${message}`);
      },
    },
  },
};

export const outlookScopes = [
  'User.Read',
  'Mail.Read',
  'Mail.Send',
  'Calendars.ReadWrite',
];

export const loginRequest = {
  scopes: outlookScopes,
};

export const authRedirectUri = redirectUri;
export const popupRedirectUri = `${window.location.origin}/blank.html`;

export const graphBaseUrl = 'https://graph.microsoft.com/v1.0';
