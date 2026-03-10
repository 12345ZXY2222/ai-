// AI Simulation Platform Main Entry
import React from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

console.log('AI Simulation Platform starting...');

const rootElement = document.getElementById('root')
if (rootElement) {
  console.log('Root element found, rendering AI Simulation Platform...');
  const root = createRoot(rootElement);
  root.render(<App />);
  console.log('AI Simulation Platform render completed');
} else {
  console.error('Root element not found');
}