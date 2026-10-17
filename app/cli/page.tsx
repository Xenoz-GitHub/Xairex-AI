import Link from 'next/link';

export default function CLIPage() {
  return (
    <main className="min-h-screen pt-32 pb-20">
      <div className="container mx-auto px-6 max-w-4xl">
        <Link href="/" className="text-cyan hover:underline mb-8 inline-block">← Back to Home</Link>
        
        <h1 className="text-4xl font-bold text-cyan mb-4">Install Xairex CLI</h1>
        <p className="text-gray-400 mb-8">One command. Fully offline. Zero cloud.</p>

        {/* Prerequisites Section */}
        <div className="bg-terminal border border-cyan/20 rounded-lg p-6 mb-8">
          <h2 className="text-2xl font-bold text-cyan mb-4 flex items-center gap-2">
            <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M6 2a1 1 0 00-1 1v1H4a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V6a2 2 0 00-2-2h-1V3a1 1 0 10-2 0v1H7V3a1 1 0 00-1-1zm0 5a1 1 0 000 2h8a1 1 0 100-2H6z" clipRule="evenodd"/>
            </svg>
            Prerequisites
          </h2>
          <p className="text-gray-400 mb-4">Install these first before running Xairex:</p>
          
          <div className="space-y-6">
            {/* Node.js */}
            <div className="border-l-2 border-cyan pl-4">
              <h3 className="text-cyan font-bold mb-2 flex items-center gap-2">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M3 12v3c0 1.657 3.134 3 7 3s7-1.343 7-3v-3c0 1.657-3.134 3-7 3s-7-1.343-7-3z"/>
                  <path d="M3 7v3c0 1.657 3.134 3 7 3s7-1.343 7-3V7c0 1.657-3.134 3-7 3S3 8.657 3 7z"/>
                  <path d="M17 5c0 1.657-3.134 3-7 3S3 6.657 3 5s3.134-3 7-3 7 1.343 7 3z"/>
                </svg>
                1. Node.js (v18 or later)
              </h3>
              <p className="text-gray-400 text-sm mb-2">Required for the browser extension and web features</p>
              <div className="bg-neural rounded p-3">
                <p className="text-xs text-gray-500 mb-1">Download:</p>
                <a href="https://nodejs.org/" target="_blank" className="text-electric hover:text-cyan transition">
                  https://nodejs.org/
                </a>
                <p className="text-xs text-gray-400 mt-2">Or install via winget:</p>
                <pre className="text-green-400 text-xs mt-1">winget install OpenJS.NodeJS.LTS</pre>
              </div>
            </div>

            {/* Git */}
            <div className="border-l-2 border-electric pl-4">
              <h3 className="text-electric font-bold mb-2 flex items-center gap-2">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M12.316 3.051a1 1 0 01.633 1.265l-4 12a1 1 0 11-1.898-.632l4-12a1 1 0 011.265-.633zM5.707 6.293a1 1 0 010 1.414L3.414 10l2.293 2.293a1 1 0 11-1.414 1.414l-3-3a1 1 0 010-1.414l3-3a1 1 0 011.414 0zm8.586 0a1 1 0 011.414 0l3 3a1 1 0 010 1.414l-3 3a1 1 0 11-1.414-1.414L16.586 10l-2.293-2.293a1 1 0 010-1.414z" clipRule="evenodd"/>
                </svg>
                2. Git
              </h3>
              <p className="text-gray-400 text-sm mb-2">Required to clone the repository</p>
              <div className="bg-neural rounded p-3">
                <p className="text-xs text-gray-500 mb-1">Download:</p>
                <a href="https://git-scm.com/download/win" target="_blank" className="text-electric hover:text-cyan transition">
                  https://git-scm.com/download/win
                </a>
                <p className="text-xs text-gray-400 mt-2">Or install via winget:</p>
                <pre className="text-green-400 text-xs mt-1">winget install Git.Git</pre>
              </div>
            </div>

            {/* Python */}
            <div className="border-l-2 border-green-400 pl-4">
              <h3 className="text-green-400 font-bold mb-2 flex items-center gap-2">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M2 5a2 2 0 012-2h12a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V5zm3.293 1.293a1 1 0 011.414 0l3 3a1 1 0 010 1.414l-3 3a1 1 0 01-1.414-1.414L7.586 10 5.293 7.707a1 1 0 010-1.414zM11 12a1 1 0 100 2h3a1 1 0 100-2h-3z" clipRule="evenodd"/>
                </svg>
                3. Python 3.12
              </h3>
              <p className="text-gray-400 text-sm mb-2">Core runtime for Xairex</p>
              <div className="bg-neural rounded p-3">
                <p className="text-xs text-gray-500 mb-1">Download:</p>
                <a href="https://www.python.org/downloads/" target="_blank" className="text-electric hover:text-cyan transition">
                  https://www.python.org/downloads/
                </a>
                <p className="text-xs text-gray-400 mt-2">Or install via winget:</p>
                <pre className="text-green-400 text-xs mt-1">winget install Python.Python.3.12</pre>
                <p className="text-xs text-yellow-400 mt-2">⚠ Make sure to check "Add Python to PATH" during installation</p>
              </div>
            </div>

            {/* Ollama */}
            <div className="border-l-2 border-purple-400 pl-4">
              <h3 className="text-purple-400 font-bold mb-2 flex items-center gap-2">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M9 2a1 1 0 000 2h2a1 1 0 100-2H9z"/>
                  <path fillRule="evenodd" d="M4 5a2 2 0 012-2 3 3 0 003 3h2a3 3 0 003-3 2 2 0 012 2v11a2 2 0 01-2 2H6a2 2 0 01-2-2V5zm3 4a1 1 0 000 2h.01a1 1 0 100-2H7zm3 0a1 1 0 000 2h3a1 1 0 100-2h-3zm-3 4a1 1 0 100 2h.01a1 1 0 100-2H7zm3 0a1 1 0 100 2h3a1 1 0 100-2h-3z" clipRule="evenodd"/>
                </svg>
                4. Ollama
              </h3>
              <p className="text-gray-400 text-sm mb-2">Local LLM server (automatically installed by Xairex installer)</p>
              <div className="bg-neural rounded p-3">
                <p className="text-xs text-gray-500 mb-1">Download (if manual install needed):</p>
                <a href="https://ollama.com/download/windows" target="_blank" className="text-electric hover:text-cyan transition">
                  https://ollama.com/download/windows
                </a>
                <p className="text-xs text-gray-400 mt-2">The Xairex installer handles this automatically</p>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-terminal border border-cyan/20 rounded-lg p-6 mb-8">
          <h2 className="text-2xl font-bold text-cyan mb-4">Installation Command</h2>
          <p className="text-xs text-gray-500 mb-2">Windows PowerShell (Run as Administrator)</p>
          <pre className="text-cyan text-sm overflow-x-auto bg-neural p-4 rounded">
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
