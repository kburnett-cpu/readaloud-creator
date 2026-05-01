/**
 * Netlify Function: /api/book-status
 *
 * Polls the Railway backend for the status of an ongoing book creation job.
 * Called repeatedly by the frontend during book creation.
 */

const RAILWAY_API_URL = process.env.RAILWAY_API_URL || 'http://localhost:5000'
const PIPELINE_SECRET = process.env.PIPELINE_SECRET || 'dev-secret'

const json = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })

export default async (req) => {
  if (req.method !== 'GET') {
    return json({ error: 'Method not allowed' }, 405)
  }

  try {
    const jobId = new URL(req.url).searchParams.get('jobId')

    if (!jobId) {
      return json({ error: 'jobId query parameter required' }, 400)
    }

    const response = await fetch(`${RAILWAY_API_URL}/status/${jobId}`, {
      method: 'GET',
      headers: { 'X-Api-Key': PIPELINE_SECRET },
    })

    if (!response.ok) {
      return json({ error: 'Failed to fetch status' }, response.status)
    }

    const data = await response.json()
    return json(data, 200)
  } catch (error) {
    console.error('Error in book-status function:', error)
    return json({ error: 'Server error while checking status' }, 500)
  }
}
