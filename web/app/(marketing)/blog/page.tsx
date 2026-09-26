import type { Metadata } from "next";
import Link from "next/link";

import { listPosts, listTags, tagSlug } from "@/lib/content";
import { formatNzDate } from "@/lib/presentation";
import { SITE_URL } from "@/lib/site";

export const metadata: Metadata = {
  title: "Blog | AccountIQ",
  description: "Plain-English writing about what a business is worth and how buyers and lenders look at one.",
  alternates: { canonical: `${SITE_URL}/blog` },
};

export default function BlogIndexPage() {
  const posts = listPosts();
  const tags = listTags();

  return (
    <section className="marketing-section">
      <div className="marketing-container">
        <h1>Blog</h1>
        <p className="marketing-article-lede">
          What a business is worth, and how buyers, lenders and shareholders look at one.
        </p>

        {tags.length ? (
          <nav className="marketing-tag-list" aria-label="Post tags">
            {tags.map((tag) => (
              <Link key={tag} href={`/blog/tag/${tagSlug(tag)}`}>
                {tag}
              </Link>
            ))}
          </nav>
        ) : null}

        {posts.length ? (
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
        ) : (
          <p>The first posts are being written. Check back shortly.</p>
        )}
      </div>
    </section>
  );
}
