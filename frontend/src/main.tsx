import React from 'react'
import ReactDOM from 'react-dom/client'
import './styles.css'

function App() {
  return <main aria-label="Application shell"><span>Awaaz Setu</span></main>
}

ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>)
