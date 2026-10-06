import type { Metadata } from "next";
import Link from "next/link";

import { PostCards } from "@/components/marketing/post-cards";
import { listPosts, listTags, tagSlug } from "@/lib/content";
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
    <section className="home-section" aria-labelledby="blog-title">
      <div className="marketing-container">
        <header className="article-head blog-head">
          <h1 id="blog-title">Writing for business owners</h1>
          <p className="article-lede">What a business is worth, and how buyers, lenders and shareholders look at one.</p>
          {tags.length ? (
            <nav className="tag-list" aria-label="Post tags">
              {tags.map((tag) => (
                <Link key={tag} href={`/blog/tag/${tagSlug(tag)}`}>
                  {tag}
                </Link>
              ))}
            </nav>
          ) : null}
        </header>

        {posts.length ? <PostCards posts={posts} /> : <p className="blog-empty">The first posts are being written. Check back shortly.</p>}
      </div>
    </section>
  );
}
