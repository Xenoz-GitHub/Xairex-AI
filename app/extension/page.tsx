'use client';

import { motion } from 'framer-motion';
import Link from 'next/link';

export default function ExtensionPage() {
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
            BROWSER EXTENSION
          </motion.h1>
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
            className="text-gray-400 max-w-2xl mx-auto"
          >
            Chrome/Edge extension for seamless browser integration.
            Messages, activity tracking, and YouTube control.
          </motion.p>
        </div>
      </section>

      {/* Features */}
      <section className="py-20">
        <div className="container mx-auto px-6">
          <div className="max-w-4xl mx-auto">
            <div className="grid md:grid-cols-3 gap-6 mb-12">
              <div className="bg-terminal border border-cyan/20 rounded-lg p-6">
                <div className="w-12 h-12 bg-cyan/10 border border-cyan rounded flex items-center justify-center mb-4">
                  <span className="text-cyan text-2xl">📨</span>
                </div>
                <h3 className="text-lg font-bold text-cyan mb-2">Message Watch</h3>
                <p className="text-sm text-gray-400">
                  Real-time monitoring of Facebook, Twitter/X, Instagram, Discord, Telegram messages.
                  Xairex can read and announce new messages.
                </p>
              </div>

              <div className="bg-terminal border border-cyan/20 rounded-lg p-6">
                <div className="w-12 h-12 bg-electric/10 border border-electric rounded flex items-center justify-center mb-4">
                  <span className="text-electric text-2xl">📊</span>
                </div>
                <h3 className="text-lg font-bold text-electric mb-2">Activity Tracking</h3>
                <p className="text-sm text-gray-400">
                  Tracks page visits, titles, URLs, timestamps. Rolling 7-hour log.
                  Ask Xairex "What was I looking at?" for instant recall.
                </p>
              </div>

              <div className="bg-terminal border border-cyan/20 rounded-lg p-6">
                <div className="w-12 h-12 bg-purple-400/10 border border-purple-400 rounded flex items-center justify-center mb-4">
                  <span className="text-purple-400 text-2xl">▶️</span>
                </div>
                <h3 className="text-lg font-bold text-purple-400 mb-2">YouTube Control</h3>
                <p className="text-sm text-gray-400">
                  Voice commands: play, pause, skip, volume, seek, speed control.
                  "Skip 30 seconds" or "slow down to 0.75x" — all hands-free.
                </p>
              </div>
            </div>

            {/* Installation */}
            <div className="bg-terminal border border-cyan/20 rounded-lg p-8 mb-8">
              <h2 className="text-2xl font-bold text-cyan mb-6">INSTALLATION</h2>
              
              <div className="space-y-6">
                <div>
                  <div className="flex items-center gap-3 mb-2">
                    <div className="w-8 h-8 bg-cyan/10 border border-cyan rounded flex items-center justify-center text-cyan font-bold">1</div>
                    <h4 className="text-electric font-bold">Install Xairex</h4>
                  </div>
                  <p className="text-sm text-gray-400 ml-11">
                    Make sure you have Xairex installed. The extension requires the local bridge server.
                  </p>
                  <div className="ml-11 mt-2">
                    <Link href="/cli" className="text-xs text-cyan hover:underline">See installation guide →</Link>
                  </div>
                </div>

                <div>
                  <div className="flex items-center gap-3 mb-2">
                    <div className="w-8 h-8 bg-cyan/10 border border-cyan rounded flex items-center justify-center text-cyan font-bold">2</div>
                    <h4 className="text-electric font-bold">Load Extension</h4>
                  </div>
                  <p className="text-sm text-gray-400 ml-11 mb-2">
                    Open Chrome/Edge and navigate to the extensions page:
                  </p>
                  <div className="ml-11 bg-neural border border-cyan/10 rounded p-3 font-mono text-xs text-cyan">
                    chrome://extensions
                  </div>
                  <p className="text-sm text-gray-400 ml-11 mt-2">
                    Enable "Developer mode" (top right toggle)
                  </p>
                </div>

                <div>
                  <div className="flex items-center gap-3 mb-2">
                    <div className="w-8 h-8 bg-cyan/10 border border-cyan rounded flex items-center justify-center text-cyan font-bold">3</div>
                    <h4 className="text-electric font-bold">Load Unpacked</h4>
                  </div>
                  <p className="text-sm text-gray-400 ml-11 mb-2">
                    Click "Load unpacked" and select the extension folder:
                  </p>
                  <div className="ml-11 bg-neural border border-cyan/10 rounded p-3 font-mono text-xs text-cyan">
                    C:\Users\YourName\Documents\MIDNIGHT-PROJECT\extension\
                  </div>
                </div>

                <div>
                  <div className="flex items-center gap-3 mb-2">
                    <div className="w-8 h-8 bg-cyan/10 border border-cyan rounded flex items-center justify-center text-cyan font-bold">4</div>
                    <h4 className="text-electric font-bold">Start Xairex</h4>
                  </div>
                  <p className="text-sm text-gray-400 ml-11 mb-2">
                    Run Xairex with the GUI:
                  </p>
                  <div className="ml-11 bg-neural border border-cyan/10 rounded p-3 font-mono text-xs text-cyan">
                    py -3.12 app.py --gui
                  </div>
                  <p className="text-sm text-gray-400 ml-11 mt-2">
                    The extension will auto-connect to the bridge within seconds.
                  </p>
                </div>

                <div>
                  <div className="flex items-center gap-3 mb-2">
                    <div className="w-8 h-8 bg-green-400/10 border border-green-400 rounded flex items-center justify-center text-green-400 font-bold">✓</div>
                    <h4 className="text-green-400 font-bold">Done</h4>
                  </div>
                  <p className="text-sm text-gray-400 ml-11">
                    Check Xairex GUI footer — you should see "BRIDGE CONNECTED" with a green dot.
                  </p>
                </div>
              </div>
            </div>

            {/* Commands */}
            <div className="bg-terminal border border-cyan/20 rounded-lg p-8">
              <h2 className="text-2xl font-bold text-cyan mb-6">VOICE COMMANDS</h2>
              
              <div className="space-y-4">
                <div className="grid md:grid-cols-2 gap-4">
                  <div>
                    <h4 className="text-sm font-bold text-electric mb-2">PLAYBACK</h4>
                    <div className="space-y-1 text-xs text-gray-400">
                      <p>• "Play the video"</p>
                      <p>• "Pause"</p>
                      <p>• "Resume"</p>
                      <p>• "Restart the video"</p>
                    </div>
                  </div>

                  <div>
                    <h4 className="text-sm font-bold text-electric mb-2">SEEK</h4>
                    <div className="space-y-1 text-xs text-gray-400">
                      <p>• "Skip 30 seconds"</p>
                      <p>• "Go back 10 seconds"</p>
                      <p>• "Jump to 2 minutes"</p>
                      <p>• "Go to the start"</p>
                    </div>
                  </div>

                  <div>
                    <h4 className="text-sm font-bold text-electric mb-2">SPEED</h4>
                    <div className="space-y-1 text-xs text-gray-400">
                      <p>• "Speed up to 1.5x"</p>
                      <p>• "Slow down to 0.75x"</p>
                      <p>• "Normal speed"</p>
                      <p>• "Double speed"</p>
                    </div>
                  </div>

                  <div>
                    <h4 className="text-sm font-bold text-electric mb-2">MESSAGES</h4>
                    <div className="space-y-1 text-xs text-gray-400">
                      <p>• "What are my messages?"</p>
                      <p>• "Any new notifications?"</p>
                      <p>• "Read my messages"</p>
                      <p>• "What was I looking at earlier?"</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Privacy */}
      <section className="py-20 border-t border-cyan/20">
        <div className="container mx-auto px-6">
          <div className="max-w-4xl mx-auto">
            <h2 className="text-3xl font-bold text-cyan mb-6 text-center">PRIVACY GUARANTEE</h2>
            <div className="bg-terminal border border-cyan/20 rounded-lg p-8">
              <div className="space-y-4 text-sm text-gray-400">
                <p>
                  <span className="text-cyan font-bold">✓ Local Bridge Only:</span> The extension connects to <span className="text-electric font-mono">ws://127.0.0.1:8769</span> — a loopback address. No external servers.
                </p>
                <p>
                  <span className="text-cyan font-bold">✓ No Telemetry:</span> Zero analytics, no tracking pixels, no data collection.
                </p>
                <p>
                  <span className="text-cyan font-bold">✓ Rolling 7-Hour Log:</span> Activity data auto-deletes after 7 hours. Never persisted long-term.
                </p>
                <p>
                  <span className="text-cyan font-bold">✓ Opt-In Messages:</span> Message monitoring is OFF by default. Enable per-platform in extension options.
                </p>
                <p>
                  <span className="text-cyan font-bold">✓ Open Source:</span> Full source code in <span className="text-electric font-mono">extension/</span> directory. Audit it yourself.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 border-t border-cyan/20">
        <div className="container mx-auto px-6 text-center">
          <h2 className="text-3xl font-bold text-cyan mb-4">Ready to Install?</h2>
          <p className="text-gray-400 mb-8 max-w-2xl mx-auto">
            Get Xairex first, then load the extension.
          </p>
          <Link href="/cli" className="px-8 py-3 bg-cyan text-neural font-bold rounded hover:bg-cyan/90 transition inline-block">
            Install Xairex
          </Link>
        </div>
      </section>
    </main>
  );
}
