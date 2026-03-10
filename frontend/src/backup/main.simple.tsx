import { createRoot } from 'react-dom/client'
import './index.css'

// Direct render without any component
const root = createRoot(document.getElementById('root')!)
root.render(
  'Hello from React! If you see this, React is working.'
)