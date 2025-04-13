"use client"

import type React from "react"

import { createContext, useEffect, useState } from "react"
import type { User, Session } from "@supabase/supabase-js"
import { supabase } from "@/lib/supabase/client"

// Create auth context
export const AuthContext = createContext<{
  user: User | null
  session: Session | null
  loading: boolean
  signIn: (email: string, password: string) => Promise<void>
  signUp: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
  deleteAccount: () => Promise<void>
}>({
  user: null,
  session: null,
  loading: true,
  signIn: async () => {},
  signUp: async () => {},
  signOut: async () => {},
  deleteAccount: async () => {},
})

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Get initial session
    const initializeAuth = async () => {
      try {
        const { data: { session } } = await supabase.auth.getSession()
        setSession(session)
        setUser(session?.user || null)
      } catch (error) {
        console.warn('Error getting session:', error)
      } finally {
        setLoading(false)
      }

      try {
        // Listen for auth changes
        const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
          setSession(session)
          setUser(session?.user || null)
        })

        return () => {
          subscription.unsubscribe()
        }
      } catch (error) {
        console.warn('Error setting up auth listener:', error)
      }
    }

    initializeAuth()
  }, [])

  const signIn = async (email: string, password: string) => {
    try {
      const { error } = await supabase.auth.signInWithPassword({ email, password })
      if (error) throw error
    } catch (error) {
      console.warn('Error signing in:', error)
    }
  }

  const signUp = async (email: string, password: string) => {
    try {
      const { error } = await supabase.auth.signUp({ email, password })
      if (error) throw error
    } catch (error) {
      console.warn('Error signing up:', error)
    }
  }

  const signOut = async () => {
    try {
      const { error } = await supabase.auth.signOut()
      if (error) throw error
    } catch (error) {
      console.warn('Error signing out:', error)
    }
  }

  const deleteAccount = async () => {
    if (!user) {
      console.warn('No user is currently signed in')
      return
    }

    try {
      await supabase.auth.signOut()
    } catch (error) {
      console.warn('Error deleting account:', error)
    }
  }

  return (
    <AuthContext.Provider value={{ user, session, loading, signIn, signUp, signOut, deleteAccount }}>
      {children}
    </AuthContext.Provider>
  )
}
