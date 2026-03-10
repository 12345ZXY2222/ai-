import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';

const App: React.FC = () => {
  return (
    <Router>
      <div style={{ padding: '20px', fontFamily: 'Arial' }}>
        <h1>AI Simulation Platform - Test</h1>
        <p>If you can see this, React is working correctly.</p>
        <Routes>
          <Route path="/" element={
            <div>
              <h2>Home Page</h2>
              <p>Simple test page working.</p>
            </div>
          } />
          <Route path="/login" element={
            <div>
              <h2>Login Page</h2>
              <p>Login test page.</p>
            </div>
          } />
          <Route path="*" element={
            <div>
              <h2>404 - Page Not Found</h2>
            </div>
          } />
        </Routes>
      </div>
    </Router>
  );
};

export default App;