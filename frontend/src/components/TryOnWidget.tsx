"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { GarmentGrid } from "./GarmentGrid";
import { LiveFeed } from "./LiveFeed";

export interface Garment {
  id: string;
  name: string;
  price: number;
  file: string;
  category: string;
  collection?: string;
}

const BACKEND = "http://127.0.0.1:8000";

export function TryOnWidget() {
  const [garments, setGarments] = useState<Garment[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load catalog on mount
  useEffect(() => {
    fetch(`${BACKEND}/api/garments`)
      .then((r) => {
        if (!r.ok) throw new Error("Catalog fetch failed");
        return r.json();
      })
      .then((data) => setGarments(data))
      .catch(() =>
        setError(
          "Cannot connect to backend server. Run 'uvicorn backend.main:app'",
        ),
      );
  }, []);

  // [FIX M3] Define selectGarment with useCallback before referencing it
  const selectGarment = useCallback(
    async (garment: Garment) => {
      if (garment.id === activeId) return;
      setLoading(true);
      try {
        const res = await fetch(`${BACKEND}/api/select-garment`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ garment_id: garment.id }),
        });
        if (!res.ok) throw new Error("Switch failed");
        setActiveId(garment.id);
      } catch {
        setError("Failed to switch garment");
      } finally {
        setLoading(false);
      }
    },
    [activeId],
  );

  // Clear garment
  const clearGarment = useCallback(async () => {
    try {
      await fetch(`${BACKEND}/api/clear-garment`, { method: "POST" });
      setActiveId(null);
    } catch {
      setError("Failed to clear garment");
    }
  }, []);

  // [PATCH P1] Auto-select garment from URL search param — ONCE ONLY.
  const deepLinkApplied = useRef(false);
  useEffect(() => {
    if (typeof window === "undefined" || garments.length === 0) return;
    if (deepLinkApplied.current) return;
    const params = new URLSearchParams(window.location.search);
    const garmentId = params.get("garment");
    if (garmentId) {
      const match = garments.find((g) => g.id === garmentId);
      if (match) selectGarment(match);
    }
    deepLinkApplied.current = true;
  }, [garments, selectGarment]);

  return (
    <div className="flex flex-col h-full">
      {/* ── Subheader ── */}
      <div className="px-6 py-3 border-b border-gray-100 flex items-center justify-between">
        <div>
          <h1 className="text-[20px] font-semibold text-gray-900 tracking-tight">
            Drag a product onto yourself.
          </h1>
          <p className="text-xs text-gray-400 mt-0.5">
            • For best results — stand 1–2m away, show shoulders and arms, plain
            background
          </p>
        </div>
      </div>

      {/* ── Error Banner ── */}
      {error && (
        <div className="mx-6 mt-3 px-4 py-2 bg-red-50 border border-red-200 rounded-xl text-xs text-red-600 flex justify-between items-center">
          <span>⚠️ {error}</span>
          <button onClick={() => setError(null)} className="font-bold ml-2">
            ✕
          </button>
        </div>
      )}

      {/* ── Main Split Panel ── */}
      <div className="flex flex-1 gap-4 px-6 py-4 overflow-hidden">
        {/* Left: Garment Grid */}
        <div className="w-[240px] flex-shrink-0 flex flex-col gap-2">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
            Collection ({garments.length})
          </p>
          <GarmentGrid
            garments={garments}
            activeId={activeId}
            loading={loading}
            backendUrl={BACKEND}
            onSelect={selectGarment}
          />
        </div>

        {/* Right: Live Camera Feed */}
        <div className="flex-1 h-full min-h-0">
          <LiveFeed
            streamUrl={`${BACKEND}/video-feed`}
            isLoading={loading}
            activeGarment={garments.find((g) => g.id === activeId) ?? null}
            onGarmentDrop={(id) => {
              const g = garments.find((x) => x.id === id);
              if (g) selectGarment(g);
            }}
            onClear={clearGarment}
          />
        </div>
      </div>
    </div>
  );
}
