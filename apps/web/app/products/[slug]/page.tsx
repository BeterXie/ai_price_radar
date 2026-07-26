import { notFound, permanentRedirect } from "next/navigation";
import { getProduct } from "@/lib/api";

export const dynamic = "force-dynamic";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

export default async function ProductPage({ params, searchParams }: { params: Promise<{ slug: string }>; searchParams: SearchParams }) {
  const [{ slug }, rawParams] = await Promise.all([params, searchParams]);
  const product = await getProduct(slug, "comparable=true");
  if (!product) notFound();

  const query = new URLSearchParams({ platform: product.platform, product: product.slug });
  for (const [key, rawValue] of Object.entries(rawParams)) {
    if (["platform", "product"].includes(key)) continue;
    const value = Array.isArray(rawValue) ? rawValue.at(-1) : rawValue;
    if (value) query.set(key, value);
  }
  permanentRedirect(`/products?${query.toString()}`);
}
