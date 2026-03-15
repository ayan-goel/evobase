import type { Metadata } from "next";
import { DM_Sans } from "next/font/google";
import "./globals.css";

const dmSans = DM_Sans({
  variable: "--font-dm-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "Evobase",
  description: "Autonomous code optimization system",
  icons: {
    icon: "/evobase-icon.png",
    apple: "/evobase-icon.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="icon" href="/favicon-32.png" sizes="32x32" type="image/png" />
        <link rel="icon" href="/evobase-icon.png" sizes="192x192" type="image/png" />
        <link rel="apple-touch-icon" href="/evobase-icon.png" />
      </head>
      <body className={`${dmSans.variable} antialiased bg-black text-white`}>
        {children}
      </body>
    </html>
  );
}
