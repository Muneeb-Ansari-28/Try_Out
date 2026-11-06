"use client";

import Image from "next/image";
import type { Garment } from "./TryOnWidget";

export function GarmentGrid({
  garments,
  activeId,
  loading,
  backendUrl,
  onSelect,
}: {
  garments: Garment[];
  activeId: string | null;
  loading: boolean;
  backendUrl: string;
  onSelect: (g: Garment) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-2.5 overflow-y-auto pr-1 pb-4">
      {garments.map((g) => {
        const isActive = g.id === activeId;
        return (
          <button
            key={g.id}
            // [FIX H6] Native HTML5 Drag Support
            draggable
            onDragStart={(e) => {
              e.dataTransfer.setData("text/garment-id", g.id);
              e.dataTransfer.effectAllowed = "copy";
            }}
            onClick={() => !loading && onSelect(g)}
            className={`
              relative aspect-square rounded-2xl overflow-hidden border-2 transition-all duration-150
              hover:scale-[1.03] active:scale-[0.97] cursor-grab active:cursor-grabbing text-left
              ${isActive ? "border-gray-900 shadow-md ring-2 ring-gray-900/10" : "border-gray-100 hover:border-gray-300"}
              ${loading && !isActive ? "opacity-60 cursor-not-allowed" : ""}
            `}
          >
            {/* [FIX H6] draggable={false} on Image so browser drags the parent tile, not the <img> */}
            {/* [PATCH P10] object-contain (was object-cover): tall garments like the coat/dress were cropped in the square tile */}
            <Image
              src={`${backendUrl}/garments/${g.file}`}
              alt={g.name}
              fill
              className="object-contain p-2"
              unoptimized
              draggable={false}
            />

            {/* Label Overlay */}
            <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/60 to-transparent p-2 pt-4">
              <p className="text-white text-[11px] font-medium truncate">
                {g.name}
              </p>
              <p className="text-white/80 text-[10px]">${g.price.toFixed(2)}</p>
            </div>

            {/* Active Indicator Ring */}
            {isActive && (
              <div className="absolute top-2 right-2 w-2 h-2 rounded-full bg-emerald-500 ring-2 ring-white" />
            )}
          </button>
        );
      })}

      {garments.length === 0 && (
        <div className="col-span-2 py-10 text-center text-xs text-gray-400">
          No garments available.
          <br />
          Run prepare_garments.py
        </div>
      )}
    </div>
  );
}

