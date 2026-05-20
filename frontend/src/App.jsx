import { useState, useEffect, useRef } from 'react'
import { 
  ShoppingCart, 
  Send, 
  RefreshCw, 
  Sidebar, 
  Activity, 
  Copy, 
  ShieldCheck, 
  User, 
  Package, 
  Zap,
  ChevronRight,
  Sun,
  Moon,
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Bot,
  X
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

function cn(...inputs) {
  return twMerge(clsx(inputs))
}

function App() {
  const [threadId, setThreadId] = useState('')
  const [userInput, setUserInput] = useState('')
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(true)
  const [darkMode, setDarkMode] = useState(false)
  const [isListening, setIsListening] = useState(false)
  const [voiceEnabled, setVoiceEnabled] = useState(true)
  const [lastLatency, setLastLatency] = useState(0)
  const [jarvisMode, setJarvisMode] = useState(false)
  const [jarvisState, setJarvisState] = useState('idle')
  
  const messagesEndRef = useRef(null)
  const recognitionRef = useRef(null)
  const silenceTimerRef = useRef(null)
  const currentAudioRef = useRef(null)   // Tracks the currently playing Audio element
  const jarvisModeRef = useRef(false)
  const jarvisStateRef = useRef('idle')
  const sendMessageRef = useRef(null)
  const isLoadingRef = useRef(false)

  // Keep refs in sync with state (avoids stale closures in event handlers)
  useEffect(() => { jarvisModeRef.current = jarvisMode }, [jarvisMode])
  useEffect(() => { jarvisStateRef.current = jarvisState }, [jarvisState])
  useEffect(() => { isLoadingRef.current = isLoading }, [isLoading])
  
  // Keep sendMessageRef updated on every render
  useEffect(() => {
    sendMessageRef.current = sendMessage
  })

  // Utility to strip Markdown for natural speech
  const cleanTextForSpeech = (text) => {
    return text
      .replace(/\*\*/g, '')
      .replace(/\*/g, '')
      .replace(/#/g, '')
      .replace(/\[(.*?)\]\(.*?\)/g, '$1')
      .replace(/`/g, '')
  }

  // ═══ Fix phonetic mishearings of order IDs from voice recognition ═══
  // Speech API commonly mishears: "ORD" → "ODD", "OR D", "odd", "order", "or", "R.D.", etc.
  // This function corrects the full user text before sending to the backend.
  const normalizeOrderIdInText = (text) => {
    // Pattern: catch variations of 'ord' prefix followed by digits (with optional spaces/separators)
    // Handles: "odd 001", "or d 001", "order 001" (prefix), "ODD001", "O.R.D 001", "0rd001"
    return text.replace(
      /\b(?:ord|odd|or\s*d|o\.?r\.?d\.?|order\s+(?:id\s+)?|0rd)\s*[-\s]*(\d{1,10})\b/gi,
      (match, digits) => `ORD${digits.replace(/\s/g, '')}`
    )
  }

  // Derive current context from the latest agent message
  const lastAgentMessage = [...messages].reverse().find(m => m.role === 'agent' && m.metadata)
  const currentIntent = lastAgentMessage?.metadata?.intent || ''
  const currentOrderId = lastAgentMessage?.metadata?.order_id || ''

  const generateId = () => 'thread-' + Math.random().toString(36).substr(2, 9)
  const now = () => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

  // NOTE: Voice selection via Web Speech API removed.
  // We now use StreamElements cloud TTS (Brian — British male MP3)
  // which bypasses ALL browser TTS bugs and plays at full system volume.

  // ═══ Initialize Speech Recognition with Auto-Submit in Both Modes ═══
  useEffect(() => {
    // Prefer webkitSpeechRecognition as it's the stable Chromium/Edge implementation
    const SpeechRecognition = window.webkitSpeechRecognition || window.SpeechRecognition
    if (SpeechRecognition) {
      recognitionRef.current = new SpeechRecognition()
      recognitionRef.current.continuous = true
      recognitionRef.current.interimResults = true
      recognitionRef.current.lang = 'en-US'

      recognitionRef.current.onresult = (event) => {
        let finalTranscript = ''
        let interimTranscript = ''

        // Loop from 0 to accumulate the ENTIRE transcript from the start of the session
        for (let i = 0; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            finalTranscript += event.results[i][0].transcript
          } else {
            interimTranscript += event.results[i][0].transcript
          }
        }
        
        const fullTranscript = finalTranscript || interimTranscript
        if (fullTranscript) {
          setUserInput(fullTranscript)
          
          // Auto-send silence timer enabled in BOTH Normal and JARVIS modes
          if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current)
          silenceTimerRef.current = setTimeout(() => {
            const textToSend = fullTranscript.trim()
            if (textToSend) {
              if (sendMessageRef.current) {
                sendMessageRef.current(textToSend)
              }
              recognitionRef.current?.stop()
              setIsListening(false)
              if (jarvisModeRef.current) {
                setJarvisState('processing')
              }
            }
            silenceTimerRef.current = null
          }, 2000) // 2-second silence timer
        }
      }

      recognitionRef.current.onerror = (err) => {
        console.error('Speech recognition error:', err)
        if (err.error === 'no-speech') {
          // 'no-speech' is a standard timeout error when no voice is detected.
          // In JARVIS mode, we can ignore this because onend will handle the restart.
          return
        }
        setIsListening(false)
        if (jarvisModeRef.current && 
            jarvisStateRef.current !== 'speaking' && 
            jarvisStateRef.current !== 'processing') {
          setJarvisState('idle')
        }
      }
      
      recognitionRef.current.onend = () => {
        // In JARVIS mode, if the SpeechRecognition engine naturally stops/times out 
        // while we are supposed to be actively listening, restart it immediately.
        if (jarvisModeRef.current && jarvisStateRef.current === 'listening') {
          try {
            recognitionRef.current.start()
          } catch (e) {
            // Already running or failed to start
          }
        } else {
          setIsListening(false)
          // Only reset to idle if not speaking or processing
          if (jarvisModeRef.current && 
              jarvisStateRef.current !== 'speaking' && 
              jarvisStateRef.current !== 'processing') {
            setJarvisState('idle')
          }
        }
      }
    }
  }, [threadId])

  useEffect(() => {
    const newId = generateId()
    setThreadId(newId)
    setMessages([{
      role: 'agent',
      content: "Hi! I'm your e-commerce support agent. Ask me about order status, returns, refunds, or cancellations.",
      timestamp: now()
    }])
  }, [])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // ═══ Stop Microphone immediately and clear silence timers ═══
  const stopMic = () => {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current)
      silenceTimerRef.current = null
    }
    if (recognitionRef.current) {
      try { recognitionRef.current.abort() } catch (e) { /* ignore */ }
    }
    setIsListening(false)
  }

  // ═══ Text-to-Speech — OpenAI TTS via Web Audio API with GainNode Amplification ═══
  // Why Web Audio API instead of HTML5 Audio:
  //   1. HTML5 Audio.volume maxes at 1.0 — can't amplify beyond system volume
  //   2. Web Audio API GainNode can push audio to 2x-3x system volume
  //   3. Bypasses OS-level audio ducking that Chrome applies when mic is hot
  //   4. Gives us full control over the audio pipeline

  // Persistent AudioContext (reused across all speak calls)
  const audioCtxRef = useRef(null)
  const gainNodeRef = useRef(null)
  const currentSourceRef = useRef(null)

  const getAudioContext = () => {
    if (!audioCtxRef.current || audioCtxRef.current.state === 'closed') {
      audioCtxRef.current = new (window.AudioContext || window.webkitAudioContext)()
      gainNodeRef.current = audioCtxRef.current.createGain()
      gainNodeRef.current.gain.value = 3.0  // 3x amplification
      gainNodeRef.current.connect(audioCtxRef.current.destination)
    }
    return audioCtxRef.current
  }

  // Stop any currently playing audio immediately
  const stopAudio = () => {
    const cur = currentAudioRef.current
    if (cur) {
      if (cur._abort) cur._abort()  // Cancel in-flight TTS fetch
      currentAudioRef.current = null
    }
    if (currentSourceRef.current) {
      try { currentSourceRef.current.stop() } catch (e) { /* already stopped */ }
      currentSourceRef.current = null
    }
  }

  const speak = async (text) => {
    if (!voiceEnabled && !jarvisModeRef.current) return
    stopAudio()
    stopMic()  // Kill the mic FIRST to prevent OS audio ducking

    const cleanedText = cleanTextForSpeech(text).trim()
    if (!cleanedText) return

    const BASE_URL = 'https://ecommerce-support-agent-93337753347.us-central1.run.app'
    const isJarvis = jarvisModeRef.current
    if (isJarvis) setJarvisState('speaking')

    // Wait 300ms for the OS to fully release the mic device
    await new Promise(r => setTimeout(r, 300))

    const abortCtrl = new AbortController()

    try {
      // Store abort function so stopAudio() can cancel in-flight fetches
      currentAudioRef.current = { _abort: () => abortCtrl.abort() }

      const resp = await fetch(
        `${BASE_URL}/tts?text=${encodeURIComponent(cleanedText)}`,
        { signal: abortCtrl.signal }
      )
      if (!resp.ok) throw new Error(`TTS fetch failed: ${resp.status}`)
      const arrayBuffer = await resp.arrayBuffer()

      // Decode MP3 into raw audio samples via Web Audio API
      const ctx = getAudioContext()
      if (ctx.state === 'suspended') await ctx.resume()
      const audioBuffer = await ctx.decodeAudioData(arrayBuffer)

      // Create a source node → GainNode (3x amplification) → speakers
      const source = ctx.createBufferSource()
      source.buffer = audioBuffer
      source.connect(gainNodeRef.current)
      currentSourceRef.current = source
      currentAudioRef.current = null  // No longer in fetch phase

      await new Promise((resolve) => {
        source.onended = resolve
        source.start(0)
      })

      // Audio finished — restart JARVIS mic if still in JARVIS mode
      currentSourceRef.current = null
      if (isJarvis && jarvisModeRef.current) {
        setJarvisState('idle')
        setTimeout(() => { if (jarvisModeRef.current) startListening() }, 400)
      }
    } catch (e) {
      if (e.name === 'AbortError') return
      console.error('TTS playback error:', e)
      currentSourceRef.current = null
      if (isJarvis && jarvisModeRef.current) {
        setJarvisState('idle')
        setTimeout(() => { if (jarvisModeRef.current) startListening() }, 400)
      }
    }
  }

  // ═══ Mic controls ═══
  const startListening = () => {
    if (isLoadingRef.current) return
    setUserInput('')
    try {
      recognitionRef.current?.start()
      setIsListening(true)
      if (jarvisModeRef.current) setJarvisState('listening')
    } catch (e) {
      // Already started — ignore
    }
  }

  const stopListening = () => {
    stopMic()
    if (jarvisModeRef.current) setJarvisState('idle')
    stopAudio()
  }

  const toggleListening = () => {
    if (isListening) {
      stopListening()
    } else {
      startListening()
    }
  }

  // ═══ JARVIS mode toggle ═══
  const toggleJarvisMode = () => {
    if (jarvisMode) {
      // Exit JARVIS mode
      stopListening()
      stopAudio()
      setJarvisState('idle')
      setJarvisMode(false)
    } else {
      // Enter JARVIS mode
      setJarvisMode(true)
      setDrawerOpen(false)
      setJarvisState('idle')
      // Auto-start listening after a short delay
      setTimeout(() => startListening(), 800)
    }
  }

  const newSession = () => {
    const newId = generateId()
    setThreadId(newId)
    setMessages([{
      role: 'agent',
      content: jarvisMode 
        ? "JARVIS online. How may I assist you?"
        : "Hi! I'm your e-commerce support agent. Ask me about order status, returns, refunds, or cancellations.",
      timestamp: now()
    }])
    stopListening()
    stopAudio()
    setJarvisState('idle')
  }

  // ═══ Send message (shared by both modes) ═══
  const sendMessage = async (overrideText = null) => {
    const textVal = (typeof overrideText === 'string' ? overrideText : userInput) || ''
    // Apply phonetic order-ID correction before sending to backend
    const text = normalizeOrderIdInText(textVal.trim())
    if (!text || isLoading) return

    stopMic()
    setUserInput('')
    setIsLoading(true)
    if (jarvisModeRef.current) setJarvisState('processing')
    const startTime = Date.now()
    
    const userMsg = {
      role: 'user',
      content: text,
      timestamp: now()
    }
    
    setMessages(prev => [...prev, userMsg])

    const aiMsgPlaceholder = {
      role: 'agent',
      content: '',
      timestamp: now(),
      streaming: true,
      metadata: null,
      isEscalated: false
    }
    
    setMessages(prev => [...prev, aiMsgPlaceholder])

    let fullText = ''
    let metadata = {}

    try {
      const BASE_URL = 'https://ecommerce-support-agent-93337753347.us-central1.run.app'
      const response = await fetch(`${BASE_URL}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, thread_id: threadId })
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        fullText = errorData.detail || `Request failed (${response.status}).`
      } else {
        const reader = response.body.getReader()
        const decoder = new TextDecoder()

        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          const lines = decoder.decode(value).split('\n\n')
          for (const line of lines) {
            const trimmed = line.trim()
            if (trimmed.startsWith('data: ')) {
              try {
                const data = JSON.parse(trimmed.slice(6))
                if (data.token) {
                  fullText += data.token
                  setMessages(prev => {
                    const updated = [...prev]
                    const last = updated[updated.length - 1]
                    if (last.role === 'agent') {
                      last.content = fullText
                    }
                    return updated
                  })
                }
                if (data.done) {
                  metadata = data
                }
              } catch (e) {}
            }
          }
        }
      }
    } catch (e) {
      fullText = 'Connection error. Please try again.'
    }

    if (!fullText.trim()) fullText = 'Sorry, I could not process your request.'
    
    const endTime = Date.now()
    setLastLatency(endTime - startTime)

    setMessages(prev => {
      const updated = [...prev]
      const last = updated[updated.length - 1]
      if (last.role === 'agent') {
        last.streaming = false
        last.content = fullText
        last.metadata = metadata
        last.isEscalated = metadata.escalated === true
      }
      return updated
    })
    
    speak(fullText)
    setIsLoading(false)
  }

  // ═══ JARVIS status label ═══
  const jarvisStatusText = {
    idle: 'Standing by',
    listening: 'Listening...',
    processing: 'Processing...',
    speaking: 'Speaking...'
  }[jarvisState]

  // ═══ Shared message renderer ═══
  const renderMessages = (isJarvis = false) => (
    <AnimatePresence initial={false}>
      {messages.map((msg, index) => (
        <motion.div 
          key={index}
          initial={{ opacity: 0, y: 10, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.2 }}
          className={cn(
            "flex flex-col",
            msg.role === 'user' ? "items-end" : "items-start"
          )}
        >
          <div className={cn(
            "max-w-[92%] sm:max-w-[85%] md:max-w-[70%] p-3 sm:p-4 rounded-3xl text-sm leading-relaxed transition-all shadow-sm",
            msg.role === 'user' 
              ? (isJarvis 
                  ? "bg-rose-600 text-white rounded-tr-none shadow-rose-600/20" 
                  : "bg-violet-600 text-white rounded-tr-none shadow-violet-600/10")
              : (isJarvis 
                  ? "bg-white/[0.03] border border-red-500/15 text-slate-200 rounded-tl-none" 
                  : (darkMode 
                      ? "bg-white/5 border border-white/10 text-slate-200 rounded-tl-none" 
                      : "bg-slate-100 border border-slate-200 text-slate-800 rounded-tl-none")),
            msg.isEscalated && "border-l-4 border-l-rose-500 bg-rose-500/5"
          )}>
            <ReactMarkdown 
              className={cn(
                "prose prose-sm max-w-none",
                (isJarvis || darkMode) ? "prose-invert" : "prose-slate"
              )}
              components={{
                strong: ({node, ...props}) => (
                  <strong 
                    className={cn("font-bold", 
                      isJarvis ? "text-rose-300" : (darkMode ? "text-violet-300" : "text-violet-600")
                    )} 
                    {...props} 
                  />
                ),
                p: ({node, ...props}) => <p className="mb-0 last:mb-0" {...props} />
              }}
            >
              {msg.content}
            </ReactMarkdown>
            {msg.streaming && <span className="cursor-blink" />}
            
            {/* Badges */}
            {msg.metadata && (
              <div className="flex flex-wrap gap-2 mt-4">
                {msg.metadata.intent && msg.metadata.intent !== 'unclear' && (
                  <span className={cn(
                    "px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-widest border",
                    isJarvis 
                      ? "bg-red-500/10 text-red-300 border-red-500/20" 
                      : (darkMode ? "bg-white/10 text-violet-300 border-white/10" : "bg-violet-50 text-violet-600 border-violet-100")
                  )}>
                    {msg.metadata.intent.replace('_', ' ')}
                  </span>
                )}
                {msg.metadata.order_id && (
                  <span className={cn(
                    "px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-widest border",
                    darkMode || isJarvis 
                      ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" 
                      : "bg-emerald-50 text-emerald-600 border-emerald-100"
                  )}>
                    📦 {msg.metadata.order_id}
                  </span>
                )}
                {msg.metadata.cache_hit && (
                  <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-widest border bg-amber-500/10 text-amber-400 border-amber-500/20">
                    ⚡ Cached
                  </span>
                )}
              </div>
            )}
          </div>
          
          <span className="text-[10px] text-slate-500 mt-1.5 px-2 font-medium">
            {msg.timestamp}
          </span>
        </motion.div>
      ))}
    </AnimatePresence>
  )

  // ═══════════════════════════════════════════════════════════════
  //  RENDER
  // ═══════════════════════════════════════════════════════════════
  return (
    <div className={cn(
      "min-h-screen min-h-[100dvh] flex items-center justify-center p-2 sm:p-4 md:p-8 overflow-hidden font-inter w-full transition-colors duration-500",
      jarvisMode 
        ? "bg-[#060608] text-slate-200" 
        : (darkMode ? "bg-slate-950 text-slate-200" : "bg-slate-50 text-slate-900")
    )}>

      {jarvisMode ? (
        /* ═══════════════════ JARVIS MODE ═══════════════════ */
        <div className="relative w-full max-w-6xl h-[100dvh] sm:h-[95dvh] md:h-[90vh] flex flex-col md:flex-row gap-4 md:gap-8">
          
          {/* Left Panel: Avatar & Controls */}
          <div className="flex-1 flex flex-col border-b md:border-b-0 md:border-r border-red-500/10 relative pb-6 md:pb-0">
            {/* JARVIS Header */}
            <header className="p-3 sm:p-4 flex justify-between items-center flex-shrink-0">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-red-600 to-rose-700 flex items-center justify-center shadow-lg shadow-red-500/30">
                  <Bot className="text-white w-5 h-5" />
                </div>
                <div>
                  <h1 className="text-base sm:text-lg font-bold tracking-tight text-white">J.A.R.V.I.S</h1>
                  <div className="flex items-center gap-2">
                    <span className={cn(
                      "w-2 h-2 rounded-full animate-pulse",
                      jarvisState === 'idle' ? "bg-red-500" : 
                      jarvisState === 'listening' ? "bg-red-400" :
                      jarvisState === 'processing' ? "bg-amber-500" :
                      "bg-red-300"
                    )} />
                    <span className="text-[10px] text-red-400/80 font-bold uppercase tracking-widest">
                      {jarvisStatusText}
                    </span>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button 
                  onClick={newSession}
                  className="p-2 rounded-lg hover:bg-white/5 text-slate-500 hover:text-red-400 transition-all" 
                  title="New Session"
                >
                  <RefreshCw className="w-5 h-5" />
                </button>
                <button 
                  onClick={toggleJarvisMode}
                  className="flex items-center gap-2 px-3 py-2 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 transition-all text-sm font-semibold"
                >
                  <X className="w-4 h-4" />
                  <span className="hidden sm:inline">Exit</span>
                </button>
              </div>
            </header>

            {/* JARVIS Avatar Section */}
            <div className="flex-1 flex flex-col items-center justify-center py-6 sm:py-10 flex-shrink-0 relative">
              <div className={cn("jarvis-avatar", `jarvis-${jarvisState}`)}>
                <div className="jarvis-glow" />
                <div className="jarvis-ring jarvis-ring-3" />
                <div className="jarvis-ring jarvis-ring-2" />
                <div className="jarvis-ring jarvis-ring-1" />
                <div className="jarvis-core" />
              </div>
              <motion.p 
                key={jarvisState}
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-5 text-xs sm:text-sm font-bold tracking-[0.2em] uppercase text-red-400/70"
              >
                {jarvisStatusText}
              </motion.p>
            </div>
          </div>

          {/* Right Panel: Messages Area */}
          <main className="flex-1 overflow-y-auto px-3 sm:px-4 md:px-8 py-4 sm:py-8 space-y-4 min-h-0 md:max-w-xl w-full mx-auto flex flex-col">
            {renderMessages(true)}
            <div ref={messagesEndRef} />
          </main>
        </div>

      ) : (
        /* ═══════════════════ NORMAL MODE ═══════════════════ */
        <div className="relative w-full max-w-6xl h-[100dvh] sm:h-[95dvh] md:h-[85vh] flex flex-col md:flex-row gap-2 md:gap-6">
          
          {/* Chat Section */}
          <div className={cn(
            "flex-1 rounded-3xl overflow-hidden flex flex-col relative shadow-2xl border transition-all duration-500",
            darkMode 
              ? "bg-slate-900/60 backdrop-blur-xl border-white/10 shadow-indigo-500/10" 
              : "bg-white/80 backdrop-blur-xl border-slate-200 shadow-slate-200/50"
          )}>
            
            {/* Header */}
            <header className={cn(
              "p-3 sm:p-4 md:p-6 border-b flex justify-between items-center transition-colors duration-500",
              darkMode ? "border-white/5 bg-white/5" : "border-slate-100 bg-slate-50/50"
            )}>
              <div className="flex items-center gap-2 sm:gap-4">
                <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-xl bg-gradient-to-br from-violet-600 to-indigo-700 flex items-center justify-center shadow-lg shadow-violet-500/20">
                  <ShoppingCart className="text-white w-4 h-4 sm:w-6 sm:h-6" />
                </div>
                <div>
                  <h1 className="text-sm sm:text-lg font-bold tracking-tight">E-commerce Support Agent</h1>
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                    <span className={cn(
                      "text-xs font-medium uppercase tracking-wider",
                      darkMode ? "text-slate-400" : "text-slate-500"
                    )}>Agent Online</span>
                  </div>
                </div>
              </div>
              
              <div className="flex items-center gap-1 sm:gap-2">
                <button 
                  onClick={() => setVoiceEnabled(!voiceEnabled)}
                  className={cn(
                    "p-2 rounded-lg transition-all group",
                    darkMode ? "hover:bg-white/10 text-slate-400" : "hover:bg-slate-100 text-slate-500",
                    voiceEnabled && "text-violet-500"
                  )}
                  title={voiceEnabled ? "Disable Voice Responses" : "Enable Voice Responses"}
                >
                  {voiceEnabled ? <Volume2 className="w-5 h-5" /> : <VolumeX className="w-5 h-5" />}
                </button>
                <button 
                  onClick={() => setDarkMode(!darkMode)}
                  className={cn(
                    "p-2 rounded-lg transition-all group",
                    darkMode ? "hover:bg-white/10 text-slate-400" : "hover:bg-slate-100 text-slate-500"
                  )}
                  title={darkMode ? "Switch to Light Mode" : "Switch to Dark Mode"}
                >
                  {darkMode ? <Sun className="w-5 h-5 group-hover:text-amber-400" /> : <Moon className="w-5 h-5 group-hover:text-indigo-600" />}
                </button>
                {/* ★ JARVIS Mode Button */}
                <button 
                  onClick={toggleJarvisMode}
                  className={cn(
                    "p-2 rounded-lg transition-all group relative",
                    darkMode ? "hover:bg-white/10 text-slate-400" : "hover:bg-slate-100 text-slate-500"
                  )}
                  title="Activate JARVIS Mode"
                >
                  <Bot className="w-5 h-5 group-hover:text-red-500 transition-colors" />
                </button>
                <button 
                  onClick={newSession}
                  className={cn(
                    "p-2 rounded-lg transition-all group",
                    darkMode ? "hover:bg-white/10 text-slate-400" : "hover:bg-slate-100 text-slate-500"
                  )} 
                  title="New Session"
                >
                  <RefreshCw className="w-5 h-5 group-hover:text-indigo-400 transition-all" />
                </button>
                <button 
                  onClick={() => setDrawerOpen(!drawerOpen)}
                  className={cn(
                    "flex items-center gap-2 px-4 py-2 rounded-xl border transition-all",
                    darkMode 
                      ? (drawerOpen ? "bg-indigo-500/20 border-indigo-500/30 text-indigo-300" : "bg-white/5 border-white/10 text-slate-400 hover:bg-white/10")
                      : (drawerOpen ? "bg-indigo-50 border-indigo-200 text-indigo-600" : "bg-slate-100 border-slate-200 text-slate-600 hover:bg-slate-200")
                  )}
                >
                  <Sidebar className="w-4 h-4" />
                  <span className="text-sm font-semibold">Details</span>
                </button>
              </div>
            </header>

            {/* Messages Area */}
            <main className="flex-1 overflow-y-auto p-3 sm:p-4 md:p-6 space-y-4 sm:space-y-6">
              {renderMessages(false)}
              <div ref={messagesEndRef} />
            </main>

            {/* Input Area */}
            <footer className={cn(
              "p-3 sm:p-4 md:p-6 transition-colors duration-500",
              darkMode ? "bg-slate-900/30 backdrop-blur-md border-t border-white/5" : "bg-slate-50/80 backdrop-blur-md border-t border-slate-200"
            )}>
              <div className="relative group flex gap-2 sm:gap-3">
                <div className="relative flex-1">
                  <input 
                    type="text" 
                    value={userInput}
                    onChange={(e) => setUserInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
                    disabled={isLoading}
                    placeholder="Ask about returns, orders, or support..." 
                    className={cn(
                      "w-full rounded-2xl px-4 sm:px-6 py-3 sm:py-4 pr-12 sm:pr-16 focus:outline-none focus:ring-2 transition-all text-sm disabled:opacity-50",
                      darkMode 
                        ? "bg-white/5 border border-white/10 text-slate-200 focus:ring-violet-500/50 focus:border-violet-500/50 placeholder:text-slate-600" 
                        : "bg-white border border-slate-200 text-slate-900 focus:ring-violet-500/30 focus:border-violet-500/30 placeholder:text-slate-400 shadow-sm"
                    )}
                  />
                  <button 
                    onClick={toggleListening}
                    className={cn(
                      "absolute right-4 top-1/2 -translate-y-1/2 p-2 rounded-xl transition-all",
                      isListening ? "bg-rose-500 text-white animate-pulse" : "text-slate-400 hover:text-violet-500"
                    )}
                  >
                    {isListening ? <Mic className="w-5 h-5" /> : <MicOff className="w-5 h-5" />}
                  </button>
                </div>
                <button 
                  onClick={() => sendMessage()}
                  disabled={isLoading || !userInput.trim()}
                  className="bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 disabled:from-slate-300 disabled:to-slate-300 dark:disabled:from-slate-800 dark:disabled:to-slate-800 text-white px-4 sm:px-8 py-2 rounded-2xl text-sm font-bold transition-all flex items-center gap-1 sm:gap-2 shadow-lg shadow-violet-600/20 whitespace-nowrap"
                >
                  <span className="hidden sm:inline">{isLoading ? '...' : 'Send'}</span>
                  <Send className="w-4 h-4" />
                </button>
              </div>
            </footer>
          </div>

          {/* Details Sidebar (Drawer) */}
          <AnimatePresence>
            {drawerOpen && (
              <motion.aside 
                initial={{ opacity: 0, x: 50 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 50 }}
                className={cn(
                  "w-72 md:w-85 rounded-3xl overflow-hidden hidden lg:flex flex-col shadow-2xl border transition-all duration-500",
                  darkMode 
                    ? "bg-slate-900/60 backdrop-blur-xl border-white/10" 
                    : "bg-white/80 backdrop-blur-xl border-slate-200 shadow-slate-200/50"
                )}
              >
                <header className={cn(
                  "p-6 border-b transition-colors duration-500",
                  darkMode ? "border-white/5 bg-white/5" : "border-slate-100 bg-slate-50/50"
                )}>
                  <h2 className="font-bold flex items-center gap-2">
                    <Activity className="w-4 h-4 text-fuchsia-400" />
                    Session Context
                  </h2>
                </header>
                <div className="p-6 space-y-8 overflow-y-auto">
                  {/* Session ID */}
                  <section>
                    <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-3 block">Current Thread</label>
                    <div className={cn(
                      "flex items-center justify-between p-3 rounded-xl border group cursor-pointer transition-all",
                      darkMode ? "bg-white/5 border-white/10 hover:border-indigo-500/30" : "bg-slate-50 border-slate-200 hover:border-indigo-500/30"
                    )}>
                      <code className={cn("text-xs truncate mr-2", darkMode ? "text-indigo-300" : "text-indigo-600")}>{threadId}</code>
                      <Copy className="w-3.5 h-3.5 text-slate-400 group-hover:text-indigo-500 transition-colors" />
                    </div>
                  </section>

                  {/* Live Intelligence */}
                  <section>
                    <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-3 block">Extracted Context</label>
                    <div className="space-y-3">
                      <div className={cn(
                        "p-3 rounded-xl border flex items-center justify-between",
                        darkMode ? "bg-indigo-500/5 border-indigo-500/10" : "bg-indigo-50 border-indigo-100"
                      )}>
                        <div className="flex items-center gap-2">
                          <Zap className="w-3.5 h-3.5 text-indigo-500" />
                          <span className="text-xs font-semibold">Last Intent</span>
                        </div>
                        <span className="text-[10px] font-bold text-indigo-500 uppercase tracking-widest">
                          {currentIntent.replace('_', ' ') || 'Searching...'}
                        </span>
                      </div>
                      <div className={cn(
                        "p-3 rounded-xl border flex items-center justify-between",
                        darkMode ? "bg-emerald-500/5 border-emerald-500/10" : "bg-emerald-50 border-emerald-100"
                      )}>
                        <div className="flex items-center gap-2">
                          <Package className="w-3.5 h-3.5 text-emerald-500" />
                          <span className="text-xs font-semibold">Active Order</span>
                        </div>
                        <span className="text-[10px] font-bold text-emerald-500 uppercase tracking-widest">
                          {currentOrderId && currentOrderId !== 'null' ? currentOrderId : 'None'}
                        </span>
                      </div>
                    </div>
                  </section>

                  {/* Status Card */}
                  <section className={cn(
                    "p-5 rounded-2xl border relative overflow-hidden group transition-all",
                    darkMode 
                      ? "bg-gradient-to-br from-indigo-600/20 to-fuchsia-600/20 border-white/10" 
                      : "bg-gradient-to-br from-indigo-50 to-fuchsia-50 border-indigo-100 shadow-sm"
                  )}>
                    <div className="absolute top-0 right-0 p-2 opacity-5 group-hover:opacity-10 transition-opacity">
                      <ShieldCheck className="w-20 h-20" />
                    </div>
                    <div className="flex items-center gap-3 mb-2 relative z-10">
                      <div className="w-8 h-8 rounded-lg bg-indigo-600/10 flex items-center justify-center">
                        <ShieldCheck className="w-5 h-5 text-indigo-600" />
                      </div>
                      <span className="text-sm font-bold">Secure Access</span>
                    </div>
                    <p className={cn("text-[10px] leading-relaxed relative z-10", darkMode ? "text-slate-400" : "text-slate-600")}>
                      Your session is being monitored by our PII scrubbers to ensure your personal data remains private.
                    </p>
                  </section>
                  
                  <footer className={cn(
                    "pt-6 mt-8 border-t flex flex-col gap-4",
                    darkMode ? "border-white/5" : "border-slate-100"
                  )}>
                    <div className="flex items-center justify-between text-[10px] font-semibold text-slate-500 uppercase tracking-widest">
                      <span>Latency</span>
                      <span className="text-emerald-500">{lastLatency ? `${lastLatency}ms` : '--'}</span>
                    </div>
                  </footer>
                </div>
              </motion.aside>
            )}
          </AnimatePresence>
        </div>
      )}
    </div>
  )
}

export default App
