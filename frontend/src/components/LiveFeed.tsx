"use client";

import { useState, useEffect, useRef } from "react";
import { X, Sparkles, RefreshCw, Download, Wand2, Eye } from "lucide-react";
import type { Garment } from "./TryOnWidget";

const BACKEND = "http://127.0.0.1:8000";

interface AIJobStatus {
  id: string;
  status: "queued" | "processing" | "completed" | "failed";
  progress?: string;
  result_url?: string;
  elapsed_s?: number;
  error?: string;
}

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

  // AI Try-On state
  const [aiLoading, setAiLoading] = useState(false);
  const [aiJob, setAiJob] = useState<AIJobStatus | null>(null);
  const [showResultModal, setShowResultModal] = useState(false);
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Cleanup polling timer on unmount
  useEffect(() => {
    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, []);

  // Trigger Photorealistic AI Try-On
  const handleAITryOn = async () => {
    if (!activeGarment || aiLoading) return;
    setAiLoading(true);
    setAiJob({
      id: "pending",
      status: "queued",
      progress: "Capturing pose & sending to neural try-on cluster...",
    });

    try {
      const res = await fetch(`${BACKEND}/api/tryon-ai`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ garment_id: activeGarment.id }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to start AI try-on");
      }

      const { job_id } = await res.json();

      // Poll job status
      pollTimerRef.current = setInterval(async () => {
        try {
          const statusRes = await fetch(`${BACKEND}/api/tryon-ai/status/${job_id}`);
          if (!statusRes.ok) return;

          const job: AIJobStatus = await statusRes.json();
          setAiJob(job);

          if (job.status === "completed") {
            if (pollTimerRef.current) clearInterval(pollTimerRef.current);
            setAiLoading(false);
            setShowResultModal(true);
          } else if (job.status === "failed") {
            if (pollTimerRef.current) clearInterval(pollTimerRef.current);
            setAiLoading(false);
          }
        } catch {
          // ignore transient poll errors
        }
      }, 2000);
    } catch (err: unknown) {
      setAiLoading(false);
      setAiJob({
        id: "error",
        status: "failed",
        error: err instanceof Error ? err.message : "AI service request failed",
        progress: "Failed to connect to AI try-on engine.",
      });
    }
  };

  return (
    <div
      className={`
        relative h-full w-full rounded-3xl overflow-hidden bg-stone-900 border border-gray-200
        transition-all duration-200 select-none
        ${isDragOver ? "ring-4 ring-indigo-500 ring-offset-2 scale-[0.99]" : ""}
      `}
      // Native HTML5 Drop Handler
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

      {/* Top-Left Pill with integrated spinner */}
      {activeGarment && (
        <div className="absolute top-4 left-4 bg-white/95 backdrop-blur-md px-3.5 py-1.5 rounded-full shadow-md flex items-center gap-2 border border-gray-100 z-10">
          {isLoading ? (
            <RefreshCw className="w-3.5 h-3.5 text-indigo-600 animate-spin" />
          ) : (
            <div className="w-2 h-2 rounded-full bg-emerald-500" />
          )}
          <span className="text-xs font-medium text-gray-800">
            Selected: <strong className="font-semibold">{activeGarment.name}</strong>
          </span>
        </div>
      )}

      {/* Top-Right Clear Button */}
      {activeGarment && (
        <button
          onClick={onClear}
          title="Clear garment"
          className="absolute top-4 right-4 p-2 bg-white/90 hover:bg-white text-gray-700 hover:text-black rounded-full shadow-md transition z-10"
        >
          <X className="w-4 h-4" />
        </button>
      )}

      {/* Prominent Floating "✨ Generate Photorealistic AI Try-On" Button */}
      {activeGarment && !aiLoading && (
        <div className="absolute bottom-6 inset-x-0 flex justify-center z-10 pointer-events-auto">
          <button
            onClick={handleAITryOn}
            className="
              px-6 py-3.5 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500
              text-white font-semibold rounded-2xl shadow-2xl flex items-center gap-2.5 text-sm
              hover:scale-[1.03] active:scale-[0.98] transition-all border border-white/20
            "
          >
            <Wand2 className="w-4 h-4 text-amber-300 animate-pulse" />
            <span>Generate Photorealistic AI Try-On</span>
          </button>
        </div>
      )}

      {/* AI Processing Overlay */}
      {aiLoading && (
        <div className="absolute inset-0 bg-black/75 backdrop-blur-md flex flex-col items-center justify-center gap-4 z-20 text-white px-6 text-center">
          <div className="relative">
            <div className="w-16 h-16 rounded-full border-4 border-indigo-400/20 border-t-indigo-500 animate-spin" />
            <Sparkles className="w-6 h-6 text-amber-400 absolute inset-0 m-auto animate-pulse" />
          </div>
          <div>
            <h3 className="text-lg font-bold tracking-tight text-white">
              AI Tailoring in Progress...
            </h3>
            <p className="text-xs text-indigo-200 mt-1 max-w-sm">
              {aiJob?.progress || "Analyzing body pose and naturally fitting fabric folds and lighting (~15–30s)..."}
            </p>
          </div>
          <div className="text-[11px] font-mono text-gray-400 bg-white/10 px-3 py-1 rounded-full">
            Powered by IDM-VTON Neural Diffusion
          </div>
        </div>
      )}

      {/* AI Error Alert */}
      {aiJob?.status === "failed" && !aiLoading && (
        <div className="absolute bottom-6 inset-x-6 mx-auto max-w-md bg-red-950/90 border border-red-500/40 text-red-200 px-4 py-3 rounded-2xl shadow-xl flex items-center justify-between text-xs z-10">
          <span>⚠️ {aiJob.error || "AI generation failed. Please try again."}</span>
          <button
            onClick={() => setAiJob(null)}
            className="text-red-400 hover:text-white font-bold ml-2"
          >
            ✕
          </button>
        </div>
      )}

      {/* Initial Guidance */}
      {!activeGarment && !streamError && (
        <div className="absolute bottom-6 inset-x-0 flex justify-center pointer-events-none">
          <div className="bg-black/60 backdrop-blur-md text-white text-xs px-4 py-2 rounded-full shadow-lg">
            👈 Drag or click any garment on the left to try on
          </div>
        </div>
      )}

      {/* ── High-Res Photorealistic Result Modal ── */}
      {showResultModal && aiJob?.result_url && activeGarment && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-lg flex items-center justify-center p-4 sm:p-8">
          <div className="bg-white rounded-3xl shadow-2xl max-w-2xl w-full overflow-hidden flex flex-col max-h-[92vh] border border-gray-100">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-indigo-600" />
                <div>
                  <h2 className="font-bold text-gray-900 text-base">
                    Photorealistic AI Try-On Result
                  </h2>
                  <p className="text-xs text-gray-400">
                    {activeGarment.name} · ${activeGarment.price.toFixed(2)} · Completed in {aiJob.elapsed_s || 25}s
                  </p>
                </div>
              </div>
              <button
                onClick={() => setShowResultModal(false)}
                className="p-2 text-gray-400 hover:text-gray-700 rounded-full hover:bg-gray-100 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body: Generated Image */}
            <div className="relative flex-1 min-h-[380px] bg-stone-950 flex items-center justify-center p-4 overflow-hidden">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`${BACKEND}${aiJob.result_url}`}
                alt="AI Virtual Try-On Result"
                className="max-h-[65vh] w-auto object-contain rounded-2xl shadow-2xl"
              />
            </div>

            {/* Modal Footer Controls */}
            <div className="px-6 py-4 bg-gray-50 border-t border-gray-100 flex items-center justify-between">
              <button
                onClick={() => setShowResultModal(false)}
                className="px-4 py-2 text-xs font-semibold text-gray-600 hover:text-gray-900 transition"
              >
                ← Back to Mirror
              </button>
              <div className="flex items-center gap-3">
                <a
                  href={`${BACKEND}${aiJob.result_url}`}
                  target="_blank"
                  rel="noreferrer"
                  className="px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-800 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition"
                >
                  <Eye className="w-3.5 h-3.5" />
                  <span>Open Fullscreen</span>
                </a>
                <a
                  href={`${BACKEND}${aiJob.result_url}`}
                  download={`tryon_${activeGarment.id}.png`}
                  className="px-5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-semibold flex items-center gap-1.5 shadow-md transition"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Download High-Res</span>
                </a>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
