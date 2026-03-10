// Test minimal React app
import React from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import TestApp from './App.test-minimal.tsx'

console.log('Test minimal app starting...');

const rootElement = document.getElementById('root')
if (rootElement) {
  console.log('Root element found, rendering test app...');
  const root = createRoot(rootElement);
  root.render(<TestApp />);
  console.log('Test app render completed');
} else {
  console.error('Root element not found');
}