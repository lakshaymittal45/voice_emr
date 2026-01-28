import Link from "next/link";


export default function Home() {
return (
<main style={{ padding: 32, maxWidth: 900, margin: "auto" }}>
<h1>🎙 Voice-Based EMR System</h1>


<p style={{ marginTop: 12, fontSize: 18 }}>
AI-powered system to convert doctor–patient conversations into
structured clinical notes.
</p>


<hr style={{ margin: "24px 0" }} />


<h2>🚀 Get Started</h2>


<Link href="/upload">
<button style={{ padding: "10px 18px", fontSize: 16 }}>
➕ Upload Consultation
</button>
</Link>
</main>
);
}