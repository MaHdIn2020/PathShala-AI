import type { Metadata } from "next";
import { Noto_Sans_Bengali } from "next/font/google";
import "./globals.css";

const notoBengali = Noto_Sans_Bengali({
  variable: "--font-noto-bengali",
  subsets: ["bengali", "latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "পাঠশালা এআই (PathShala AI) — এনসিটিবি প্রাথমিক পাঠ্যবই সহায়ক",
  description: "এনসিটিবি প্রাথমিক শ্রেণি (১-৫) পাঠ্যবই ভিত্তিক নির্ভরযোগ্য বাংলা গৃহশিক্ষক",
  manifest: "/manifest.json",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="bn" className={`${notoBengali.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col font-sans">{children}</body>
    </html>
  );
}
