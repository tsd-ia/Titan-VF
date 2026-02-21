import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const DASHBOARD_PASSWORD = process.env.DASHBOARD_PASSWORD || "TitanSentinel2026";

export default function proxy(request: NextRequest) {
    const { pathname } = request.nextUrl;

    // 1. Permitir Login, API y archivos estáticos sin filtros
    if (
        pathname === "/login" ||
        pathname.startsWith("/api") ||
        pathname.startsWith("/_next") ||
        pathname.includes(".")
    ) {
        return NextResponse.next();
    }

    // 2. Verificar autenticación
    const authCookie = request.cookies.get("titan_auth");

    if (authCookie?.value === DASHBOARD_PASSWORD) {
        return NextResponse.next();
    }

    // 3. Redirigir a Login si no está autenticado
    const loginUrl = new URL("/login", request.url);
    return NextResponse.redirect(loginUrl);
}

export const config = {
    matcher: [
        "/((?!api|_next/static|_next/image|favicon.ico).*)",
    ],
};
