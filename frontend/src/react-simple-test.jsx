import React from 'react';
import { createRoot } from 'react-dom/client';

console.log('Simple React test module loaded');

// 如果已经有输出，添加内容
const output = document.getElementById('output') || document.body;

// 创建简单的React应用
function SimpleApp() {
    return React.createElement('div', null,
        React.createElement('h2', null, 'React Test Working!'),
        React.createElement('p', null, 'If you see this, React is loading correctly.')
    );
}

// 渲染
const root = createRoot(output);
root.render(React.createElement(SimpleApp));

export default SimpleApp;