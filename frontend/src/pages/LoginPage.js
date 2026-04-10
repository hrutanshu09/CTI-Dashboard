import React, { useState } from 'react';
import { ShieldCheck } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import GoogleSignInButton from '../components/GoogleSignInButton';

const LoginPage = () => {
  const { signInWithGoogleCredential } = useAuth();
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const googleClientId = process.env.REACT_APP_GOOGLE_CLIENT_ID || '';

  const handleCredential = async (credential) => {
    setError('');
    setIsSubmitting(true);
    try {
      await signInWithGoogleCredential(credential);
    } catch (err) {
      const message = err?.response?.data?.detail || 'Sign-in failed. Please try again.';
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-white flex items-center justify-center px-4">
      <div className="w-full max-w-md bg-panel border border-border rounded-2xl p-8 shadow-2xl">
        <div className="flex items-center gap-3 mb-6">
          <div className="h-11 w-11 rounded-lg bg-blue-500/20 flex items-center justify-center">
            <ShieldCheck className="text-blue-300" size={22} />
          </div>
          <div>
            <h1 className="brand-font text-xl font-bold">FlashCTI</h1>
            <p className="text-sm text-gray-400">Secure sign-in for your CTI workspace</p>
          </div>
        </div>

        <p className="text-sm text-gray-300 mb-5">
          Continue with your Google account to sign in or create your account.
        </p>

        {!googleClientId && (
          <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded-md p-3 mb-4">
            Missing `REACT_APP_GOOGLE_CLIENT_ID` in frontend environment.
          </div>
        )}

        <GoogleSignInButton
          clientId={googleClientId}
          onCredential={handleCredential}
          onError={setError}
        />

        {isSubmitting && <p className="text-xs text-blue-300 mt-3">Signing you in...</p>}
        {error && <p className="text-sm text-red-300 mt-3">{error}</p>}
      </div>
    </div>
  );
};

export default LoginPage;
