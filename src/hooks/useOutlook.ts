import { useCallback, useEffect, useRef, useState } from 'react';
import { BrowserAuthErrorCodes, InteractionStatus, type AccountInfo } from '@azure/msal-browser';
import { useMsal } from '@azure/msal-react';
import { authRedirectUri, graphBaseUrl, loginRequest, outlookConfigError, popupRedirectUri } from '@/authConfig';

export interface OutlookMessage {
  id: string;
  subject?: string;
  bodyPreview?: string;
  receivedDateTime?: string;
  isRead?: boolean;
  from?: { emailAddress?: { name?: string; address?: string } };
}

export interface OutlookEvent {
  id: string;
  subject?: string;
  start?: { dateTime?: string; timeZone?: string };
  end?: { dateTime?: string; timeZone?: string };
  location?: { displayName?: string };
  webLink?: string;
}

interface GraphCollection<T> {
  value: T[];
  '@odata.nextLink'?: string;
}

interface SendMailInput {
  to: string | string[];
  subject: string;
  body: string;
}

function getErrorMessage(error: unknown) {
  if ((error as { errorCode?: string })?.errorCode === BrowserAuthErrorCodes.interactionInProgress) {
    return 'A Microsoft sign-in window is already open. Finish or close it before trying again.';
  }
  if (error instanceof Error) return error.message;
  return 'An unexpected Outlook error occurred.';
}

export function useOutlook() {
  const { instance, accounts, inProgress } = useMsal();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [account, setAccount] = useState<AccountInfo | null>(
    () => instance.getActiveAccount() ?? accounts[0] ?? null,
  );
  const interactionLock = useRef(false);

  useEffect(() => {
    setAccount(instance.getActiveAccount() ?? accounts[0] ?? null);
  }, [accounts, instance]);

  const assertInteractionAvailable = useCallback(() => {
    if (interactionLock.current || inProgress !== InteractionStatus.None) {
      const interactionError = new Error('A Microsoft sign-in window is already open. Finish or close it before trying again.');
      Object.assign(interactionError, { errorCode: BrowserAuthErrorCodes.interactionInProgress });
      throw interactionError;
    }
  }, [inProgress]);

  const run = useCallback(async <T,>(operation: () => Promise<T>): Promise<T> => {
    setLoading(true);
    setError(null);
    try {
      return await operation();
    } catch (caught) {
      console.error('Outlook/MSAL operation failed.', caught);
      const message = getErrorMessage(caught);
      setError(message);
      throw caught;
    } finally {
      setLoading(false);
    }
  }, []);

  const connect = useCallback(async () => {
    if (outlookConfigError) {
      console.error('Outlook/MSAL configuration failed.', outlookConfigError);
      setError(outlookConfigError);
      throw new Error(outlookConfigError);
    }

    return run(async () => {
      assertInteractionAvailable();
      interactionLock.current = true;
      try {
        await instance.loginRedirect({
          ...loginRequest,
          redirectUri: authRedirectUri,
        });
      } finally {
        interactionLock.current = false;
      }
    });
  }, [assertInteractionAvailable, instance, run]);

  const disconnect = useCallback(async () => {
    if (!account) return;
    return run(async () => {
      assertInteractionAvailable();
      interactionLock.current = true;
      try {
        await instance.logoutPopup({
          account,
          postLogoutRedirectUri: `${window.location.origin}/settings`,
          mainWindowRedirectUri: `${window.location.origin}/settings`,
        });
        setAccount(null);
      } finally {
        interactionLock.current = false;
      }
    });
  }, [account, assertInteractionAvailable, instance, run]);

  const acquireToken = useCallback(async () => {
    if (outlookConfigError) throw new Error(outlookConfigError);
    if (!account) throw new Error('Connect Outlook before using Microsoft Graph.');

    try {
      const response = await instance.acquireTokenSilent({ ...loginRequest, account });
      return response.accessToken;
    } catch (silentError) {
      console.warn('Silent Outlook token acquisition failed; opening a Microsoft sign-in popup.', silentError);
      assertInteractionAvailable();
      interactionLock.current = true;
      try {
        const response = await instance.acquireTokenPopup({
          ...loginRequest,
          account,
          redirectUri: popupRedirectUri,
        });
        instance.setActiveAccount(response.account);
        setAccount(response.account);
        return response.accessToken;
      } finally {
        interactionLock.current = false;
      }
    }
  }, [account, assertInteractionAvailable, instance]);

  const graphRequest = useCallback(async <T,>(path: string, init?: RequestInit): Promise<T> => {
    const accessToken = await acquireToken();
    const response = await fetch(`${graphBaseUrl}${path}`, {
      ...init,
      headers: {
        Authorization: `Bearer ${accessToken}`,
        ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
        ...init?.headers,
      },
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(payload?.error?.message || `Microsoft Graph request failed (${response.status}).`);
    }

    if (response.status === 202 || response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  }, [acquireToken]);

  const getMessages = useCallback(() => run(async () => {
    const query = new URLSearchParams({
      '$top': '50',
      '$select': 'id,subject,bodyPreview,receivedDateTime,isRead,from',
      '$orderby': 'receivedDateTime desc',
    });
    const response = await graphRequest<GraphCollection<OutlookMessage>>(`/me/messages?${query}`);
    return response.value;
  }), [graphRequest, run]);

  const getEvents = useCallback(() => run(async () => {
    const start = new Date();
    const end = new Date(start);
    end.setMonth(end.getMonth() + 3);
    const query = new URLSearchParams({
      startDateTime: start.toISOString(),
      endDateTime: end.toISOString(),
      '$top': '50',
      '$select': 'id,subject,start,end,location,webLink',
      '$orderby': 'start/dateTime',
    });
    const response = await graphRequest<GraphCollection<OutlookEvent>>(`/me/calendarView?${query}`);
    return response.value;
  }), [graphRequest, run]);

  const sendMail = useCallback((mail: SendMailInput) => run(async () => {
    const recipients = (Array.isArray(mail.to) ? mail.to : [mail.to])
      .map((address) => address.trim())
      .filter(Boolean)
      .map((address) => ({ emailAddress: { address } }));

    if (!recipients.length) throw new Error('At least one recipient is required.');

    await graphRequest<void>('/me/sendMail', {
      method: 'POST',
      body: JSON.stringify({
        message: {
          subject: mail.subject,
          body: { contentType: 'HTML', content: mail.body },
          toRecipients: recipients,
        },
        saveToSentItems: true,
      }),
    });
  }), [graphRequest, run]);

  return {
    connect,
    disconnect,
    isConnected: Boolean(account),
    account,
    loading: loading || inProgress !== InteractionStatus.None,
    error,
    getMessages,
    getEvents,
    sendMail,
  };
}
