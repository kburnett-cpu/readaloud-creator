/**
 * Netlify Function: /api/create-book
 *
 * Receives book creation form data from the frontend and forwards it to the
 * Railway backend. Returns immediately with a jobId for status polling.
 */

const RAILWAY_API_URL = process.env.RAILWAY_API_URL || 'http://localhost:5000'
const PIPELINE_SECRET = process.env.PIPELINE_SECRET || 'dev-secret'

const json = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })

export default async (req) => {
  if (req.method !== 'POST') {
    return json({ error: 'Method not allowed' }, 405)
  }

  try {
    const { topic, names, gradeLevel, readingLevel, featured } = await req.json()

    if (!topic || !names || names.length === 0 || !gradeLevel) {
      return json({ error: 'Missing required fields' }, 400)
    }

    const response = await fetch(`${RAILWAY_API_URL}/create-book`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Api-Key': PIPELINE_SECRET,
      },
      body: JSON.stringify({ topic, names, gradeLevel, readingLevel, featured: !!featured }),
    })

    if (!response.ok) {
      const error = await response.text()
      console.error('Railway backend error:', error)
      return json({ error: 'Failed to start book creation. Please try again.' }, response.status)
    }

    const data = await response.json()
    return json(data, 200)
  } catch (error) {
    console.error('Error in create-book function:', error)
    return json({ error: 'Server error. Please try again later.' }, 500)
  }
}
