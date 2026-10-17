import Link from 'next/link';

export default function CLIPage() {
  return (
    <main className="min-h-screen pt-32 pb-20">
      <div className="container mx-auto px-6 max-w-4xl">
        <Link href="/" className="text-cyan hover:underline mb-8 inline-block">← Back to Home</Link>
        
        <h1 className="text-4xl font-bold text-cyan mb-4">Install Xairex CLI</h1>
        <p className="text-gray-400 mb-8">One command. Fully offline. Zero cloud.</p>

        <div className="bg-terminal border border-cyan/20 rounded-lg p-6 mb-8">
          <p className="text-xs text-gray-500 mb-2">Windows PowerShell</p>
          <pre className="text-cyan text-sm overflow-x-auto">
{`git clone https://github.com/Xenoz-GitHub/Xairex-AI.git
cd Xairex-AI
.\\scripts\\install.ps1`}
          </pre>
        </div>

        <div className="space-y-8">
          <div className="bg-terminal border border-cyan/20 rounded-lg p-6">
            <h2 className="text-2xl font-bold text-cyan mb-4">What Gets Installed</h2>
            <ul className="text-gray-400 space-y-2">
              <li>→ Python 3.12 (if needed)</li>
              <li>→ Ollama (local LLM server)</li>
              <li>→ Whisper model (speech recognition)</li>
              <li>→ Piper voice (text-to-speech)</li>
              <li>→ All required dependencies</li>
            </ul>
          </div>

          <div className="bg-terminal border border-cyan/20 rounded-lg p-6">
            <h2 className="text-2xl font-bold text-cyan mb-4">System Requirements</h2>
            <div className="grid md:grid-cols-2 gap-6">
              <div>
                <h3 className="text-cyan mb-2">Minimum</h3>
                <ul className="text-gray-400 space-y-1">
                  <li>→ Windows 10/11 (64-bit)</li>
                  <li>→ 8GB RAM</li>
                  <li>→ 3GB free disk space</li>
                  <li>→ Any modern CPU</li>
                </ul>
              </div>
              <div>
                <h3 className="text-cyan mb-2">Recommended</h3>
                <ul className="text-gray-400 space-y-1">
                  <li>→ Windows 11 (64-bit)</li>
                  <li>→ 16GB RAM</li>
                  <li>→ 5GB free disk space</li>
                  <li>→ Intel i5/Ryzen 5 or better</li>
                </ul>
              </div>
            </div>
          </div>

          <div className="bg-terminal border border-cyan/20 rounded-lg p-6">
            <h2 className="text-2xl font-bold text-cyan mb-4">Installation Steps</h2>
            <ol className="space-y-3 text-gray-300">
              <li className="flex gap-3">
                <span className="text-cyan font-bold">1.</span>
                <span>Clone the repository from GitHub</span>
              </li>
              <li className="flex gap-3">
                <span className="text-cyan font-bold">2.</span>
                <span>Run the installer script (automatically downloads everything)</span>
              </li>
              <li className="flex gap-3">
                <span className="text-cyan font-bold">3.</span>
                <span>Wait 10-15 minutes for dependencies to install</span>
              </li>
              <li className="flex gap-3">
                <span className="text-cyan font-bold">4.</span>
                <span>Launch Xairex from your desktop or run: python app.py --gui</span>
              </li>
            </ol>
          </div>
        </div>
      </div>
    </main>
  );
}
