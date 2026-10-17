'use client';

import { motion } from 'framer-motion';
import Link from 'next/link';

const features = [
  {
    id: 'voice',
    title: 'Voice Control',
    subtitle: 'Wake word activation',
    description: 'Say "Hey Xairex" to activate. Custom-trained wake word model for accurate detection.',
    tech: 'OpenWakeWord • Whisper STT',
    metrics: ['95% accuracy', '< 300ms latency', 'Background listening'],
    color: 'cyan'
  },
  {
    id: 'brain',
    title: 'Neural Brain',
    subtitle: 'Local LLM reasoning',
    description: 'Qwen3 4B running entirely on your CPU. No cloud. No tracking. No data leaving your machine.',
    tech: 'Ollama • Qwen3',
    metrics: ['~1s response', '4B parameters', '100% offline'],
    color: 'electric'
  },
  {
    id: 'tts',
    title: 'Voice Synthesis',
    subtitle: 'Natural female voice',
    description: 'High-quality text-to-speech with adjustable speed and volume. Female voice trained for clarity.',
    tech: 'Piper TTS',
    metrics: ['22kHz output', 'Adjustable pitch', 'Low latency'],
    color: 'purple'
  },
  {
    id: 'tools',
    title: 'OS Integration',
    subtitle: '23 system tools',
    description: 'Full control over your system: open apps, control volume, type text, manage files, browser automation.',
    tech: 'Windows API • pycaw • UIA',
    metrics: ['23 tools', 'Safe registry', 'Audit logging'],
    color: 'green'
  },
  {
    id: 'memory',
    title: 'Persistent Memory',
    subtitle: 'SQLite knowledge base',
    description: 'Remembers facts, preferences, and context across sessions. Privacy-first local storage.',
    tech: 'SQLite • Vector search',
    metrics: ['Instant recall', 'Semantic search', 'Local only'],
    color: 'orange'
  },
  {
    id: 'gui',
    title: 'Desktop GUI',
    subtitle: 'Tkinter interface',
    description: 'Modern chat transcript with animated status orb, live metrics, and full settings window.',
    tech: 'Tkinter • Canvas API',
    metrics: ['Real-time updates', 'Scrollable UI', 'Theme system'],
    color: 'pink'
  }
];

const tools = [
  { name: 'open_app', desc: 'Launch any application', time: '43ms' },
  { name: 'open_website', desc: 'Open URLs in browser', time: '85ms' },
  { name: 'set_volume', desc: 'Control system volume', time: '120ms' },
  { name: 'media_control', desc: 'Play/pause/next/prev', time: '67ms' },
  { name: 'wifi_control', desc: 'Manage network', time: '200ms' },
  { name: 'system_info', desc: 'Get CPU/RAM/disk', time: '55ms' },
  { name: 'find_files', desc: 'Search filesystem', time: '150ms' },
  { name: 'type_text', desc: 'Keyboard automation', time: '12ms/key' },
  { name: 'press_keys', desc: 'Hotkeys & combos', time: '45ms' },
  { name: 'search_web', desc: 'YouTube/Google/Wiki', time: '30ms' },
  { name: 'write_file', desc: 'Create files', time: '22ms' },
  { name: 'edit_file', desc: 'Modify content', time: '35ms' },
  { name: 'move_file', desc: 'Relocate files', time: '40ms' },
  { name: 'copy_file', desc: 'Duplicate files', time: '50ms' },
  { name: 'make_directory', desc: 'Create folders', time: '18ms' },
  { name: 'organize_folder', desc: 'Smart categorization', time: '~2s' },
  { name: 'turbo_write_code', desc: 'Turbo C++ automation', time: '~14s' },
  { name: 'vscode_control', desc: 'VS Code integration', time: '~3s' },
  { name: 'browser_activity', desc: 'Read browser state', time: '5ms' },
  { name: 'browser_command', desc: 'Control active tab', time: '80ms' },
  { name: 'admin_command', desc: 'UAC-elevated tasks', time: '~4s' },
  { name: 'shell_command', desc: 'Any CLI tool', time: 'varies' },
  { name: 'find_app', desc: 'Discover apps', time: '850ms' }
];

