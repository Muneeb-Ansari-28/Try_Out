import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Navbar } from "@/components/Navbar";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Virtual Try-On — Live AR",
  description: "Real-time virtual try-on powered by MediaPipe and FastAPI",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={`${inter.className} bg-white text-gray-900 pt-12`}>
        {/* [FIX H10] Global navigation bar */}
        <Navbar />
        {children}
      </body>
    </html>
  );
}
