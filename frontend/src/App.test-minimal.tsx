// Minimal test app to verify React works
import React from 'react';

const TestApp: React.FC = () => {
  return (
    <div style={{ padding: '20px', fontFamily: 'Arial, sans-serif' }}>
      <h1 style={{ color: 'green' }}>✅ AI Simulation Platform Test</h1>
      <p>If you see this, React is working correctly with the actual App.tsx.</p>
      <div style={{ backgroundColor: '#f0f0f0', padding: '10px', marginTop: '10px' }}>
        <p><strong>Test Status:</strong> React Components loading successfully</p>
        <p><strong>Check:</strong> This confirms the main App.tsx should work</p>
      </div>
    </div>
  );
};

export default TestApp;