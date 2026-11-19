import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono, Noto_Sans_Bengali, Space_Grotesk } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const spaceGrotesk = Space_Grotesk({
  variable: "--font-space",
  subsets: ["latin"],
  weight: ["500", "600", "700"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

const notoBengali = Noto_Sans_Bengali({
  variable: "--font-bengali",
  subsets: ["bengali", "latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "PathShalaAI — এনসিটিবি প্রাথমিক গৃহশিক্ষক",
  description: "এনসিটিবি প্রাথমিক শ্রেণি (১-৫) পাঠ্যবই ভিত্তিক নির্ভরযোগ্য বাংলা এআই গৃহশিক্ষক",
  manifest: "/manifest.json",
};

export const viewport: Viewport = {
  themeColor: "#08080d",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="bn"
      className={`${inter.variable} ${spaceGrotesk.variable} ${jetbrainsMono.variable} ${notoBengali.variable} dark h-full antialiased`}
    >
      <body className="min-h-full bg-[#08080d] text-[#eef2f3] font-sans selection:bg-[#00e5ff] selection:text-[#001318]">
        {children}
      </body>
    </html>
  );
}
