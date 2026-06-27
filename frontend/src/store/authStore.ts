import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AuthState {
  token: string | null;
  userId: number | null;
  email: string | null;
  fullName: string | null;
  avatar: string | null;          // base64 data URL, stored locally only
  setAuth: (token: string, userId: number, email: string, fullName: string) => void;
  setAvatar: (avatar: string | null) => void;
  setFullName: (fullName: string) => void;
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
      avatar: null,

      setAuth: (token, userId, email, fullName) =>
        set({ token, userId, email, fullName }),

      setAvatar: (avatar) => set({ avatar }),
      setFullName: (fullName) => set({ fullName }),

      logout: () =>
        set({ token: null, userId: null, email: null, fullName: null }),

      isAuthenticated: () => !!get().token,
    }),
    { name: "sja-auth" }   // persists to localStorage
  )
);
