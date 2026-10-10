import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import { refreshChartColors } from './charts/canvas.js';
import './styles/app.css';

refreshChartColors();
createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
