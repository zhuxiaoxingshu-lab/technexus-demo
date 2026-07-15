import type { Metadata } from "next";
import { headers } from "next/headers";
import "./globals.css";

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const host = requestHeaders.get("x-forwarded-host") || requestHeaders.get("host") || "localhost:3000";
  const protocol = requestHeaders.get("x-forwarded-proto") || (host.startsWith("localhost") ? "http" : "https");
  const metadataBase = new URL(`${protocol}://${host}`);
  const title = "元数智转｜AI 技术转移平台";
  const description = "基于真实产业技术需求库和 AI 技术任务拆解的成果匹配与技术经理人对接平台。";
  return {
    metadataBase,
    title: { default: title, template: "%s｜元数智转" },
    description,
    icons: { icon: "/favicon.ico" },
    openGraph: { title, description, type: "website", images: [{ url: new URL("/og.png", metadataBase), width: 1200, height: 630, alt: "元数智转 AI 技术转移平台" }] },
    twitter: { card: "summary_large_image", title, description, images: [new URL("/og.png", metadataBase)] },
  };
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}
