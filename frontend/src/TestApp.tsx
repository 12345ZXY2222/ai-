import React from 'react';

const TestApp: React.FC = () => {
  return (
    <div style={{ padding: '40px', fontFamily: 'Arial, sans-serif' }}>
      <h1>AI Simulation Platform - Test Page</h1>
      <p>If you can see this, React is working correctly.</p>
      <div style={{ marginTop: '20px', padding: '20px', backgroundColor: '#f0f0f0', borderRadius: '8px' }}>
        <h3>System Status:</h3>
        <ul>
          <li>✅ React is running</li>
          <li>✅ Basic rendering works</li>
          <li>✅ CSS styling works</li>
        </ul>
      </div>
      <div style={{ marginTop: '30px' }}>
        <h3>Next Steps:</h3>
        <p>If this page shows correctly but the main app doesn't work, there's likely an error in one of the components.</p>
        <button 
          onClick={() => alert('JavaScript is working!')}
          style={{ padding: '10px 20px', backgroundColor: '#1890ff', color: 'white', border: 'none', borderRadius: '4px' }}
        >
          Test JavaScript
        </button>
      </div>
    </div>
  );
};

export default TestApp;