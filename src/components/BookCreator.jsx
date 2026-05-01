import { useState } from 'react'

const GRADE_LEVELS = {
  'PreK': 'Pre-A',
  'K': 'A',
  '1st': 'B',
  '2nd': 'C',
  '3rd': 'D',
  '4th': 'F',
  '5th': 'F',
  '6th': 'F',
}

const STATUS_MESSAGES = {
  idle: 'Ready to create a new book',
  validating: 'Validating form...',
  submitting: 'Submitting to pipeline...',
  running: 'Book is being created...',
  story: 'Writing the story...',
  prompts: 'Creating illustration prompts...',
  images: 'Generating illustrations...',
  library: 'Updating library...',
  deploying: 'Deploying to Netlify...',
  done: '✅ Your book is ready!',
  error: '❌ Something went wrong',
}

export default function BookCreator() {
  const [formData, setFormData] = useState({
    topic: '',
    names: [],
    nameInput: '',
    gradeLevel: '3rd',
    featured: false,
  })

  const [creationState, setCreationState] = useState('idle') // idle, validating, submitting, running, done, error
  const [jobId, setJobId] = useState(null)
  const [statusData, setStatusData] = useState(null)
  const [errorMsg, setErrorMsg] = useState('')
  const [newBookId, setNewBookId] = useState(null)

  const handleInputChange = (e) => {
    const { name, value, type, checked } = e.target
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }))
  }

  const handleAddName = () => {
    const trimmed = formData.nameInput.trim()
    if (trimmed && formData.names.length < 5) {
      setFormData(prev => ({
        ...prev,
        names: [...prev.names, trimmed],
        nameInput: '',
      }))
    }
  }

  const handleRemoveName = (idx) => {
    setFormData(prev => ({
      ...prev,
      names: prev.names.filter((_, i) => i !== idx),
    }))
  }

  const validateForm = () => {
    if (!formData.topic.trim()) {
      setErrorMsg('Please enter a topic or story idea')
      return false
    }
    if (formData.names.length === 0) {
      setErrorMsg('Please add at least one student name')
      return false
    }
    return true
  }

  const handleSubmit = async (e) => {
    e.preventDefault()

    setErrorMsg('')
    setCreationState('validating')

    if (!validateForm()) {
      setCreationState('idle')
      return
    }

    setCreationState('submitting')

    try {
      const response = await fetch('/api/create-book', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic: formData.topic,
          names: formData.names,
          gradeLevel: formData.gradeLevel,
          readingLevel: GRADE_LEVELS[formData.gradeLevel],
          featured: formData.featured,
        }),
      })

      if (!response.ok) {
        throw new Error('Failed to start book creation')
      }

      const { jobId: newJobId } = await response.json()
      setJobId(newJobId)
      setCreationState('running')

      // Start polling for status
      pollStatus(newJobId)
    } catch (err) {
      setErrorMsg(err.message)
      setCreationState('error')
    }
  }

  const pollStatus = (jId) => {
    const pollInterval = setInterval(async () => {
      try {
        const response = await fetch(`/api/book-status?jobId=${jId}`)
        if (!response.ok) throw new Error('Status check failed')

        const data = await response.json()
        setStatusData(data)

        if (data.status === 'done') {
          clearInterval(pollInterval)
          setCreationState('done')
          setNewBookId(data.bookId)
        } else if (data.status === 'error') {
          clearInterval(pollInterval)
          setCreationState('error')
          setErrorMsg(data.error || 'Book creation failed')
        } else {
          setCreationState(data.step || 'running')
        }
      } catch (err) {
        clearInterval(pollInterval)
        setCreationState('error')
        setErrorMsg('Lost connection to server. Please refresh.')
      }
    }, 3000) // Poll every 3 seconds
  }

  const handleReset = () => {
    setFormData({
      topic: '',
      names: [],
      nameInput: '',
      gradeLevel: '3rd',
      featured: false,
    })
    setCreationState('idle')
    setJobId(null)
    setStatusData(null)
    setErrorMsg('')
    setNewBookId(null)
  }

  if (creationState === 'done') {
    return (
      <div style={styles.card}>
        <div style={styles.successIcon}>✨</div>
        <h2 style={styles.successTitle}>Book Created Successfully!</h2>
        <p style={styles.successMsg}>
          Your book "{statusData?.bookTitle}" has been created and is now available in the ReadAloud library.
        </p>
        <p style={styles.note}>
          Note: New books appear within 1-2 minutes after creation completes. If you don't see it yet, refresh the ReadAloud page.
        </p>
        <a
          href={`https://hareadaloud.netlify.app/?bookId=${newBookId}`}
          target="_blank"
          rel="noopener noreferrer"
          style={styles.linkBtn}
        >
          🎉 Open the book
        </a>
        <button onClick={handleReset} style={styles.newBookBtn}>
          Create another book
        </button>
      </div>
    )
  }

  if (creationState === 'error') {
    return (
      <div style={styles.card}>
        <div style={styles.errorIcon}>⚠️</div>
        <h2 style={styles.errorTitle}>Something went wrong</h2>
        <p style={styles.errorText}>{errorMsg}</p>
        <button onClick={handleReset} style={styles.retryBtn}>
          ← Try again
        </button>
      </div>
    )
  }

  if (creationState !== 'idle') {
    // Status/progress screen
    const progress = statusData?.progress || 0
    const total = statusData?.total || 16
    const progressPercent = total > 0 ? Math.round((progress / total) * 100) : 0

    return (
      <div style={styles.card}>
        <div style={styles.spinner}>⏳</div>
        <h2 style={styles.statusTitle}>Creating your book...</h2>
        <p style={styles.statusMsg}>
          {STATUS_MESSAGES[creationState] || STATUS_MESSAGES.running}
        </p>
        {statusData?.step === 'images' && (
          <div style={styles.progressContainer}>
            <div style={styles.progressLabel}>
              Illustrations: {progress}/{total}
            </div>
            <div style={styles.progressBar}>
              <div style={{ ...styles.progressFill, width: `${progressPercent}%` }} />
            </div>
            <div style={styles.progressPercent}>{progressPercent}%</div>
          </div>
        )}
        <p style={styles.note}>
          This typically takes 15-20 minutes. You can close this page and come back later.
        </p>
      </div>
    )
  }

  // Idle/form state
  return (
    <form onSubmit={handleSubmit} style={styles.card}>
      <h2 style={styles.formTitle}>Create a New Book</h2>
      <p style={styles.formDesc}>
        Fill out the form below and we'll generate a custom ReadAloud book for your students.
      </p>

      {/* Grade Level */}
      <div style={styles.formGroup}>
        <label style={styles.label}>Grade Level *</label>
        <select
          name="gradeLevel"
          value={formData.gradeLevel}
          onChange={handleInputChange}
          style={styles.select}
        >
          {Object.keys(GRADE_LEVELS).map(grade => (
            <option key={grade} value={grade}>{grade}</option>
          ))}
        </select>
        <p style={styles.hint}>
          Reading level {GRADE_LEVELS[formData.gradeLevel]} will be used
        </p>
      </div>

      {/* Topic / Story Idea */}
      <div style={styles.formGroup}>
        <label style={styles.label}>Topic or Story Idea *</label>
        <textarea
          name="topic"
          value={formData.topic}
          onChange={handleInputChange}
          placeholder="e.g., A turtle learning to swim in the Caribbean Sea. Include any specific themes, characters, or lessons you'd like."
          style={styles.textarea}
          rows={4}
        />
      </div>

      {/* Student Names */}
      <div style={styles.formGroup}>
        <label style={styles.label}>Student Names * (up to 5)</label>
        <div style={styles.nameInputGroup}>
          <input
            type="text"
            value={formData.nameInput}
            onChange={(e) => setFormData(prev => ({ ...prev, nameInput: e.target.value }))}
            onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddName())}
            placeholder="Enter a name and press + or Enter"
            style={styles.nameInput}
          />
          <button
            type="button"
            onClick={handleAddName}
            style={styles.addNameBtn}
            disabled={formData.names.length >= 5}
          >
            +
          </button>
        </div>
        <div style={styles.namesList}>
          {formData.names.map((name, idx) => (
            <div key={idx} style={styles.nameTag}>
              <span>{name}</span>
              <button
                type="button"
                onClick={() => handleRemoveName(idx)}
                style={styles.removeNameBtn}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Featured */}
      <div style={styles.formGroup}>
        <label style={styles.checkboxLabel}>
          <input
            type="checkbox"
            name="featured"
            checked={formData.featured}
            onChange={handleInputChange}
            style={styles.checkbox}
          />
          Featured this week
        </label>
        <p style={styles.hint}>Shows a ⭐ badge in the library</p>
      </div>

      {errorMsg && (
        <div style={styles.errorBox}>
          {errorMsg}
        </div>
      )}

      <button type="submit" style={styles.submitBtn}>
        ✨ Create Book
      </button>

      <p style={styles.disclaimer}>
        Book creation takes 15-20 minutes. The book will be added to the ReadAloud library automatically.
      </p>
    </form>
  )
}

