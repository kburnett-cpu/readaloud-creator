/**
 * Netlify Function: /api/create-book
 *
 * Receives book creation form data from the frontend and forwards it to the
 * Railway backend. Returns immediately with a jobId for status polling.
 *
 * Environment variables needed:
 * - RAILWAY_API_URL: Base URL of the Railway backend (e.g., https://app.railway.app)
 * - PIPELINE_SECRET: Shared secret for authenticating with Railway backend
 */

const RAILWAY_API_URL = process.env.RAILWAY_API_URL || 'http://localhost:5000'
const PIPELINE_SECRET = process.env.PIPELINE_SECRET || 'dev-secret'

export default async (req, res) => {
  // Only allow POST requests
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' })
  }

  try {
    const { topic, names, gradeLevel, readingLevel, featured } = req.body

    // Basic validation
    if (!topic || !names || names.length === 0 || !gradeLevel) {
      return res.status(400).json({ error: 'Missing required fields' })
    }

    // Forward to Railway backend
    const backendUrl = `${RAILWAY_API_URL}/create-book`
    const response = await fetch(backendUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Api-Key': PIPELINE_SECRET,
      },
      body: JSON.stringify({
        topic,
        names,
        gradeLevel,
        readingLevel,
        featured: !!featured,
      }),
    })

    if (!response.ok) {
      const error = await response.text()
      console.error('Railway backend error:', error)
      return res.status(response.status).json({
        error: 'Failed to start book creation. Please try again.'
      })
    }

    const data = await response.json()
    return res.status(200).json(data)
  } catch (error) {
    console.error('Error in create-book function:', error)
    return res.status(500).json({
      error: 'Server error. Please try again later.'
    })
  }
}
