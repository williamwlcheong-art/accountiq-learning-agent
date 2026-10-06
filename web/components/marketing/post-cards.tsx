import Link from "next/link";

import type { PostMeta } from "@/lib/content";
import { formatNzDate } from "@/lib/presentation";

/** Blog posts as cards: the blog index, a tag page and the home page all use this. */
export function PostCards({ posts, headingLevel = 2 }: { posts: PostMeta[]; headingLevel?: 2 | 3 }) {
  const Heading = headingLevel === 2 ? "h2" : "h3";
  return (
    <ul className="home-posts">
      {posts.map((post) => (
        <li key={post.slug}>
          <Link href={`/blog/${post.slug}`}>
            <time dateTime={post.date}>{formatNzDate(post.date, "long")}</time>
            <Heading>{post.title}</Heading>
            <p>{post.description}</p>
          </Link>
        </li>
      ))}
    </ul>
  );
}
