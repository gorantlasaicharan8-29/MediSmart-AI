import React, { useState, useEffect, useCallback } from 'react'
import { getCurrentUser, loginUser, logoutUser, registerUser } from '../services/api'
import { AuthContext } from './authContextInstance'

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)

  // Validate existing session on mount using HttpOnly cookie
  const checkAuth = useCallback(async () => {
    try {
      const currentUser = await getCurrentUser()
      setUser(currentUser)
      setError(null)
    } catch {
      // 401 or network issue means user is unauthenticated
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    let ignore = false
    const init = async () => {
      try {
        const currentUser = await getCurrentUser()
        if (!ignore) {
          setUser(currentUser)
          setError(null)
        }
      } catch {
        if (!ignore) {
          setUser(null)
        }
      } finally {
        if (!ignore) {
          setIsLoading(false)
        }
      }
    }
    init()
    return () => {
      ignore = true
    }
  }, [])

  const login = async (credentials) => {
    setError(null)
    try {
      const response = await loginUser(credentials)
      setUser(response.user)
      return response.user
    } catch (err) {
      setError(err.message)
      throw err
    }
  }

  const register = async (userData) => {
    setError(null)
    try {
      const response = await registerUser(userData)
      return response
    } catch (err) {
      setError(err.message)
      throw err
    }
  }

  const logout = async () => {
    try {
      await logoutUser()
    } catch {
      // Ignore network errors during logout
    } finally {
      setUser(null)
      setError(null)
    }
  }

  const value = {
    user,
    isAuthenticated: Boolean(user),
    isLoading,
    error,
    login,
    register,
    logout,
    refreshUser: checkAuth,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
