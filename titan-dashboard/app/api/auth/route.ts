import { NextRequest, NextResponse } from "next/server";

const DASHBOARD_PASSWORD = process.env.DASHBOARD_PASSWORD || "TitanSentinel2026";

export async function POST(request: NextRequest) {
    const { password } = await request.json();
    if (password === DASHBOARD_PASSWORD) {
        const response = NextResponse.json({ ok: true });
        response.cookies.set("titan_auth", DASHBOARD_PASSWORD, {
            httpOnly: true,
            secure: process.env.NODE_ENV === "production",
            maxAge: 60 * 60 * 24 * 30, // 30 días
            path: "/",
        });
        return response;
    }
    return NextResponse.json({ ok: false }, { status: 401 });
}
