import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "TITAN SENTINEL — Dashboard de Trading",
  description: "Análisis en tiempo real de XAUUSDm. ATR, RSI, Soportes, Resistencias, Fibonacci y Gemini AI.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="es">
      <body className={`${inter.className} bg-gray-950`}>
        {children}
      </body>
    </html>
  );
}
