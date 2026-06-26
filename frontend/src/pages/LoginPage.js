import React, { useState } from 'react';
import { LogIn, ShieldCheck, UserPlus } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const LoginPage = () => {
  const { login, signup } = useAuth();
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({ name: '', email: '', password: '' });
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setIsSubmitting(true);
    try {
      if (mode === 'signup') {
        await signup(form);
      } else {
        await login({ email: form.email, password: form.password });
      }
    } catch (err) {
      const message = err?.response?.data?.detail || 'Authentication failed. Please try again.';
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const isSignup = mode === 'signup';

  return (
    <div className="min-h-screen bg-background text-white flex items-center justify-center px-4">
      <div className="w-full max-w-md bg-panel border border-border rounded-lg p-8 shadow-2xl">
        <div className="flex items-center gap-3 mb-6">
          <div className="h-11 w-11 rounded-lg bg-blue-500/20 flex items-center justify-center">
            <ShieldCheck className="text-blue-300" size={22} />
          </div>
          <div>
            <h1 className="brand-font text-xl font-bold">FlashCTI</h1>
            <p className="text-sm text-gray-400">Secure sign-in for your CTI workspace</p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 mb-6 rounded-lg bg-background/70 p-1 border border-border">
          <button
            type="button"
            onClick={() => {
              setMode('login');
              setError('');
            }}
            className={`h-10 rounded-md text-sm font-medium flex items-center justify-center gap-2 transition ${
              !isSignup ? 'bg-blue-500 text-white' : 'text-gray-300 hover:bg-white/5'
            }`}
          >
            <LogIn size={16} />
            Login
          </button>
          <button
            type="button"
            onClick={() => {
              setMode('signup');
              setError('');
            }}
            className={`h-10 rounded-md text-sm font-medium flex items-center justify-center gap-2 transition ${
              isSignup ? 'bg-blue-500 text-white' : 'text-gray-300 hover:bg-white/5'
            }`}
          >
            <UserPlus size={16} />
            Sign up
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {isSignup && (
            <div>
              <label className="block text-xs font-semibold text-gray-400 mb-2" htmlFor="name">
                Name
              </label>
              <input
                id="name"
                name="name"
                value={form.name}
                onChange={handleChange}
                className="w-full h-11 rounded-md bg-background border border-border px-3 text-sm text-white outline-none focus:border-blue-400"
                placeholder="Your name"
              />
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-gray-400 mb-2" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              name="email"
              type="email"
              value={form.email}
              onChange={handleChange}
              className="w-full h-11 rounded-md bg-background border border-border px-3 text-sm text-white outline-none focus:border-blue-400"
              placeholder="analyst@example.com"
              autoComplete="email"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-400 mb-2" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              value={form.password}
              onChange={handleChange}
              className="w-full h-11 rounded-md bg-background border border-border px-3 text-sm text-white outline-none focus:border-blue-400"
              placeholder="Minimum 6 characters"
              autoComplete={isSignup ? 'new-password' : 'current-password'}
              required
              minLength={6}
            />
          </div>

          {error && (
            <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded-md p-3">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full h-11 rounded-md bg-blue-500 hover:bg-blue-400 disabled:opacity-60 disabled:hover:bg-blue-500 text-white text-sm font-semibold flex items-center justify-center gap-2 transition"
          >
            {isSignup ? <UserPlus size={17} /> : <LogIn size={17} />}
            {isSubmitting ? 'Please wait...' : isSignup ? 'Create account' : 'Login'}
          </button>
        </form>
      </div>
    </div>
  );
};

export default LoginPage;
