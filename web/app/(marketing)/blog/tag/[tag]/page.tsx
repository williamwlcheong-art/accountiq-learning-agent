import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { PostCards } from "@/components/marketing/post-cards";
import { listTags, postsForTag, tagLabel, tagSlug } from "@/lib/content";
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

  return (
    <section className="home-section" aria-labelledby="tag-title">
      <div className="marketing-container">
        <header className="article-head blog-head">
          <nav className="breadcrumb" aria-label="Breadcrumb">
            <Link href="/blog">Blog</Link>
          </nav>
          <h1 id="tag-title">{label}</h1>
        </header>
        <PostCards posts={postsForTag(tag)} />
      </div>
    </section>
  );
}
