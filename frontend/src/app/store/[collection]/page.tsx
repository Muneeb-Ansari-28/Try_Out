import Link from "next/link";
import Image from "next/image";
import type { Garment } from "@/components/TryOnWidget";

const BACKEND = "http://127.0.0.1:8000";

async function getGarments(): Promise<Garment[]> {
  try {
    const res = await fetch(`${BACKEND}/api/garments`, { cache: "no-store" });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

// [FIX H9] In Next 15, params is a Promise<{ collection: string }>
export default async function StorePage({
  params,
}: {
  params: Promise<{ collection: string }>;
}) {
  const { collection } = await params;
  const allGarments = await getGarments();

  // Filter if collection is not 'all' or 'default'
  const filtered =
    collection === "all" || collection === "default"
      ? allGarments
      : allGarments.filter((g) => g.collection === collection);

  return (
    <div className="min-h-screen bg-stone-50 py-10 px-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 capitalize tracking-tight">
              {collection} Collection
            </h1>
            <p className="text-sm text-gray-400 mt-1">
              {filtered.length} pieces available
            </p>
          </div>
          <Link
            href="/"
            className="px-5 py-2.5 bg-gray-900 hover:bg-black text-white rounded-full text-xs font-semibold shadow-md transition"
          >
            ← Open Mirror
          </Link>
        </div>

        {/* Product Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-5">
          {filtered.map((g) => (
            <div
              key={g.id}
              className="bg-white rounded-2xl overflow-hidden border border-gray-100 shadow-sm hover:shadow-md transition flex flex-col justify-between"
            >
              <div className="aspect-square relative p-4 bg-stone-100">
                <Image
                  src={`${BACKEND}/garments/${g.file}`}
                  alt={g.name}
                  fill
                  className="object-contain p-4"
                  unoptimized
                />
              </div>

              <div className="p-4 flex flex-col justify-between flex-1">
                <div>
                  <h2 className="text-sm font-semibold text-gray-900 truncate">
                    {g.name}
                  </h2>
                  <p className="text-xs text-gray-400 mt-0.5">
                    ${g.price.toFixed(2)}
                  </p>
                </div>
                <div className="mt-4">
                  {/* [FIX M3] Direct deep link with query parameter */}
                  <Link
                    href={`/?garment=${g.id}`}
                    className="block w-full text-center py-2 bg-gray-900 hover:bg-black text-white rounded-xl text-xs font-medium transition"
                  >
                    Try On in Mirror →
                  </Link>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

