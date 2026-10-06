import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Arrow } from "@/components/marketing/arrow";
import { getPost, listPosts, tagSlug } from "@/lib/content";
import { formatNzDate } from "@/lib/presentation";
import { FEE, REGISTER_PATH, REVIEWER, SITE_URL, appUrl } from "@/lib/site";

type Props = { params: Promise<{ slug: string }> };

export function generateStaticParams() {
  return listPosts().map((post) => ({ slug: post.slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const post = await getPost(slug);
  if (!post) return {};
  const url = `${SITE_URL}/blog/${slug}`;
  return {
    title: `${post.meta.title} | AccountIQ`,
    description: post.meta.description,
    alternates: { canonical: url },
    openGraph: {
      title: post.meta.title,
      description: post.meta.description,
      url,
      type: "article",
      publishedTime: post.meta.date,
      modifiedTime: post.meta.updated,
      authors: [post.meta.author],
      images: post.meta.image ? [post.meta.image] : undefined,
    },
  };
}

export default async function BlogPostPage({ params }: Props) {
  const { slug } = await params;
  const post = await getPost(slug);
  if (!post) notFound();

  const { meta } = post;
  const articleSchema = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: meta.title,
    description: meta.description,
    datePublished: meta.date,
    dateModified: meta.updated || meta.date,
    author: { "@type": "Person", name: meta.author },
    publisher: { "@type": "Organization", name: "AccountIQ" },
    mainEntityOfPage: `${SITE_URL}/blog/${slug}`,
  };
  const breadcrumbSchema = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Blog", item: `${SITE_URL}/blog` },
      { "@type": "ListItem", position: 2, name: meta.title, item: `${SITE_URL}/blog/${slug}` },
    ],
  };

  return (
    <article className="article">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify([articleSchema, breadcrumbSchema]) }}
      />
      <div className="marketing-container article-column">
        <header className="article-head">
          <nav className="breadcrumb" aria-label="Breadcrumb">
            <Link href="/blog">Blog</Link>
          </nav>
          <h1>{meta.title}</h1>
          <p className="article-meta">
            {meta.author}. <time dateTime={meta.date}>{formatNzDate(meta.date, "long")}</time>
            {meta.updated ? (
              <>
                {". Last reviewed "}
                <time dateTime={meta.updated}>{formatNzDate(meta.updated, "long")}</time>
              </>
            ) : null}
          </p>
        </header>
        <div className="prose" dangerouslySetInnerHTML={{ __html: post.html }} />

        {meta.tags.length ? (
          <nav className="tag-list" aria-label="Tags">
            {meta.tags.map((tag) => (
              <Link key={tag} href={`/blog/tag/${tagSlug(tag)}`}>
                {tag}
              </Link>
            ))}
          </nav>
        ) : null}

        <aside className="article-cta" aria-labelledby="article-cta-title">
          <h2 id="article-cta-title">Wondering what your own business is worth?</h2>
          <p>
            AccountIQ works out an indicative valuation from your own financial statements. {FEE.display}, checked by{" "}
            {REVIEWER.name} {REVIEWER.credential}.
          </p>
          <Link className="home-button" href={appUrl(REGISTER_PATH)}>
            Start your valuation
            <Arrow />
          </Link>
        </aside>
      </div>
    </article>
  );
}
