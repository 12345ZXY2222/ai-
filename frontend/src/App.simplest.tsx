import React from 'react';

const App: React.FC = () => {
  return (
    <div style={{ padding: '20px', fontFamily: 'Arial' }}>
      <h1>REACT SIMPLEST TEST</h1>
      <p>If you see this, React is working with Vite.</p>
      <div style={{ backgroundColor: '#e8f5e9', padding: '15px', marginTop: '20px' }}>
        <p>✅ React component rendered</p>
        <p>✅ Vite development server working</p>
        <p>✅ No external dependencies</p>
      </div>
    </div>
  );
};

export default App;