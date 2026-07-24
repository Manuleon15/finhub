import type { NextAuthConfig } from "next-auth";
import Google from "next-auth/providers/google";

/**
 * Configuración NextAuth v5 (Auth.js).
 *
 * Login con Google OAuth. Solo emails en ALLOWED_EMAILS pueden entrar.
 * Rutas protegidas: /portfolio, /copilot, /settings
 * Rutas públicas: /, /research, /screener, /alerts, /earnings
 */
export const authConfig = {
  providers: [
    Google({
      clientId: process.env.AUTH_GOOGLE_ID,
      clientSecret: process.env.AUTH_GOOGLE_SECRET,
    }),
  ],
  pages: {
    signIn: "/login",
  },
  callbacks: {
    authorized({ auth, request }) {
      const isLoggedIn = !!auth?.user;
      const pathname = request.nextUrl.pathname;

      // Rutas que requieren login
      const protectedRoutes = ["/portfolio", "/copilot", "/settings"];
      const isProtected = protectedRoutes.some((r) => pathname.startsWith(r));

      if (isProtected && !isLoggedIn) {
        return false; // Redirect a /login
      }

      return true;
    },
    async signIn({ user }) {
      // Whitelist de emails
      const allowedEmails = (process.env.ALLOWED_EMAILS || "")
        .split(",")
        .map((e) => e.trim().toLowerCase())
        .filter(Boolean);

      if (allowedEmails.length === 0) {
        // Si no hay whitelist, permitir a todos (dev mode)
        return true;
      }

      const email = user.email?.toLowerCase();
      if (email && allowedEmails.includes(email)) {
        return true;
      }

      // Email no autorizado
      console.warn(`Acceso denegado para: ${email}`);
      return false;
    },
  },
  session: { strategy: "jwt" },
} satisfies NextAuthConfig;

