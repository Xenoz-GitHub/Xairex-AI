'use client';

import { motion } from 'framer-motion';
import Link from 'next/link';
import { NeuralCore } from '@/components/NeuralCore';

export default function HomePage() {
  return (
    <main className="min-h-screen">
      {/* Header */}
      <header className="fixed top-0 left-0 right-0 z-50 bg-neural/80 backdrop-blur border-b border-cyan/20">
        <div className="container mx-auto px-6 py-4 flex justify-between items-center">
          <div className="flex items-center gap-3">
            <img src="/iconxairex.png" alt="Xairex" className="w-8 h-8" />
            <span className="text-xl text-cyan">XAIREX</span>
            <span className="text-xs text-gray-500">v0.1.0</span>
          </div>
          
          <nav className="hidden md:flex gap-6 text-sm">
            <Link href="/#about" className="hover:text-cyan transition">About</Link>
            <Link href="/cli" className="hover:text-cyan transition">CLI</Link>
            <Link href="https://github.com/Xenoz-GitHub/Xairex-AI" target="_blank" className="px-4 py-2 border border-cyan text-cyan hover:bg-cyan hover:text-neural transition rounded">
              GitHub
            </Link>
          </nav>

          <div className="hidden lg:flex gap-2 text-xs">
            <span className="px-2 py-1 border border-green-400 text-green-400 rounded">OFFLINE</span>
            <span className="px-2 py-1 border border-electric text-electric rounded">CPU-ONLY</span>
            <span className="px-2 py-1 border border-purple-400 text-purple-400 rounded">NO CLOUD</span>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="pt-32 pb-20">
        <div className="container mx-auto px-6">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            {/* Terminal */}
            <motion.div
              initial={{ opacity: 0, x: -50 }}
              animate={{ opacity: 1, x: 0 }}
              className="bg-terminal border border-cyan/20 rounded-lg p-8"
            >
              <div className="flex gap-2 mb-4">
                <div className="w-3 h-3 rounded-full bg-red-500"></div>
                <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                <div className="w-3 h-3 rounded-full bg-green-500"></div>
              </div>

              <div className="mb-6">
                <h1 className="text-4xl font-bold text-cyan mb-2">XAIREX</h1>
                <p className="text-gray-400">OFFLINE NEURAL VOICE ASSISTANT</p>
                <p className="text-green-400 text-sm mt-2">● SYSTEM READY</p>
              </div>

              <div className="space-y-2 text-sm text-gray-500">
                <p>→ Local speech-to-text (Whisper)</p>
                <p>→ Local LLM brain (Ollama)</p>
                <p>→ Local text-to-speech (Piper)</p>
                <p>→ 23 OS integration tools</p>
                <p>→ Zero cloud dependencies</p>
              </div>

              <div className="mt-8 pt-6 border-t border-cyan/20">
                <p className="text-xs text-gray-600 mb-3">RUNTIME METRICS</p>
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div><span className="text-gray-500">CPU:</span> <span className="text-cyan">Intel i5-13420H</span></div>
                  <div><span className="text-gray-500">RAM:</span> <span className="text-cyan">15.7 GB</span></div>
                  <div><span className="text-gray-500">Response:</span> <span className="text-green-400">~1s warm</span></div>
                  <div><span className="text-gray-500">Status:</span> <span className="text-green-400">READY</span></div>
                </div>
              </div>

              <div className="mt-6 pt-4 border-t border-cyan/20">
                <div className="flex items-center gap-2">
                  <span className="text-gray-600">$</span>
                  <input
                    type="text"
                    placeholder="Type a command or 'talk' to speak..."
                    className="flex-1 bg-transparent border-none outline-none text-cyan placeholder-gray-600"
                  />
                  <motion.span
                    animate={{ opacity: [0, 1, 0] }}
                    transition={{ duration: 1, repeat: Infinity }}
                    className="text-cyan"
                  >
                    |
                  </motion.span>
                </div>
              </div>
            </motion.div>

            {/* Neural Core */}
            <motion.div
              initial={{ opacity: 0, x: 50 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex flex-col items-center"
            >
              <NeuralCore />
              
              <div className="mt-12 flex flex-wrap gap-3 justify-center">
                <button className="px-6 py-2 bg-green-400/10 border border-green-400 text-green-400 rounded hover:bg-green-400 hover:text-neural transition">
                  TALK
                </button>
                <button className="px-6 py-2 bg-red-500/10 border border-red-500 text-red-500 rounded hover:bg-red-500 hover:text-white transition">
                  STOP
                </button>
                <button className="px-6 py-2 bg-cyan/10 border border-cyan text-cyan rounded hover:bg-cyan hover:text-neural transition">
                  HEALTH
                </button>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 border-t border-cyan/20" id="about">
        <div className="container mx-auto px-6 text-center">
          <h2 className="text-3xl font-bold text-cyan mb-4">Ready to Install?</h2>
          <p className="text-gray-400 mb-8 max-w-2xl mx-auto">
            One command. Fully offline. Zero cloud. Your personal AI assistant running entirely on your machine.
          </p>
          <div className="flex gap-4 justify-center flex-wrap">
            <Link href="/cli" className="px-8 py-3 bg-cyan text-neural font-bold rounded hover:bg-cyan/90 transition">
              Install Now
            </Link>
            <Link href="https://github.com/Xenoz-GitHub/Xairex-AI" target="_blank" className="px-8 py-3 border border-cyan text-cyan rounded hover:bg-cyan hover:text-neural transition">
              View Source
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 border-t border-cyan/20">
        <div className="container mx-auto px-6 text-center text-gray-500 text-sm">
          <p>Created by XenozExe</p>
          <p className="mt-2">Fully offline. CPU-only. Zero cloud.</p>
        </div>
      </footer>
    </main>
  );
}
