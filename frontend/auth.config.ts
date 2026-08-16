import type { NextAuthConfig } from "next-auth";
import Google from "next-auth/providers/google";

// Auth desactivado temporalmente (dev). El login se re-activa fácil.
export const authConfig = {
  providers: [
    Google({
      clientId: process.env.AUTH_GOOGLE_ID || "",
      clientSecret: process.env.AUTH_GOOGLE_SECRET || "",
    }),
  ],
  pages: { signIn: "/login" },
  callbacks: {
    authorized() {
      // Dejar pasar a todo el mundo (dev)
      return true;
    },
    async signIn() {
      // No bloquear por email (dev)
      return true;
    },
  },
  session: { strategy: "jwt" },
} satisfies NextAuthConfig;
