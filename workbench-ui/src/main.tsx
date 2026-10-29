import { FocusStyleManager } from '@blueprintjs/core'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@blueprintjs/core/lib/css/blueprint.css'
import '@blueprintjs/icons/lib/css/blueprint-icons.css'
import './App.css'
import App from './App.tsx'

FocusStyleManager.onlyShowFocusOnTabs()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
