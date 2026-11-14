import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import { createApi } from './api';
import './styles.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode><App client={createApi()} preview={false} onExit={() => window.location.reload()}/></StrictMode>,
);

