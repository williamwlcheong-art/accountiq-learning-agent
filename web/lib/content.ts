import fs from "node:fs";
import path from "node:path";

import matter from "gray-matter";
import { remark } from "remark";
import remarkHtml from "remark-html";

const CONTENT_ROOT = path.join(process.cwd(), "content");
const PAGES_DIR = path.join(CONTENT_ROOT, "pages");
const POSTS_DIR = path.join(CONTENT_ROOT, "posts");

// Drafts are visible while developing and left out of the build.
const SHOW_DRAFTS = process.env.NODE_ENV === "development";

export type PageMeta = {
  slug: string;
  title: string;
  description: string;
  updated?: string;
};

export type PostMeta = PageMeta & {
  date: string;
  author: string;
  tags: string[];
  image?: string;
};

export type Document<Meta> = {
  meta: Meta;
  html: string;
};

function readDir(dir: string): string[] {
  if (!fs.existsSync(dir)) return [];
  return fs
    .readdirSync(dir)
    .filter((name) => name.endsWith(".md"))
    .map((name) => name.replace(/\.md$/, ""));
}

function readFile(dir: string, slug: string) {
  const file = path.join(dir, `${slug}.md`);
  if (!fs.existsSync(file)) return null;
  return matter(fs.readFileSync(file, "utf8"));
}

function requireString(value: unknown, field: string, where: string): string {
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(`Content file ${where} is missing a "${field}" value in its front matter.`);
  }
  return value.trim();
}

/**
 * YAML parses an unquoted `2026-09-16` into a Date, so a date field arrives as
 * either a Date or a string depending on how the author wrote it. Both are
 * normalised to `YYYY-MM-DD`.
 */
function asDateString(value: unknown): string | undefined {
  if (value instanceof Date && !Number.isNaN(value.getTime())) {
    return value.toISOString().slice(0, 10);
  }
  if (typeof value === "string" && value.trim()) return value.trim();
  return undefined;
}

function requireDate(value: unknown, field: string, where: string): string {
  const date = asDateString(value);
  if (!date) {
    throw new Error(`Content file ${where} is missing a "${field}" value in its front matter.`);
  }
  return date;
}

function isDraft(data: Record<string, unknown>): boolean {
  return data.draft === true;
}

/**
 * Markdown bodies come from files committed to this repo, never from users or
 * from the AI pipeline. remark-html sanitises by default, so raw HTML written
 * inside a Markdown file is stripped rather than rendered.
 */
async function toHtml(body: string): Promise<string> {
  const processed = await remark().use(remarkHtml).process(body);
  return processed.toString();
}

function pageMeta(slug: string, data: Record<string, unknown>, where: string): PageMeta {
  return {
    slug,
    title: requireString(data.title, "title", where),
    description: requireString(data.description, "description", where),
    updated: asDateString(data.updated),
  };
}

function postMeta(slug: string, data: Record<string, unknown>): PostMeta {
  const where = `posts/${slug}.md`;
  return {
    ...pageMeta(slug, data, where),
    date: requireDate(data.date, "date", where),
    author: typeof data.author === "string" ? data.author : "William Cheong",
    tags: Array.isArray(data.tags) ? data.tags.map(String) : [],
    image: typeof data.image === "string" ? data.image : undefined,
  };
}

export function listPageSlugs(): string[] {
  return readDir(PAGES_DIR).filter((slug) => {
    const file = readFile(PAGES_DIR, slug);
    return file ? SHOW_DRAFTS || !isDraft(file.data) : false;
  });
}

export async function getPage(slug: string): Promise<Document<PageMeta> | null> {
  const file = readFile(PAGES_DIR, slug);
  if (!file) return null;
  if (isDraft(file.data) && !SHOW_DRAFTS) return null;
  return {
    meta: pageMeta(slug, file.data, `pages/${slug}.md`),
    html: await toHtml(file.content),
  };
}

export function listPosts(): PostMeta[] {
  return readDir(POSTS_DIR)
    .map((slug) => {
      const file = readFile(POSTS_DIR, slug);
      if (!file) return null;
      if (isDraft(file.data) && !SHOW_DRAFTS) return null;
      return postMeta(slug, file.data);
    })
    .filter((post): post is PostMeta => post !== null)
    .sort((a, b) => b.date.localeCompare(a.date));
}

export async function getPost(slug: string): Promise<Document<PostMeta> | null> {
  const file = readFile(POSTS_DIR, slug);
  if (!file) return null;
  if (isDraft(file.data) && !SHOW_DRAFTS) return null;
  return {
    meta: postMeta(slug, file.data),
    html: await toHtml(file.content),
  };
}

export function listTags(): string[] {
  const tags = new Set<string>();
  for (const post of listPosts()) {
    for (const tag of post.tags) tags.add(tag);
  }
  return [...tags].sort();
}

export function tagSlug(tag: string): string {
  return tag.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}

export function postsForTag(slug: string): PostMeta[] {
  return listPosts().filter((post) => post.tags.some((tag) => tagSlug(tag) === slug));
}

export function tagLabel(slug: string): string | null {
  for (const tag of listTags()) {
    if (tagSlug(tag) === slug) return tag;
  }
  return null;
}
