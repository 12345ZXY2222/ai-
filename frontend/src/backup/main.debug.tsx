// Debug test - only console.log
console.log('=== MAIN.TSX STARTING ===')

try {
  const rootElement = document.getElementById('root')
  console.log('Root element:', rootElement)
  
  if (rootElement) {
    console.log('Root found, adding test content...')
    // 直接DOM操作
    rootElement.innerHTML = '<h1>DEBUG TEST</h1><p>If you see this, JavaScript is executing.</p>'
    
    // 检查React全局变量
    console.log('React global:', window.React)
    console.log('ReactDOM global:', window.ReactDOM)
    
    // 尝试导入React
    console.log('Attempting to import react-dom/client...')
    import('react-dom/client').then(module => {
      console.log('ReactDOM module loaded:', module)
      const { createRoot } = module
      console.log('createRoot function:', createRoot)
      
      try {
        const root = createRoot(rootElement)
        console.log('createRoot succeeded, calling render...')
        root.render('Hello from React!')
        console.log('React render succeeded')
      } catch (renderErr) {
        console.error('React render error:', renderErr)
        rootElement.innerHTML += '<p style="color: red;">React render error: ' + renderErr.message + '</p>'
      }
    }).catch(importErr => {
      console.error('Failed to import ReactDOM:', importErr)
      const errorDiv = document.createElement('div')
      errorDiv.innerHTML = '<p style="color: red;">ReactDOM import error: ' + importErr.message + '</p>'
      rootElement.appendChild(errorDiv)
    })
  } else {
    console.error('Root element not found!')
  }
} catch (error) {
  console.error('Global error in main.tsx:', error)
}

console.log('=== MAIN.TSX FINISHED ===')