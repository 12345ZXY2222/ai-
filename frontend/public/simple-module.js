console.log('Simple module script loaded');

document.addEventListener('DOMContentLoaded', () => {
  console.log('DOM loaded, adding content');
  const root = document.getElementById('root');
  if (root) {
    root.innerHTML = '<h1>SIMPLE MODULE JS</h1><p>If you see this, plain JS modules work.</p>';
  }
});