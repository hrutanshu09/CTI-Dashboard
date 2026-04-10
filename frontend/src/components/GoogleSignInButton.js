import React, { useEffect, useRef } from 'react';

const GOOGLE_SCRIPT_SRC = 'https://accounts.google.com/gsi/client';

const loadGoogleScript = () =>
  new Promise((resolve, reject) => {
    if (window.google?.accounts?.id) {
      resolve();
      return;
    }

    const existing = document.querySelector(`script[src="${GOOGLE_SCRIPT_SRC}"]`);
    if (existing) {
      existing.addEventListener('load', resolve, { once: true });
      existing.addEventListener('error', reject, { once: true });
      return;
    }

    const script = document.createElement('script');
    script.src = GOOGLE_SCRIPT_SRC;
    script.async = true;
    script.defer = true;
    script.onload = resolve;
    script.onerror = reject;
    document.body.appendChild(script);
  });

const GoogleSignInButton = ({ clientId, onCredential, onError }) => {
  const buttonRef = useRef(null);

  useEffect(() => {
    let active = true;

    const renderGoogleButton = async () => {
      try {
        await loadGoogleScript();
        if (!active || !window.google?.accounts?.id || !buttonRef.current) return;

        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: (response) => {
            if (response?.credential) {
              onCredential(response.credential);
            } else {
              onError?.('Google sign-in did not return a credential.');
            }
          },
        });

        buttonRef.current.innerHTML = '';
        window.google.accounts.id.renderButton(buttonRef.current, {
          theme: 'filled_black',
          size: 'large',
          text: 'continue_with',
          shape: 'pill',
          width: 280,
        });
      } catch {
        onError?.('Unable to load Google sign-in.');
      }
    };

    if (clientId) {
      renderGoogleButton();
    }

    return () => {
      active = false;
    };
  }, [clientId, onCredential, onError]);

  return <div ref={buttonRef} className="min-h-[40px]" />;
};

export default GoogleSignInButton;
