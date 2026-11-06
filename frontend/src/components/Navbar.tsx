"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Sparkles, ShoppingBag, Video } from "lucide-react";

export function Navbar() {
  const path = usePathname();

  return (
    <header className="fixed top-0 left-0 right-0 h-12 bg-white/90 backdrop-blur-md border-b border-gray-100 flex items-center justify-between px-6 z-50 text-sm">
      <div className="flex items-center gap-6">
        <Link
          href="/"
          className="font-bold text-gray-900 flex items-center gap-1.5 tracking-tight"
        >
          <Sparkles className="w-4 h-4 text-indigo-600" />
          <span>VTON Studio</span>
        </Link>
        <nav className="flex items-center gap-4">
          <Link
            href="/"
            className={`flex items-center gap-1.5 transition ${
              path === "/"
                ? "text-gray-900 font-medium"
                : "text-gray-400 hover:text-gray-600"
            }`}
          >
            <Video className="w-3.5 h-3.5" />
            <span>Try On</span>
          </Link>
          <Link
            href="/store/default"
            className={`flex items-center gap-1.5 transition ${
              path.startsWith("/store")
                ? "text-gray-900 font-medium"
                : "text-gray-400 hover:text-gray-600"
            }`}
          >
            <ShoppingBag className="w-3.5 h-3.5" />
            <span>Store</span>
          </Link>
        </nav>
      </div>
      <div className="text-xs text-gray-400 font-mono">Local · T550</div>
    </header>
  );
}
