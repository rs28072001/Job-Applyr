import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AuthState {
  token: string | null;
  userId: number | null;
  email: string | null;
  fullName: string | null;
  setAuth: (token: string, userId: number, email: string, fullName: string) => void;
  logout: () => void;
  isAuthenticated: () => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      userId: null,
      email: null,
      fullName: null,

      setAuth: (token, userId, email, fullName) =>
        set({ token, userId, email, fullName }),

      logout: () =>
        set({ token: null, userId: null, email: null, fullName: null }),

      isAuthenticated: () => !!get().token,
    }),
    { name: "sja-auth" }   // persists to localStorage
  )
);
