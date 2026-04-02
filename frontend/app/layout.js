import "./globals.css";

export const metadata = {
  title: "Voice EMR - HBCH Punjab",
  description: "Voice-based electronic medical records for hospital consultations",
  icons: {
    icon: "/hbch-logo.png",
    shortcut: "/hbch-logo.png",
    apple: "/hbch-logo.png",
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