const styles = {
  card: {
    background: 'white',
    borderRadius: 12,
    padding: 24,
    boxShadow: '0 2px 10px rgba(0,0,0,0.09)',
  },
  formTitle: {
    fontSize: 20,
    fontWeight: 800,
    color: '#1B4F72',
    marginBottom: 8,
    marginTop: 0,
  },
  formDesc: {
    fontSize: 14,
    color: '#7F8C8D',
    marginBottom: 24,
  },
  formGroup: {
    marginBottom: 20,
  },
  label: {
    display: 'block',
    fontSize: 13,
    fontWeight: 700,
    color: '#2C3E50',
    marginBottom: 6,
  },
  select: {
    width: '100%',
    padding: '10px 12px',
    borderRadius: 6,
    border: '1.5px solid #CBD5E0',
    fontSize: 14,
    fontFamily: 'inherit',
    backgroundColor: 'white',
    cursor: 'pointer',
  },
  textarea: {
    width: '100%',
    padding: '10px 12px',
    borderRadius: 6,
    border: '1.5px solid #CBD5E0',
    fontSize: 14,
    fontFamily: 'inherit',
    resize: 'vertical',
    boxSizing: 'border-box',
  },
  nameInputGroup: {
    display: 'flex',
    gap: 8,
    marginBottom: 12,
  },
  nameInput: {
    flex: 1,
    padding: '10px 12px',
    borderRadius: 6,
    border: '1.5px solid #CBD5E0',
    fontSize: 14,
    fontFamily: 'inherit',
  },
  addNameBtn: {
    width: 40,
    height: 40,
    borderRadius: 6,
    border: 'none',
    background: '#2E86C1',
    color: 'white',
    fontSize: 18,
    fontWeight: 700,
    cursor: 'pointer',
    transition: 'background 0.2s',
  },
  namesList: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 8,
  },
  nameTag: {
    background: '#EBF5FB',
    border: '1px solid #AED6F1',
    borderRadius: 20,
    padding: '6px 12px',
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    fontSize: 13,
    fontWeight: 600,
    color: '#1B4F72',
  },
  removeNameBtn: {
    background: 'none',
    border: 'none',
    color: '#1B4F72',
    fontSize: 16,
    cursor: 'pointer',
    padding: 0,
    lineHeight: 1,
    fontWeight: 700,
  },
  checkboxLabel: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    fontSize: 14,
    fontWeight: 600,
    color: '#2C3E50',
    cursor: 'pointer',
  },
  checkbox: {
    width: 18,
    height: 18,
    cursor: 'pointer',
  },
  hint: {
    fontSize: 12,
    color: '#7F8C8D',
    marginTop: 4,
    margin: '4px 0 0 0',
  },
  submitBtn: {
    width: '100%',
    padding: '12px 24px',
    fontSize: 15,
    fontWeight: 700,
    background: '#2E86C1',
    color: 'white',
    border: 'none',
    borderRadius: 6,
    cursor: 'pointer',
    transition: 'background 0.2s',
  },
  disclaimer: {
    fontSize: 12,
    color: '#7F8C8D',
    marginTop: 12,
    textAlign: 'center',
  },
  errorBox: {
    background: '#FADBD8',
    border: '1px solid #F5B7B1',
    borderRadius: 6,
    padding: 12,
    color: '#A93226',
    fontSize: 13,
    marginBottom: 16,
  },
  errorIcon: {
    fontSize: 48,
    marginBottom: 12,
    textAlign: 'center',
  },
  errorTitle: {
    fontSize: 18,
    fontWeight: 700,
    color: '#C0392B',
    marginBottom: 8,
    textAlign: 'center',
    margin: '0 0 8px 0',
  },
  errorText: {
    fontSize: 14,
    color: '#7F8C8D',
    textAlign: 'center',
    marginBottom: 20,
  },
  retryBtn: {
    width: '100%',
    padding: '12px 24px',
    fontSize: 15,
    fontWeight: 700,
    background: '#2E86C1',
    color: 'white',
    border: 'none',
    borderRadius: 6,
    cursor: 'pointer',
  },
  successIcon: {
    fontSize: 48,
    marginBottom: 12,
    textAlign: 'center',
  },
  successTitle: {
    fontSize: 18,
    fontWeight: 700,
    color: '#27AE60',
    marginBottom: 8,
    textAlign: 'center',
    margin: '0 0 8px 0',
  },
  successMsg: {
    fontSize: 14,
    color: '#2C3E50',
    textAlign: 'center',
    marginBottom: 12,
  },
  note: {
    fontSize: 12,
    color: '#7F8C8D',
    textAlign: 'center',
    marginBottom: 16,
    fontStyle: 'italic',
  },
  linkBtn: {
    display: 'inline-block',
    width: '100%',
    textAlign: 'center',
    padding: '12px 24px',
    fontSize: 15,
    fontWeight: 700,
    background: '#27AE60',
    color: 'white',
    borderRadius: 6,
    textDecoration: 'none',
    marginBottom: 12,
    boxSizing: 'border-box',
    border: 'none',
    cursor: 'pointer',
    transition: 'background 0.2s',
  },
  newBookBtn: {
    width: '100%',
    padding: '12px 24px',
    fontSize: 15,
    fontWeight: 700,
    background: '#2E86C1',
    color: 'white',
    border: 'none',
    borderRadius: 6,
    cursor: 'pointer',
  },
  spinner: {
    fontSize: 48,
    textAlign: 'center',
    marginBottom: 16,
    animation: 'spin 2s linear infinite',
  },
  statusTitle: {
    fontSize: 18,
    fontWeight: 700,
    color: '#1B4F72',
    textAlign: 'center',
    marginBottom: 8,
    margin: '0 0 8px 0',
  },
  statusMsg: {
    fontSize: 14,
    color: '#2C3E50',
    textAlign: 'center',
    marginBottom: 16,
  },
  progressContainer: {
    marginBottom: 16,
  },
  progressLabel: {
    fontSize: 12,
    color: '#7F8C8D',
    marginBottom: 6,
    fontWeight: 600,
  },
  progressBar: {
    height: 8,
    borderRadius: 4,
    background: '#E2E8F0',
    overflow: 'hidden',
    marginBottom: 6,
  },
  progressFill: {
    height: '100%',
    background: '#2E86C1',
    transition: 'width 0.3s ease',
  },
  progressPercent: {
    fontSize: 12,
    color: '#7F8C8D',
    textAlign: 'right',
  },
}
