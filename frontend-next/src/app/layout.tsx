import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "CBSE AI Evaluator",
  description: "Advanced AI-powered answer sheet evaluation with real-time feedback and visual marking.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body suppressHydrationWarning className={`${inter.className} min-h-full flex flex-col transition-colors duration-300`}>
        {children}
      </body>
    </html>
  );
}
