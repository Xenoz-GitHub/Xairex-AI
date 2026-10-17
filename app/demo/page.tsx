'use client';

import { motion } from 'framer-motion';
import Link from 'next/link';
import { useState } from 'react';
import { EnhancedNeuralCore } from '@/components/EnhancedNeuralCore';

type State = 'idle' | 'listening' | 'thinking' | 'speaking';

const demoScenarios = [
  {
    id: 'volume',
    title: 'Volume Control',
    userInput: '"Set volume to 100%"',
    steps: [
      { state: 'listening' as State, duration: 2000, text: 'Listening to your voice...' },
      { state: 'thinking' as State, duration: 1500, text: 'Processing command...' },
      { state: 'speaking' as State, duration: 2000, text: 'Volume is now at 100%.' }
    ],
    metrics: { stt: '210ms', llm: '120ms', tool: '85ms', tts: '180ms', total: '595ms' }
  },
  {
    id: 'app',
    title: 'Open Application',
    userInput: '"Open Notepad"',
    steps: [
      { state: 'listening' as State, duration: 1800, text: 'Listening...' },
      { state: 'thinking' as State, duration: 1200, text: 'Searching for Notepad...' },
      { state: 'speaking' as State, duration: 1800, text: 'Opening Notepad now.' }
    ],
    metrics: { stt: '185ms', llm: '95ms', tool: '43ms', tts: '160ms', total: '483ms' }
  },
  {
    id: 'code',
    title: 'Write Code',
    userInput: '"Create a Fibonacci program in Turbo C++"',
    steps: [
      { state: 'listening' as State, duration: 2500, text: 'Listening to your request...' },
      { state: 'thinking' as State, duration: 3000, text: 'Generating C++ code...' },
      { state: 'speaking' as State, duration: 3000, text: 'I created FIBO.CPP in Turbo C++, typed your program and saved it.' }
    ],
    metrics: { stt: '250ms', llm: '650ms', tool: '14600ms', tts: '220ms', total: '15720ms' }
  },
  {
    id: 'search',
    title: 'Web Search',
    userInput: '"Search YouTube for AI tutorials"',
    steps: [
      { state: 'listening' as State, duration: 2000, text: 'Listening...' },
      { state: 'thinking' as State, duration: 800, text: 'Opening browser...' },
      { state: 'speaking' as State, duration: 1500, text: 'I opened YouTube with your search.' }
    ],
    metrics: { stt: '195ms', llm: '50ms', tool: '85ms', tts: '145ms', total: '475ms' }
  },
  {
    id: 'memory',
    title: 'Remember Fact',
    userInput: '"Remember my favorite color is blue"',
    steps: [
      { state: 'listening' as State, duration: 2200, text: 'Listening...' },
      { state: 'thinking' as State, duration: 1500, text: 'Storing to memory...' },
      { state: 'speaking' as State, duration: 2000, text: 'I will remember that your favorite color is blue.' }
    ],
    metrics: { stt: '220ms', llm: '140ms', tool: '22ms', tts: '185ms', total: '567ms' }
  },
  {
    id: 'organize',
    title: 'Organize Files',
    userInput: '"Organize my Downloads folder"',
    steps: [
      { state: 'listening' as State, duration: 2000, text: 'Listening...' },
      { state: 'thinking' as State, duration: 4000, text: 'Analyzing 100 files, categorizing...' },
      { state: 'speaking' as State, duration: 3000, text: 'I found 100 files. I can sort them into 7 categories. Should I proceed?' }
    ],
    metrics: { stt: '200ms', llm: '180ms', tool: '2100ms', tts: '240ms', total: '2720ms' }
  }
];

