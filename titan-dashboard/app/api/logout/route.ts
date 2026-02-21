import { NextResponse } from "next/server";

export async function POST() {
    const response = NextResponse.json({ ok: true });
    response.cookies.set("titan_auth", "", { maxAge: 0, path: "/" });
    return response;
}
