import React, { useEffect } from 'react';

const TestApp: React.FC = () => {
  useEffect(() => {
    console.log('TestApp mounted successfully');
    alert('React is working! If you see this alert, JavaScript is executing.');
  }, []);

  return (
    <div style={{ 
      padding: '40px', 
      fontFamily: 'Arial, sans-serif',
      backgroundColor: 'white',
      minHeight: '100vh'
    }}>
      <h1 style={{ color: 'green', fontSize: '2em' }}>✅ React Test Successful</h1>
      <p>This is a pure React component with no external dependencies.</p>
      <div style={{ 
        marginTop: '20px', 
        padding: '20px', 
        border: '2px solid blue',
        borderRadius: '8px',
        backgroundColor: '#f0f8ff'
      }}>
        <h2>Debug Information:</h2>
        <ul>
          <li>React version: {React.version}</li>
          <li>Current time: {new Date().toLocaleString()}</li>
          <li>Window location: {window.location.href}</li>
          <li>User agent: {navigator.userAgent}</li>
        </ul>
      </div>
      <div style={{ 
        marginTop: '30px',
        padding: '15px',
        backgroundColor: '#ffeb3b',
        border: '2px solid #ff9800'
      }}>
        <h3>If you can see this yellow box, React is rendering correctly.</h3>
        <p>The page should not be blank. If it is, check browser console for errors (F12).</p>
      </div>
    </div>
  );
};

export default TestApp;