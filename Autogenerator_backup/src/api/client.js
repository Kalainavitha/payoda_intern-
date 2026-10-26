const API_BASE_URL = (
  import.meta.env.VITE_API_URL || 'http://127.0.0.1:8001'
).replace(/\/+$/, '')

/**
 * Constructs a full API URL.
 */
export function apiUrl(path = '') {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${API_BASE_URL}${normalizedPath}`
}

/**
 * Standard fetch wrapper for making API requests.
 */
export async function apiRequest(endpoint, options = {}) {
  const url = apiUrl(endpoint)

  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        ...(options.body instanceof FormData
          ? {}
          : { 'Content-Type': 'application/json' }),
        ...(options.headers || {})
      }
    })

    // Handle 204 No Content
    if (response.status === 204) {
      return null
    }

    let data = null

    try {
      data = await response.json()
    } catch {
      data = null
    }

    if (!response.ok) {
      let errorMessage = `HTTP Error ${response.status}: ${response.statusText}`

      if (data?.detail) {
        if (typeof data.detail === 'string') {
          errorMessage = data.detail
        } else if (Array.isArray(data.detail)) {
          errorMessage = data.detail
            .map(error => {
              const location = Array.isArray(error.loc)
                ? error.loc.join('.')
                : ''
              return location
                ? `${location}: ${error.msg}`
                : error.msg
            })
            .join(', ')
        }
      }

      throw new Error(errorMessage)
    }

    return data
  } catch (error) {
    // Give a clearer message when the browser cannot reach FastAPI.
    if (error instanceof TypeError && error.message === 'Failed to fetch') {
      throw new Error(
        `Cannot connect to the FastAPI backend at ${API_BASE_URL}. ` +
        `Make sure the backend is running on port 8001.`
      )
    }

    throw error
  }
}

/**
 * Helper to create JSON POST/PUT/PATCH options.
 */
export function jsonOptions(method, body) {
  return {
    method,
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(body)
  }
}