import { Header, Footer } from "@compute3/shared-ui";
import Link from "next/link";
import { notFound } from "next/navigation";
import fs from "fs";
import path from "path";
import templatesIndex from "@/content/comfyui/index.json";
import ClientParticleCanvas from "@/components/ClientParticleCanvas";

type Template = {
  template_id: string;
  title: string;
  description: string;
  bundle: string;
  output_type: string;
  tags: string[];
};

type Frontmatter = {
  title: string;
  description: string;
  template_id: string;
  bundle: string;
  output_type: string;
  thumbnail: string;
  tags: string[];
  tutorial_url: string;
  date: string;
  models: string[];
};

function parseMarkdownTable(content: string): { headers: string[]; rows: string[][] } | null {
  const lines = content.trim().split("\n");
  if (lines.length < 2) return null;

  const headers = lines[0].split("|").map(h => h.trim()).filter(Boolean);
  const rows = lines.slice(2).map(line =>
    line.split("|").map(cell => cell.trim()).filter(Boolean)
  );

  return { headers, rows };
}

function parseMdxFile(templateId: string): { frontmatter: Frontmatter; sections: Record<string, string> } | null {
  try {
    const mdxPath = path.join(process.cwd(), "content", "comfyui", templateId, "index.mdx");
    const content = fs.readFileSync(mdxPath, "utf-8");

    // Parse frontmatter
    const fmMatch = content.match(/^---\n([\s\S]*?)\n---/);
    if (!fmMatch) return null;

    const fmLines = fmMatch[1].split("\n");
    const frontmatter: Record<string, any> = {};
    for (const line of fmLines) {
      const [key, ...valueParts] = line.split(": ");
      if (key && valueParts.length) {
        const value = valueParts.join(": ");
        try {
          frontmatter[key.trim()] = JSON.parse(value);
        } catch {
          frontmatter[key.trim()] = value;
        }
      }
    }

    // Parse sections
    const body = content.slice(fmMatch[0].length);
    const sections: Record<string, string> = {};
    const sectionRegex = /## ([^\n]+)\n([\s\S]*?)(?=\n## |$)/g;
    let match;
    while ((match = sectionRegex.exec(body)) !== null) {
      sections[match[1].trim()] = match[2].trim();
    }

    return { frontmatter: frontmatter as Frontmatter, sections };
  } catch {
    return null;
  }
}

export async function generateStaticParams() {
  return templatesIndex.templates.map((t: Template) => ({
    template: t.template_id,
  }));
}