export default function FeaturesPage() {
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
            <Link href="/cli" className="hover:text-cyan transition">CLI</Link>
            <Link href="https://github.com/Xenoz-GitHub/Xairex-AI" target="_blank" className="text-cyan">GitHub</Link>
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
            ADVANCED FEATURES
          </motion.h1>
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
            className="text-gray-400 max-w-2xl mx-auto"
          >
            Enterprise-grade AI capabilities running entirely on your local machine.
            Zero cloud dependencies. Maximum privacy.
          </motion.p>
        </div>
      </section>

      {/* Feature Grid */}
      <section className="py-20">
        <div className="container mx-auto px-6">
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {features.map((feature, i) => (
              <motion.div
                key={feature.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.1 }}
                className="bg-terminal border border-cyan/20 rounded-lg p-6 hover:border-cyan/50 transition group"
              >
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3 className={`text-xl font-bold text-${feature.color}-400 group-hover:text-${feature.color}-300 transition`}>
                      {feature.title}
                    </h3>
                    <p className="text-xs text-gray-500 mt-1">{feature.subtitle}</p>
                  </div>
                  <div className={`w-2 h-2 rounded-full bg-${feature.color}-400 animate-pulse`} />
                </div>

                <p className="text-gray-400 text-sm mb-4">{feature.description}</p>

                <div className="mb-4 p-3 bg-neural rounded border border-cyan/10">
                  <p className="text-xs text-gray-600 mb-1">TECHNOLOGY STACK</p>
                  <p className="text-xs text-cyan">{feature.tech}</p>
                </div>

                <div className="space-y-1">
                  {feature.metrics.map((metric, j) => (
                    <div key={j} className="flex items-center gap-2 text-xs">
                      <div className={`w-1 h-1 rounded-full bg-${feature.color}-400`} />
                      <span className="text-gray-500">{metric}</span>
                    </div>
                  ))}
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Tools Registry */}
      <section className="py-20 border-t border-cyan/20">
        <div className="container mx-auto px-6">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-cyan mb-4">TOOL REGISTRY</h2>
            <p className="text-gray-400">23 production-ready OS integration tools</p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {tools.map((tool, i) => (
              <motion.div
                key={tool.name}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.03 }}
                className="bg-terminal border border-cyan/10 rounded p-4 hover:border-cyan/30 transition flex items-start justify-between group"
              >
                <div>
                  <p className="text-sm text-cyan font-mono group-hover:text-electric transition">{tool.name}</p>
                  <p className="text-xs text-gray-500 mt-1">{tool.desc}</p>
                </div>
                <span className="text-xs text-green-400 font-mono">{tool.time}</span>
              </motion.div>
            ))}
          </div>

          <div className="mt-12 p-6 bg-terminal border border-cyan/20 rounded-lg">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
              <span className="text-sm text-green-400">AUDIT SYSTEM ACTIVE</span>
            </div>
            <p className="text-xs text-gray-500">
              Every tool execution is logged to SQLite with: timestamp, tool name, arguments,
              execution time, success status, and output preview. Full audit trail for debugging.
            </p>
          </div>
        </div>
      </section>

      {/* Specifications */}
      <section className="py-20 border-t border-cyan/20">
        <div className="container mx-auto px-6">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-cyan mb-4">TECHNICAL SPECIFICATIONS</h2>
            <p className="text-gray-400">Production-grade architecture</p>
          </div>

          <div className="grid md:grid-cols-2 gap-8">
            <div className="bg-terminal border border-cyan/20 rounded-lg p-6">
              <h3 className="text-lg font-bold text-electric mb-4">RUNTIME</h3>
              <div className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Python Version</span>
                  <span className="text-cyan">3.12.10</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Test Coverage</span>
                  <span className="text-green-400">658 tests passing</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Code Quality</span>
                  <span className="text-green-400">Ruff clean</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">CPU Usage</span>
                  <span className="text-cyan">~40% during inference</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">RAM Usage</span>
                  <span className="text-cyan">~3 GB peak</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Disk Space</span>
                  <span className="text-cyan">~8 GB (models + venv)</span>
                </div>
              </div>
            </div>

            <div className="bg-terminal border border-cyan/20 rounded-lg p-6">
              <h3 className="text-lg font-bold text-electric mb-4">PERFORMANCE</h3>
              <div className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Cold Start</span>
                  <span className="text-cyan">~3s</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Warm Response</span>
                  <span className="text-green-400">~1s (xairex-fast)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">STT Latency</span>
                  <span className="text-cyan">~2.15s (small.en)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">LLM Inference</span>
                  <span className="text-cyan">~607ms avg</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">TTS Generation</span>
                  <span className="text-cyan">~200ms</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Tool Execution</span>
                  <span className="text-green-400">43-200ms</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 border-t border-cyan/20">
        <div className="container mx-auto px-6 text-center">
          <h2 className="text-3xl font-bold text-cyan mb-4">Ready to Experience It?</h2>
          <p className="text-gray-400 mb-8 max-w-2xl mx-auto">
            Install Xairex now and get a fully offline AI assistant with enterprise features.
          </p>
          <Link href="/cli" className="px-8 py-3 bg-cyan text-neural font-bold rounded hover:bg-cyan/90 transition inline-block">
            Install Now
          </Link>
        </div>
      </section>
    </main>
  );
}
