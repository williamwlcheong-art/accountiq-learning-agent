import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { getPost, listPosts, tagSlug } from "@/lib/content";
import { formatNzDate } from "@/lib/presentation";
import { REGISTER_PATH, SITE_URL, appUrl } from "@/lib/site";

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
    <article className="marketing-section">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify([articleSchema, breadcrumbSchema]) }}
      />
      <div className="marketing-container marketing-article">
        <nav className="marketing-breadcrumb" aria-label="Breadcrumb">
          <Link href="/blog">Blog</Link>
        </nav>
        <h1>{meta.title}</h1>
        <p className="marketing-article-meta">
          {meta.author}. <time dateTime={meta.date}>{formatNzDate(meta.date, "long")}</time>
          {meta.updated ? (
            <>
              {". Last reviewed "}
              <time dateTime={meta.updated}>{formatNzDate(meta.updated, "long")}</time>
            </>
          ) : null}
        </p>
        <div className="prose" dangerouslySetInnerHTML={{ __html: post.html }} />

        {meta.tags.length ? (
          <nav className="marketing-tag-list" aria-label="Tags">
            {meta.tags.map((tag) => (
              <Link key={tag} href={`/blog/tag/${tagSlug(tag)}`}>
                {tag}
              </Link>
            ))}
          </nav>
        ) : null}

        <aside className="marketing-post-cta">
          <h2>Wondering what your own business is worth?</h2>
          <p>
            AccountIQ prepares an indicative valuation report from your financial statements for one fixed fee, and a
            reviewer checks it before it reaches you.
          </p>
          <Link className="marketing-cta" href={appUrl(REGISTER_PATH)}>
            Get a business valuation
          </Link>
        </aside>
      </div>
    </article>
  );
}
