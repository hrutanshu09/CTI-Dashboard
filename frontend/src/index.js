import React from 'react';
import ReactDOM from 'react-dom/client';
import './styles/globals.css';
import App from './App';
import { BrowserRouter } from 'react-router-dom';
import { ModuleStateProvider } from './context/ModuleStateContext';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <ModuleStateProvider>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ModuleStateProvider>
  </React.StrictMode>
);
