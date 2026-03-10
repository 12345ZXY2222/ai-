import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';

const HomePage: React.FC = () => {
  return React.createElement('div', { style: { padding: '20px' } }, 
    React.createElement('h1', null, 'AI Simulation Platform - No JSX Test'),
    React.createElement('p', null, 'If you can see this, React is working without JSX.'),
    React.createElement('div', { style: { backgroundColor: '#e8f5e9', padding: '15px', marginTop: '20px' } },
      React.createElement('p', null, '✅ React.createElement is working')
    )
  );
};

const App: React.FC = () => {
  return React.createElement(Router, null,
    React.createElement(Routes, null,
      React.createElement(Route, { 
        path: '/', 
        element: React.createElement(HomePage) 
      }),
      React.createElement(Route, { 
        path: '/login', 
        element: React.createElement('div', null, 'Login Page') 
      })
    )
  );
};

export default App;