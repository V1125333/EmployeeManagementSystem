import type { Configuration, PopupRequest } from '@azure/msal-browser';

export const msalConfig: Configuration;
export const outlookConfigError: string | null;
export const outlookScopes: string[];
export const loginRequest: PopupRequest;
export const authRedirectUri: string;
export const popupRedirectUri: string;
export const graphBaseUrl: string;
