import React from 'react';

const App: React.FC = () => {
  return (
    <div style={{ padding: '20px', fontFamily: 'Arial' }}>
      <h1>AI Simulation Platform - TEST</h1>
      <p>If you can see this, React is working correctly.</p>
      <div style={{ backgroundColor: '#e8f5e9', padding: '15px', marginTop: '20px' }}>
        <p>✅ React application is running</p>
        <p>✅ Vite development server is working</p>
        <p>✅ JavaScript execution is successful</p>
      </div>
      <div style={{ marginTop: '20px' }}>
        <h2>Next Steps:</h2>
        <ul>
          <li>Check browser console for errors</li>
          <li>Verify component imports</li>
          <li>Test API connections</li>
        </ul>
      </div>
    </div>
  );
};

export default App;