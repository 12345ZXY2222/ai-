// Ultra simple test - direct render
const rootElement = document.getElementById('root')
if (rootElement) {
  console.log('Root element found, attempting render...')
  // Direct DOM manipulation first
  rootElement.innerHTML = '<h1>DIRECT DOM TEST</h1><p>If you see this, DOM manipulation works.</p>'
  
  // Then try React
  import('react-dom/client').then(module => {
    const { createRoot } = module
    console.log('ReactDOM loaded, createRoot:', createRoot)
    const root = createRoot(rootElement)
    root.render('Hello from React!')
    console.log('React render called')
  }).catch(err => {
    console.error('Failed to load ReactDOM:', err)
    rootElement.innerHTML += '<p style="color: red;">ReactDOM load error: ' + err.message + '</p>'
  })
} else {
  console.error('Root element not found!')
}