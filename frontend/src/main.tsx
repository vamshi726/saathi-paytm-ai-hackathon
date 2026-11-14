import { StrictMode, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ClerkProvider, SignInButton, UserButton, useAuth } from '@clerk/react';
import { App } from './App';
import { createApi } from './api';
import { createPreview } from './preview';
import type { Client } from './types';
import './styles.css';

function Launcher({ getToken, clerkControls }: { getToken?: () => Promise<string | null>; clerkControls?: React.ReactNode }) {
  const [token, setToken] = useState('');
  const [connection, setConnection] = useState<{ client: Client; preview: boolean } | null>(null);
  if (connection) return <App client={connection.client} preview={connection.preview} onExit={() => { setConnection(null); setToken(''); }}/>;
  return <div className="login-wrap"><section className="login panel"><div className="brand"><span className="brand-mark">s</span>saathi<span className="brand-dot">●</span></div>
    <p className="eyebrow">PAYMENT SUPPORT, WITH CONTEXT</p><h1>A teammate you can follow.</h1><p>Open the support workspace to investigate a case, review its evidence and see what happens next.</p>
    <div className="notice">Synthetic payment data only. No Paytm production connection or real money movement.</div>
    <form onSubmit={e => { e.preventDefault(); if (token.trim()) { const secret = token.trim(); setConnection({ client: createApi(async () => secret), preview: false }); setToken(''); } }}>
      <label htmlFor="token">Local demo bearer token</label><input id="token" type="password" autoComplete="off" value={token} onChange={e => setToken(e.target.value)} placeholder="Your backend demo token" required/>
      <p className="fine">Kept in memory for this connection only. Use the token configured on your local API.</p><button className="full" disabled={!token.trim()}>Connect to local backend ↗</button>
    </form>
    {clerkControls}{getToken && <button className="secondary full" onClick={() => setConnection({ client: createApi(getToken), preview: false })}>Connect with Clerk session</button>}
    <div className="separator">EXPLORE THE INTERFACE</div><button className="secondary full" onClick={() => { let storage: Storage | undefined; try { storage = sessionStorage; } catch { /* memory-only */ } setConnection({ client: createPreview(storage), preview: true }); }}>Open UI rehearsal</button>
    <p className="fine">Five primary scenarios + refund-history variant. Browser-only simulation; not a completed backend workflow or evaluation.</p>
  </section></div>;
}
function ClerkLauncher() {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const provider = useMemo(() => () => getToken(), [getToken]);
  return <Launcher getToken={isLoaded && isSignedIn ? provider : undefined} clerkControls={<div className="clerk-controls">{isSignedIn ? <UserButton/> : <SignInButton mode="modal"><button className="secondary full">Sign in with Clerk</button></SignInButton>}<p className="fine">Clerk sign-in requires backend JWT verification. The current local API accepts only its configured demo token.</p></div>}/>;
}
const key = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;
createRoot(document.getElementById('root')!).render(<StrictMode>{key ? <ClerkProvider publishableKey={key}><ClerkLauncher/></ClerkProvider> : <Launcher/>}</StrictMode>);

