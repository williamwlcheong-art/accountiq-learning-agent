import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { listTags, postsForTag, tagLabel, tagSlug } from "@/lib/content";
import { formatNzDate } from "@/lib/presentation";
import { SITE_URL } from "@/lib/site";

type Props = { params: Promise<{ tag: string }> };

export function generateStaticParams() {
  return listTags().map((tag) => ({ tag: tagSlug(tag) }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { tag } = await params;
  const label = tagLabel(tag);
  if (!label) return {};
  return {
    title: `${label} | AccountIQ blog`,
    description: `Posts about ${label.toLowerCase()} from AccountIQ.`,
    alternates: { canonical: `${SITE_URL}/blog/tag/${tag}` },
  };
}

export default async function BlogTagPage({ params }: Props) {
  const { tag } = await params;
  const label = tagLabel(tag);
  if (!label) notFound();

  const posts = postsForTag(tag);

  return (
    <section className="marketing-section">
      <div className="marketing-container">
        <nav className="marketing-breadcrumb" aria-label="Breadcrumb">
          <Link href="/blog">Blog</Link>
        </nav>
        <h1>{label}</h1>
        <ul className="marketing-post-list">
          {posts.map((post) => (
            <li key={post.slug}>
              <Link href={`/blog/${post.slug}`}>
                <h2>{post.title}</h2>
                <p>{post.description}</p>
                <time dateTime={post.date}>{formatNzDate(post.date, "long")}</time>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
