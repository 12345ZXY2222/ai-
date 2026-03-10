// Ultra simple React app - no JSX
import React from 'react';

const App: React.FC = () => {
  return React.createElement('div', { style: { padding: '20px' } },
    React.createElement('h1', null, 'Ultra Simple React App'),
    React.createElement('p', null, 'No JSX, just React.createElement'),
    React.createElement('div', { style: { backgroundColor: '#f0f0f0', padding: '10px', marginTop: '10px' } },
      React.createElement('p', null, 'If you see this, React is working without any fancy features.')
    )
  );
};

export default App;