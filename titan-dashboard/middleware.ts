import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const DASHBOARD_PASSWORD = process.env.DASHBOARD_PASSWORD || "TitanSentinel2026";

export function middleware(request: NextRequest) {
    // Skip API routes and static files
    if (
        request.nextUrl.pathname.startsWith("/_next") ||
        request.nextUrl.pathname.startsWith("/api") ||
        request.nextUrl.pathname.startsWith("/favicon")
    ) {
        return NextResponse.next();
    }

    const cookie = request.cookies.get("titan_auth");
    if (cookie?.value === DASHBOARD_PASSWORD) {
        return NextResponse.next();
    }

    // If it's the login page, allow
    if (request.nextUrl.pathname === "/login") {
        return NextResponse.next();
    }

    // Redirect to login
    return NextResponse.redirect(new URL("/login", request.url));
}

export const config = {
    matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
