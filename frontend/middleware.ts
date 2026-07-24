import { auth } from "./auth";
export { auth as middleware } from "./auth";

export const config = {
  // Proteger estas rutas — el resto son públicas
  matcher: ["/portfolio/:path*", "/copilot/:path*", "/settings/:path*"],
};

