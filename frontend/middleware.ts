// Auth desactivado temporalmente (dev local)
// Para reactivar, restaurar el middleware que usa NextAuth.
import { NextResponse } from "next/server";

export default function middleware() {
  return NextResponse.next();
}

export const config = {
  matcher: [],
};

