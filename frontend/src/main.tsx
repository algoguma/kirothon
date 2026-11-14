import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource/black-han-sans' // OFL-1.1, title font
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
