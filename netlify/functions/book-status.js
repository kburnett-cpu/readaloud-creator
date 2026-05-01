/**
 * Netlify Function: /api/book-status
 *
 * Polls the Railway backend for the status of an ongoing book creation job.
 * Called repeatedly by the frontend during book creation.
 *
 * Query params:
 * - jobId: The job ID returned from /create-book
 *
 * Environment variables needed:
 * - RAILWAY_API_URL: Base URL of the Railway backend
 * - PIPELINE_SECRET: Shared secret for authenticating with Railway backend
 */

const RAILWAY_API_URL = process.env.RAILWAY_API_URL || 'http://localhost:5000'
const PIPELINE_SECRET = process.env.PIPELINE_SECRET || 'dev-secret'

export default async (req, res) => {
  // Only allow GET requests
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' })
  }

  try {
    const { jobId } = req.query

    if (!jobId) {
      return res.status(400).json({ error: 'jobId query parameter required' })
    }

    // Fetch status from Railway backend
    const backendUrl = `${RAILWAY_API_URL}/status/${jobId}`
    const response = await fetch(backendUrl, {
      method: 'GET',
      headers: {
        'X-Api-Key': PIPELINE_SECRET,
      },
    })

    if (!response.ok) {
      console.error('Status check failed:', response.status)
      return res.status(response.status).json({
        error: 'Failed to fetch status'
      })
    }

    const data = await response.json()
    return res.status(200).json(data)
  } catch (error) {
    console.error('Error in book-status function:', error)
    return res.status(500).json({
      error: 'Server error while checking status'
    })
  }
}
