import { useEffect, useRef } from "react";

import { GOOGLE_CLIENT_ID } from "@/config";

/**
 * Self-contained Google Identity Services button.
 *
 * We load the GIS script ourselves with `?hl=<locale>` because that query
 * param is the only reliable way to set the button's language — GIS otherwise
 * renders it in the signed-in Google account's language and ignores the
 * per-button `locale` option (which is why it showed up in Vietnamese on an
 * English UI). Returns the ID-token `credential` for the backend to verify.
 */

type GsiId = {
  initialize: (config: {
    client_id: string;
    callback: (resp: { credential?: string }) => void;
  }) => void;
  renderButton: (parent: HTMLElement, options: Record<string, unknown>) => void;
};

declare global {
  interface Window {
    google?: { accounts: { id: GsiId } };
  }
}

const SCRIPT_ID = "gsi-client";

function loadGsi(locale: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const src = `https://accounts.google.com/gsi/client?hl=${encodeURIComponent(locale)}`;
    const existing = document.getElementById(SCRIPT_ID) as HTMLScriptElement | null;
    if (existing) {
      if (existing.src === src && window.google?.accounts?.id) return resolve();
      existing.remove(); // locale changed — reload with the new hl
    }
    const s = document.createElement("script");
    s.id = SCRIPT_ID;
    s.src = src;
    s.async = true;
    s.defer = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("Failed to load Google script"));
    document.head.appendChild(s);
  });
}

interface Props {
  locale: string;
  text?: "continue_with" | "signup_with" | "signin_with";
  onCredential: (credential: string) => void;
  onError?: () => void;
}

export function GoogleButton({ locale, text = "continue_with", onCredential, onError }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const onCredentialRef = useRef(onCredential);
  onCredentialRef.current = onCredential;
  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return;
    let cancelled = false;

    loadGsi(locale)
      .then(() => {
        if (cancelled || !ref.current || !window.google?.accounts?.id) return;
        window.google.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: (resp) => {
            if (resp.credential) onCredentialRef.current(resp.credential);
            else onErrorRef.current?.();
          },
        });
        ref.current.innerHTML = "";
        window.google.accounts.id.renderButton(ref.current, {
          type: "standard",
          theme: "outline",
          size: "large",
          text,
          shape: "rectangular",
          width: 352,
          locale,
        });
      })
      .catch(() => onErrorRef.current?.());

    return () => {
      cancelled = true;
    };
  }, [locale, text]);

  return <div ref={ref} className="flex justify-center" />;
}
