import { useState } from 'react'
import BookCreator from './components/BookCreator'
import './App.css'

const CONFIG = {
  TEACHER_PIN: import.meta.env.VITE_TEACHER_PIN || '1234',
}

export default function App() {
  const [authenticated, setAuthenticated] = useState(false)
  const [pinInput, setPinInput] = useState('')
  const [pinError, setPinError] = useState('')

  const handlePinSubmit = (e) => {
    e.preventDefault()
    if (pinInput === CONFIG.TEACHER_PIN) {
      setAuthenticated(true)
      setPinError('')
    } else {
      setPinError('Incorrect PIN')
      setPinInput('')
    }
  }

  if (!authenticated) {
    return (
      <div style={styles.pinScreen}>
        <div style={styles.pinCard}>
          <h1 style={styles.title}>📚 ReadAloud Creator</h1>
          <p style={styles.subtitle}>Teacher Book Creation Tool</p>
          <form onSubmit={handlePinSubmit} style={styles.form}>
            <input
              type="password"
              placeholder="Enter teacher PIN"
              value={pinInput}
              onChange={(e) => setPinInput(e.target.value)}
              style={styles.input}
              maxLength="4"
              autoFocus
            />
            <button type="submit" style={styles.button}>
              Enter
            </button>
          </form>
          {pinError && <p style={styles.error}>{pinError}</p>}
        </div>
      </div>
    )
  }

  return (
    <div style={styles.appContainer}>
      <header style={styles.header}>
        <h1>📚 ReadAloud Creator</h1>
        <button
          onClick={() => setAuthenticated(false)}
          style={styles.logoutBtn}
        >
          Logout
        </button>
      </header>
      <main style={styles.main}>
        <BookCreator />
      </main>
    </div>
  )
}

const styles = {
  pinScreen: {
    height: '100dvh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'linear-gradient(135deg, #1B4F72 0%, #2E86C1 60%, #5DADE2 100%)',
    fontFamily: "'Nunito', system-ui, sans-serif",
  },
  pinCard: {
    background: 'white',
    borderRadius: 16,
    padding: 40,
    boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
    textAlign: 'center',
    maxWidth: 300,
    width: '90%',
  },
  title: {
    fontSize: 28,
    fontWeight: 800,
    color: '#1B4F72',
    marginBottom: 4,
    margin: '0 0 4px 0',
  },
  subtitle: {
    fontSize: 14,
    color: '#7F8C8D',
    marginBottom: 24,
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
  },
  input: {
    padding: '12px 14px',
    fontSize: 18,
    borderRadius: 8,
    border: '2px solid #CBD5E0',
    textAlign: 'center',
    letterSpacing: 4,
    fontWeight: 600,
    fontFamily: 'monospace',
    transition: 'border-color 0.2s',
  },
  button: {
    padding: '12px 24px',
    fontSize: 14,
    fontWeight: 700,
    background: '#2E86C1',
    color: 'white',
    border: 'none',
    borderRadius: 8,
    cursor: 'pointer',
    transition: 'background 0.2s',
  },
  error: {
    color: '#E74C3C',
    fontSize: 12,
    marginTop: 8,
  },
  appContainer: {
    minHeight: '100dvh',
    background: '#F0F4F8',
    fontFamily: "'Nunito', system-ui, sans-serif",
  },
  header: {
    background: 'linear-gradient(135deg, #1B4F72 0%, #2E86C1 60%, #5DADE2 100%)',
    color: 'white',
    padding: '16px 24px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    boxShadow: '0 2px 12px rgba(0,0,0,0.18)',
  },
  logoutBtn: {
    background: 'rgba(255,255,255,0.2)',
    border: '1.5px solid rgba(255,255,255,0.5)',
    borderRadius: 16,
    padding: '5px 12px',
    fontSize: 12,
    fontWeight: 800,
    color: 'white',
    cursor: 'pointer',
    fontFamily: "'Nunito', system-ui, sans-serif",
    transition: 'all 0.2s',
  },
  main: {
    maxWidth: 600,
    margin: '0 auto',
    padding: '24px 16px',
  },
}