export default function DemoPage() {
  const [activeScenario, setActiveScenario] = useState<typeof demoScenarios[0] | null>(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [transcript, setTranscript] = useState<string[]>([]);

  const playScenario = (scenario: typeof demoScenarios[0]) => {
    setActiveScenario(scenario);
    setCurrentStep(0);
    setIsPlaying(true);
    setTranscript([`User: ${scenario.userInput}`]);

    let stepIndex = 0;
    const runStep = () => {
      if (stepIndex < scenario.steps.length) {
        setCurrentStep(stepIndex);
        setTranscript(prev => [...prev, `[${scenario.steps[stepIndex].state.toUpperCase()}] ${scenario.steps[stepIndex].text}`]);
        
        setTimeout(() => {
          stepIndex++;
          runStep();
        }, scenario.steps[stepIndex].duration);
      } else {
        setIsPlaying(false);
        setTranscript(prev => [...prev, `✓ Complete — Total: ${scenario.metrics.total}`]);
      }
    };

    runStep();
  };

  const currentState: State = isPlaying && activeScenario
    ? activeScenario.steps[currentStep]?.state || 'idle'
    : 'idle';

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
            INTERACTIVE DEMO
          </motion.h1>
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
            className="text-gray-400 max-w-2xl mx-auto"
          >
            See Xairex in action. Click any scenario to watch the full execution pipeline.
          </motion.p>
        </div>
      </section>

      {/* Demo Area */}
      <section className="py-20">
        <div className="container mx-auto px-6">
          <div className="grid lg:grid-cols-2 gap-12">
            {/* Neural Core Visualizer */}
            <div className="flex flex-col items-center">
              <EnhancedNeuralCore state={currentState} />

              {activeScenario && (
                <div className="mt-8 w-full max-w-md">
                  <div className="bg-terminal border border-cyan/20 rounded-lg p-4">
                    <p className="text-xs text-gray-600 mb-2">CURRENT METRICS</p>
                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div>
                        <span className="text-gray-500">STT:</span>{' '}
                        <span className="text-cyan">{activeScenario.metrics.stt}</span>
                      </div>
                      <div>
                        <span className="text-gray-500">LLM:</span>{' '}
                        <span className="text-green-400">{activeScenario.metrics.llm}</span>
                      </div>
                      <div>
                        <span className="text-gray-500">Tool:</span>{' '}
                        <span className="text-electric">{activeScenario.metrics.tool}</span>
                      </div>
                      <div>
                        <span className="text-gray-500">TTS:</span>{' '}
                        <span className="text-purple-400">{activeScenario.metrics.tts}</span>
                      </div>
                      <div className="col-span-2 pt-2 border-t border-cyan/10">
                        <span className="text-gray-500">Total:</span>{' '}
                        <span className="text-cyan font-bold">{activeScenario.metrics.total}</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Scenarios & Transcript */}
            <div>
              <h3 className="text-xl font-bold text-cyan mb-6">DEMO SCENARIOS</h3>
              <div className="space-y-3 mb-8">
                {demoScenarios.map((scenario) => (
                  <button
                    key={scenario.id}
                    onClick={() => !isPlaying && playScenario(scenario)}
                    disabled={isPlaying}
                    className={`w-full text-left p-4 rounded-lg border transition ${
                      activeScenario?.id === scenario.id
                        ? 'bg-cyan/10 border-cyan text-cyan'
                        : 'bg-terminal border-cyan/20 hover:border-cyan/50'
                    } ${isPlaying ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                  >
                    <div className="flex justify-between items-start mb-1">
                      <span className="font-bold">{scenario.title}</span>
                      {activeScenario?.id === scenario.id && isPlaying && (
                        <span className="text-xs text-green-400 animate-pulse">● RUNNING</span>
                      )}
                    </div>
                    <p className="text-xs text-gray-500">{scenario.userInput}</p>
                  </button>
                ))}
              </div>

              {/* Transcript */}
              <div className="bg-terminal border border-cyan/20 rounded-lg p-6">
                <div className="flex items-center justify-between mb-4">
                  <h4 className="text-sm font-bold text-cyan">EXECUTION TRANSCRIPT</h4>
                  {transcript.length > 0 && (
                    <button
                      onClick={() => {
                        setTranscript([]);
                        setActiveScenario(null);
                        setIsPlaying(false);
                      }}
                      className="text-xs text-gray-500 hover:text-cyan transition"
                    >
                      Clear
                    </button>
                  )}
                </div>

                <div className="space-y-2 text-sm font-mono max-h-96 overflow-y-auto">
                  {transcript.length === 0 ? (
                    <p className="text-gray-600 text-xs">Select a scenario to begin...</p>
                  ) : (
                    transcript.map((line, i) => (
                      <motion.div
                        key={i}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        className={
                          line.startsWith('User:')
                            ? 'text-electric'
                            : line.startsWith('[LISTENING]')
                            ? 'text-green-400'
                            : line.startsWith('[THINKING]')
                            ? 'text-yellow-400'
                            : line.startsWith('[SPEAKING]')
                            ? 'text-purple-400'
                            : line.startsWith('✓')
                            ? 'text-green-400 font-bold'
                            : 'text-gray-400'
                        }
                      >
                        {line}
                      </motion.div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Performance Notes */}
      <section className="py-20 border-t border-cyan/20">
        <div className="container mx-auto px-6">
          <div className="max-w-4xl mx-auto">
            <h3 className="text-2xl font-bold text-cyan mb-6 text-center">PERFORMANCE NOTES</h3>
            <div className="grid md:grid-cols-2 gap-6">
              <div className="bg-terminal border border-cyan/20 rounded-lg p-6">
                <h4 className="text-sm font-bold text-electric mb-3">FAST PROFILE (xairex-fast)</h4>
                <ul className="space-y-2 text-sm text-gray-400">
                  <li>• Qwen3 1.7B model</li>
                  <li>• ~1s warm response time</li>
                  <li>• 40% CPU peak usage</li>
                  <li>• 2.8GB RAM</li>
                  <li>• Perfect for daily tasks</li>
                </ul>
              </div>

              <div className="bg-terminal border border-cyan/20 rounded-lg p-6">
                <h4 className="text-sm font-bold text-purple-400 mb-3">QUALITY PROFILE (xairex-brain)</h4>
                <ul className="space-y-2 text-sm text-gray-400">
                  <li>• Qwen3 4B model</li>
                  <li>• ~2-3s response time</li>
                  <li>• 60% CPU peak usage</li>
                  <li>• 4.2GB RAM</li>
                  <li>• Better reasoning</li>
                </ul>
              </div>
            </div>

            <div className="mt-6 p-6 bg-terminal border border-cyan/20 rounded-lg">
              <p className="text-xs text-gray-500">
                <span className="text-cyan font-bold">Note:</span> All measurements taken on Intel i5-13420H
                (4P+4E, 12 threads) with 15.7GB RAM. Your performance may vary based on CPU capabilities.
                All processing happens locally — no internet required after installation.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 border-t border-cyan/20">
        <div className="container mx-auto px-6 text-center">
          <h2 className="text-3xl font-bold text-cyan mb-4">Try It Yourself</h2>
          <p className="text-gray-400 mb-8 max-w-2xl mx-auto">
            Install Xairex and experience the full power of local AI.
          </p>
          <Link href="/cli" className="px-8 py-3 bg-cyan text-neural font-bold rounded hover:bg-cyan/90 transition inline-block">
            Install Now
          </Link>
        </div>
      </section>
    </main>
  );
}
