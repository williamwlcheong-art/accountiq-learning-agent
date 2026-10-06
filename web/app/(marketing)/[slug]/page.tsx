import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { getPage, listPageSlugs } from "@/lib/content";
import { formatNzDate } from "@/lib/presentation";
import { SITE_URL } from "@/lib/site";

type Props = { params: Promise<{ slug: string }> };

export function generateStaticParams() {
  return listPageSlugs().map((slug) => ({ slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const page = await getPage(slug);
  if (!page) return {};
  return {
    title: `${page.meta.title} | AccountIQ`,
    description: page.meta.description,
    alternates: { canonical: `${SITE_URL}/${slug}` },
    openGraph: {
      title: page.meta.title,
      description: page.meta.description,
      url: `${SITE_URL}/${slug}`,
      type: "article",
    },
  };
}

export default async function ContentPage({ params }: Props) {
  const { slug } = await params;
  const page = await getPage(slug);
  if (!page) notFound();

  return (
    <article className="article">
      <div className="marketing-container article-column">
        <header className="article-head">
          <h1>{page.meta.title}</h1>
          <p className="article-lede">{page.meta.description}</p>
          {page.meta.updated ? (
            <p className="article-meta">
              Last reviewed <time dateTime={page.meta.updated}>{formatNzDate(page.meta.updated, "long")}</time>
            </p>
          ) : null}
        </header>
        <div className="prose" dangerouslySetInnerHTML={{ __html: page.html }} />
      </div>
    </article>
  );
}