export default async function TemplatePage({ params }: { params: Promise<{ template: string }> }) {
  const { template: templateId } = await params;

  const templateMeta = templatesIndex.templates.find(
    (t: Template) => t.template_id === templateId
  );

  if (!templateMeta) {
    notFound();
  }

  const parsed = parseMdxFile(templateId);
  if (!parsed) {
    notFound();
  }

  const { frontmatter, sections } = parsed;

  return (
    <>
      <Header />
      <main className="min-h-screen bg-white">
        {/* Hero Section - Two Column Layout */}
        <div className="relative py-12 sm:py-16 bg-gradient-to-br from-white via-gray-50 to-[var(--gradient-start)] overflow-hidden">
          <ClientParticleCanvas />
          <div className="relative z-20 max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
            {/* Breadcrumb */}
            <nav className="mb-6 text-sm">
              <Link href="/playground" className="text-gray-500 hover:text-[var(--color-primary)] hover:underline transition-colors">
                Playground
              </Link>
              <span className="text-gray-400 mx-2">/</span>
              <Link href="/playground/comfyui" className="text-gray-500 hover:text-[var(--color-primary)] hover:underline transition-colors">
                ComfyUI Templates
              </Link>
              <span className="text-gray-400 mx-2">/</span>
              <span className="text-gray-900 font-medium">{frontmatter.title}</span>
            </nav>

            {/* Two Column Hero */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 lg:gap-12 items-start">
              {/* Left Column - Info */}
              <div>
                {/* Tags */}
                <div className="flex flex-wrap items-center gap-2 mb-4">
                  <span className="px-3 py-1 bg-white border border-gray-200 rounded-full text-sm font-medium text-gray-700">
                    {frontmatter.output_type}
                  </span>
                  {frontmatter.tags?.map((tag, i) => (
                    <span key={i} className="px-3 py-1 bg-[var(--gradient-start)] text-[var(--color-primary)] rounded-full text-sm font-medium">
                      {tag}
                    </span>
                  ))}
                </div>

                <h1 className="text-3xl md:text-4xl font-extrabold tracking-tighter text-gray-900 mb-4">
                  {frontmatter.title}
                </h1>

                {frontmatter.description && (
                  <p className="text-lg text-gray-600 mb-6">
                    {frontmatter.description}
                  </p>
                )}

                {/* Quick Actions */}
                <div className="flex flex-wrap gap-3">
                  <Link
                    href="#usage"
                    className="btn-primary text-white font-semibold py-2.5 px-5 rounded-lg text-sm"
                  >
                    Get Started
                  </Link>
                  {frontmatter.tutorial_url && (
                    <a
                      href={frontmatter.tutorial_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-2 bg-white border border-gray-200 text-gray-700 font-medium py-2.5 px-5 rounded-lg text-sm hover:border-gray-300 transition-colors"
                    >
                      View Tutorial
                      <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                        <path d="M11 3a1 1 0 100 2h2.586l-6.293 6.293a1 1 0 101.414 1.414L15 6.414V9a1 1 0 102 0V4a1 1 0 00-1-1h-5z" />
                        <path d="M5 5a2 2 0 00-2 2v8a2 2 0 002 2h8a2 2 0 002-2v-3a1 1 0 10-2 0v3H5V7h3a1 1 0 000-2H5z" />
                      </svg>
                    </a>
                  )}
                </div>
              </div>

              {/* Right Column - Thumbnail */}
              {frontmatter.thumbnail && (
                <div className="bg-white rounded-2xl overflow-hidden border border-gray-200 shadow-lg">
                  <img
                    src={frontmatter.thumbnail}
                    alt={frontmatter.title}
                    className="w-full aspect-square object-cover"
                  />
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Content */}
        <section className="py-12 bg-white">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">

            {/* About */}
            {sections["About"] && (
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">About</h2>
                <div className="prose prose-gray max-w-none">
                  <p className="text-gray-600 whitespace-pre-wrap">{sections["About"]}</p>
                </div>
              </div>
            )}

            {/* Parameters */}
            {sections["Parameters"] && (
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">Parameters</h2>
                <div className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-gray-50 border-b border-gray-200">
                          <th className="text-left py-3 px-4 font-semibold text-gray-600">Parameter</th>
                          <th className="text-left py-3 px-4 font-semibold text-gray-600">Type</th>
                          <th className="text-left py-3 px-4 font-semibold text-gray-600">Default</th>
                          <th className="text-left py-3 px-4 font-semibold text-gray-600">Description</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(() => {
                          const table = parseMarkdownTable(sections["Parameters"]);
                          if (!table) return null;
                          return table.rows.map((row, i) => (
                            <tr key={i} className="border-b border-gray-100 last:border-0">
                              {row.map((cell, j) => (
                                <td key={j} className="py-3 px-4 text-gray-700">
                                  {j === 0 ? (
                                    <code className="bg-gray-100 px-2 py-0.5 rounded text-sm font-mono text-gray-800">
                                      {cell.replace(/`/g, "")}
                                    </code>
                                  ) : (
                                    cell.replace(/`/g, "")
                                  )}
                                </td>
                              ))}
                            </tr>
                          ));
                        })()}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {/* Usage */}
            {sections["Usage"] && (
              <div id="usage" className="mb-10 scroll-mt-8">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">Usage</h2>
                <div className="code-block-glow">
                  <pre className="bg-gray-900 rounded-xl p-5 overflow-x-auto text-sm">
                    <code className="text-green-400 font-mono">
                      {sections["Usage"].replace(/```bash\n?|\n?```/g, "").trim()}
                    </code>
                  </pre>
                </div>
              </div>
            )}

            {/* Required Models */}
            {sections["Required Models"] && (
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">Required Models</h2>
                <ul className="space-y-2">
                  {sections["Required Models"].split("\n").filter(Boolean).map((line, i) => (
                    <li key={i} className="flex items-center gap-3 text-gray-700">
                      <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-primary)]"></span>
                      <code className="bg-gray-100 px-3 py-1.5 rounded-lg text-sm font-mono text-gray-800">
                        {line.replace(/^-\s*`?|`?\s*\([^)]+\)\s*$/g, "").trim()}
                      </code>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Example Prompt */}
            {sections["Example Prompt"] && (
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">Example Prompt</h2>
                <pre className="bg-gray-100 border border-gray-200 rounded-xl p-5 overflow-x-auto text-sm text-gray-700 whitespace-pre-wrap font-mono">
                  {sections["Example Prompt"].replace(/```\n?|\n?```/g, "").trim()}
                </pre>
              </div>
            )}

            {/* CTA */}
            <div className="mt-12 p-8 bg-gradient-to-br from-[var(--gradient-start)] to-[var(--gradient-end)] rounded-2xl border border-gray-200">
              <h3 className="text-2xl font-bold text-gray-900 mb-2">Ready to run this template?</h3>
              <p className="text-gray-600 mb-6">
                Install the Compute3 CLI and run this template on GPU in seconds.
              </p>
              <div className="code-block-glow mb-6">
                <pre className="bg-gray-900 rounded-xl p-4 overflow-x-auto text-sm">
                  <code className="text-green-400 font-mono">pip install c3cli && c3 comfyui run {templateId}</code>
                </pre>
              </div>
              <Link
                href="/docs/comfyui"
                className="inline-flex items-center gap-2 btn-primary text-white font-semibold py-3 px-6 rounded-lg"
              >
                View Documentation
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z" clipRule="evenodd" />
                </svg>
              </Link>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
