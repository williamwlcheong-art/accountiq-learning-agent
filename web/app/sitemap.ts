import type { MetadataRoute } from "next";

import { listPageSlugs, listPosts, listTags, tagSlug } from "@/lib/content";
import { SITE_URL } from "@/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  const staticRoutes = ["", "/valuation", "/blog"].map((route) => ({
    url: `${SITE_URL}${route}`,
    changeFrequency: "monthly" as const,
    priority: route === "" ? 1 : 0.8,
  }));

  const pages = listPageSlugs().map((slug) => ({
    url: `${SITE_URL}/${slug}`,
    changeFrequency: "yearly" as const,
    priority: 0.6,
  }));

  const posts = listPosts().map((post) => ({
    url: `${SITE_URL}/blog/${post.slug}`,
    lastModified: new Date(post.updated || post.date),
    changeFrequency: "yearly" as const,
    priority: 0.6,
  }));

  const tags = listTags().map((tag) => ({
    url: `${SITE_URL}/blog/tag/${tagSlug(tag)}`,
    changeFrequency: "monthly" as const,
    priority: 0.3,
  }));

  return [...staticRoutes, ...pages, ...posts, ...tags];
}
