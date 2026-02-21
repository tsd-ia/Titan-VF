"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);
    const router = useRouter();

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        const res = await fetch("/api/auth", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ password }),
        });
        if (res.ok) {
            router.push("/");
            router.refresh();
        } else {
            setError("Contraseña incorrecta");
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-gray-950 flex items-center justify-center p-4">
            <div className="w-full max-w-sm">
                <div className="text-center mb-8">
                    <div className="text-5xl mb-4">🛡️</div>
                    <h1 className="text-3xl font-bold text-white">TITAN SENTINEL</h1>
                    <p className="text-gray-400 mt-2">Dashboard de Trading en Vivo</p>
                </div>
                <form onSubmit={handleLogin} className="bg-gray-900 rounded-2xl p-8 border border-gray-800 shadow-2xl">
                    <label className="block text-gray-400 text-sm font-medium mb-2">
                        Contraseña de acceso
                    </label>
                    <input
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        className="w-full bg-gray-800 text-white rounded-xl px-4 py-3 border border-gray-700 focus:outline-none focus:border-yellow-500 transition-colors mb-4"
                        placeholder="••••••••••••••"
                        autoFocus
                    />
                    {error && (
                        <p className="text-red-400 text-sm mb-4">❌ {error}</p>
                    )}
                    <button
                        type="submit"
                        disabled={loading}
                        className="w-full bg-yellow-500 hover:bg-yellow-400 text-black font-bold py-3 rounded-xl transition-colors disabled:opacity-50"
                    >
                        {loading ? "Verificando..." : "Entrar al Sentinel"}
                    </button>
                </form>
                <p className="text-center text-gray-600 text-xs mt-6">
                    Solo tú tienes acceso. Datos en tiempo real.
                </p>
            </div>
        </div>
    );
}
