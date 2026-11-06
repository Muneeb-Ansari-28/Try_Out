"use client";

import { useState } from "react";
import { X, Sparkles, RefreshCw } from "lucide-react";
import type { Garment } from "./TryOnWidget";

export function LiveFeed({
  streamUrl,
  isLoading,
  activeGarment,
  onGarmentDrop,
  onClear,
}: {
  streamUrl: string;
  isLoading: boolean;
  activeGarment: Garment | null;
  onGarmentDrop: (garmentId: string) => void;
  onClear: () => void;
}) {
  const [streamError, setStreamError] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);

  return (
    <div
      className={`
        relative h-full w-full rounded-3xl overflow-hidden bg-stone-900 border border-gray-200
        transition-all duration-200 select-none
        ${isDragOver ? "ring-4 ring-indigo-500 ring-offset-2 scale-[0.99]" : ""}
      `}
      // [FIX H6] Native HTML5 Drop Handler
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragOver(true);
      }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setIsDragOver(false);
        const gid = e.dataTransfer.getData("text/garment-id");
        if (gid) onGarmentDrop(gid);
      }}
    >
      {/* MJPEG Stream Tag */}
      {!streamError ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={streamUrl}
          alt="Live virtual try-on stream"
          className="w-full h-full object-cover"
          onError={() => setStreamError(true)}
        />
      ) : (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-stone-950 text-stone-300">
          <p className="text-3xl">📡</p>
          <p className="font-semibold text-sm">Camera Stream Disconnected</p>
          <p className="text-xs text-stone-500 max-w-sm text-center">
            Make sure the backend is running on 127.0.0.1:8000 and your webcam
            is not locked by another app.
          </p>
          <button
            onClick={() => setStreamError(false)}
            className="mt-2 px-4 py-1.5 bg-white text-stone-900 rounded-full text-xs font-semibold hover:bg-stone-200"
          >
            Retry Stream
          </button>
        </div>
      )}

      {/* Drag Over Hint */}
      {isDragOver && (
        <div className="absolute inset-0 flex items-center justify-center bg-indigo-950/40 backdrop-blur-sm pointer-events-none">
          <div className="bg-indigo-600 text-white font-semibold px-6 py-3 rounded-2xl shadow-xl flex items-center gap-2 text-sm">
            <Sparkles className="w-4 h-4" />
            <span>Drop to Try On</span>
          </div>
        </div>
      )}

      {/* [FIX H10] Top-Left Pill with integrated spinner */}
      {activeGarment && (
        <div className="absolute top-4 left-4 bg-white/95 backdrop-blur-md px-3.5 py-1.5 rounded-full shadow-md flex items-center gap-2 border border-gray-100">
          {isLoading ? (
            <RefreshCw className="w-3.5 h-3.5 text-indigo-600 animate-spin" />
          ) : (
            <div className="w-2 h-2 rounded-full bg-emerald-500" />
          )}
          <span className="text-xs font-medium text-gray-800">
            Wearing:{" "}
            <strong className="font-semibold">{activeGarment.name}</strong>
          </span>
        </div>
      )}

      {/* [FIX H10] Top-Right Clear Button (independent position) */}
      {activeGarment && (
        <button
          onClick={onClear}
          title="Clear garment"
          className="absolute top-4 right-4 p-2 bg-white/90 hover:bg-white text-gray-700 hover:text-black rounded-full shadow-md transition"
        >
          <X className="w-4 h-4" />
        </button>
      )}

      {/* Initial Guidance */}
      {!activeGarment && !streamError && (
        <div className="absolute bottom-6 inset-x-0 flex justify-center pointer-events-none">
          <div className="bg-black/60 backdrop-blur-md text-white text-xs px-4 py-2 rounded-full shadow-lg">
            👈 Drag or click any garment on the left to try on
          </div>
        </div>
      )}
    </div>
  );
}

