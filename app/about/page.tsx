'use client';

import { motion } from 'framer-motion';
import Link from 'next/link';

export default function AboutPage() {
  return (
    <main className="min-h-screen pt-24 pb-20">
      {/* Header */}
      <header className="fixed top-0 left-0 right-0 z-50 bg-neural/80 backdrop-blur border-b border-cyan/20">
        <div className="container mx-auto px-6 py-4 flex justify-between items-center">
          <Link href="/" className="flex items-center gap-3">
            <img src="/iconxairex.png" alt="Xairex" className="w-8 h-8" />
            <span className="text-xl text-cyan">XAIREX</span>
          </Link>
          <nav className="flex gap-6 text-sm">
            <Link href="/" className="hover:text-cyan transition">Home</Link>
            <Link href="/features" className="hover:text-cyan transition">Features</Link>
            <Link href="/cli" className="hover:text-cyan transition">CLI</Link>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="py-20 border-b border-cyan/20">
        <div className="container mx-auto px-6 text-center">
          <motion.h1
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-5xl font-bold text-cyan mb-4"
          >
            ABOUT XAIREX
          </motion.h1>
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
            className="text-gray-400 max-w-2xl mx-auto"
          >
            The fully offline personal AI assistant that respects your privacy.
          </motion.p>
        </div>
      </section>

      {/* Mission */}
      <section className="py-20">
        <div className="container mx-auto px-6">
          <div className="max-w-4xl mx-auto">
            <div className="grid md:grid-cols-2 gap-12 mb-20">
              <motion.div
                initial={{ opacity: 0, x: -50 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.3 }}
              >
                <h2 className="text-3xl font-bold text-cyan mb-6">THE MISSION</h2>
                <p className="text-gray-400 mb-4">
                  Every conversation you have with cloud-based AI assistants is analyzed, stored, and monetized. 
                  Your voice commands travel across the internet. Your personal data becomes training material.
                </p>
                <p className="text-gray-400 mb-4">
                  <span className="text-cyan font-bold">Xairex changes that.</span>
                </p>
                <p className="text-gray-400">
                  Built from the ground up for complete offline operation, Xairex gives you enterprise-grade AI capabilities 
                  without sacrificing your privacy. No telemetry. No cloud dependencies. No data leaving your machine.
                </p>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, x: 50 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.4 }}
                className="bg-terminal border border-cyan/20 rounded-lg p-8"
              >
                <h3 className="text-xl font-bold text-electric mb-6">CORE PRINCIPLES</h3>
                <div className="space-y-4">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <div className="w-2 h-2 rounded-full bg-cyan" />
                      <span className="text-cyan font-bold">Privacy First</span>
                    </div>
                    <p className="text-xs text-gray-500 pl-4">Zero telemetry, no cloud, no tracking</p>
                  </div>

                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <div className="w-2 h-2 rounded-full bg-green-400" />
                      <span className="text-green-400 font-bold">Fully Offline</span>
                    </div>
                    <p className="text-xs text-gray-500 pl-4">All models run locally on CPU</p>
                  </div>

                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <div className="w-2 h-2 rounded-full bg-electric" />
                      <span className="text-electric font-bold">Open Source</span>
                    </div>
                    <p className="text-xs text-gray-500 pl-4">Full transparency, community-driven</p>
                  </div>

                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <div className="w-2 h-2 rounded-full bg-purple-400" />
                      <span className="text-purple-400 font-bold">Production Ready</span>
                    </div>
                    <p className="text-xs text-gray-500 pl-4">658 tests, typed, audited, documented</p>
                  </div>
                </div>
              </motion.div>
            </div>

            {/* Technology Stack */}
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 }}
              className="border-t border-cyan/20 pt-12"
            >
              <h2 className="text-3xl font-bold text-cyan mb-8 text-center">TECHNOLOGY STACK</h2>
              
              <div className="grid md:grid-cols-3 gap-6">
                <div className="bg-terminal border border-cyan/20 rounded-lg p-6">
                  <h4 className="text-sm font-bold text-cyan mb-3">SPEECH</h4>
                  <div className="space-y-2 text-xs text-gray-400">
                    <p>• <span className="text-electric">Whisper</span> — OpenAI's STT (small.en, CPU-optimized)</p>
                    <p>• <span className="text-electric">Piper</span> — High-quality neural TTS</p>
                    <p>• <span className="text-electric">OpenWakeWord</span> — Custom wake word detection</p>
                  </div>
                </div>

                <div className="bg-terminal border border-cyan/20 rounded-lg p-6">
                  <h4 className="text-sm font-bold text-cyan mb-3">INTELLIGENCE</h4>
                  <div className="space-y-2 text-xs text-gray-400">
                    <p>• <span className="text-green-400">Ollama</span> — Local LLM server</p>
                    <p>• <span className="text-green-400">Qwen3</span> — 1.7B/4B models</p>
                    <p>• <span className="text-green-400">SQLite</span> — Persistent memory</p>
                  </div>
                </div>

                <div className="bg-terminal border border-cyan/20 rounded-lg p-6">
                  <h4 className="text-sm font-bold text-cyan mb-3">INTEGRATION</h4>
                  <div className="space-y-2 text-xs text-gray-400">
                    <p>• <span className="text-purple-400">Python 3.12</span> — Core runtime</p>
                    <p>• <span className="text-purple-400">pycaw</span> — Audio control</p>
                    <p>• <span className="text-purple-400">UIA</span> — UI automation</p>
                  </div>
                </div>
              </div>
            </motion.div>

            {/* Stats */}
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6 }}
              className="border-t border-cyan/20 pt-12 mt-12"
            >
              <div className="grid grid-cols-2 md:grid-cols-4 gap-6 text-center">
                <div>
                  <div className="text-4xl font-bold text-cyan mb-2">658</div>
                  <div className="text-xs text-gray-500">Tests Passing</div>
                </div>
                <div>
                  <div className="text-4xl font-bold text-green-400 mb-2">23</div>
                  <div className="text-xs text-gray-500">System Tools</div>
                </div>
                <div>
                  <div className="text-4xl font-bold text-electric mb-2">~1s</div>
                  <div className="text-xs text-gray-500">Response Time</div>
                </div>
                <div>
                  <div className="text-4xl font-bold text-purple-400 mb-2">0%</div>
                  <div className="text-xs text-gray-500">Cloud Dependency</div>
                </div>
              </div>
            </motion.div>

            {/* Developer */}
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.7 }}
              className="border-t border-cyan/20 pt-12 mt-12"
            >
              <div className="text-center mb-8">
                <h2 className="text-3xl font-bold text-cyan mb-2">DEVELOPER</h2>
                <p className="text-gray-500 text-sm">Created by</p>
              </div>

              <div className="max-w-2xl mx-auto bg-terminal border border-cyan/20 rounded-lg p-8">
                <div className="flex flex-col md:flex-row items-center gap-6">
                  <img
                    src="https://scontent-sin2-2.xx.fbcdn.net/v/t39.30808-1/853372316_122212439540870269_2016621905916160583_n.webp"
                    alt="XenozExe"
                    className="w-32 h-32 rounded-full border-2 border-cyan"
                    onError={(e) => {
                      e.currentTarget.src = '/iconxairex.png';
                    }}
                  />
                  <div className="flex-1 text-center md:text-left">
                    <h3 className="text-2xl font-bold text-cyan mb-2">XenozExe</h3>
                    <p className="text-gray-400 text-sm mb-4">
                      Privacy advocate. Security researcher. Builder of offline AI systems.
                    </p>
                    <div className="flex flex-wrap gap-3 justify-center md:justify-start">
                      <a
                        href="https://github.com/Xenoz-GitHub"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="px-4 py-2 bg-cyan/10 border border-cyan text-cyan rounded text-sm hover:bg-cyan hover:text-neural transition"
                      >
                        GitHub
                      </a>
                      <a
                        href="https://github.com/Xenoz-GitHub/Xairex-AI"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="px-4 py-2 bg-electric/10 border border-electric text-electric rounded text-sm hover:bg-electric hover:text-neural transition"
                      >
                        View Project
                      </a>
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 border-t border-cyan/20">
        <div className="container mx-auto px-6 text-center">
          <h2 className="text-3xl font-bold text-cyan mb-4">Join the Movement</h2>
          <p className="text-gray-400 mb-8 max-w-2xl mx-auto">
            Take back control of your AI assistant. Install Xairex today.
          </p>
          <Link href="/cli" className="px-8 py-3 bg-cyan text-neural font-bold rounded hover:bg-cyan/90 transition inline-block">
            Install Now
          </Link>
        </div>
      </section>
    </main>
  );
}
