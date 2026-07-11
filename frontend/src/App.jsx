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
  X,
  Play
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'
import confetti from 'canvas-confetti'

function cn(...inputs) {
  return twMerge(clsx(inputs))
}

function ProductCardSkeleton() {
  return (
    <div className="flex flex-col justify-between p-4 rounded-2xl border border-slate-700/10 bg-slate-800/10 skeleton-pulse">
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="h-3 w-14 bg-slate-700/40 rounded-full" />
          <div className="h-3 w-4 bg-slate-700/20 rounded" />
        </div>
        <div className="h-3.5 w-5/6 bg-slate-700/30 rounded mb-2" />
        <div className="h-3.5 w-2/3 bg-slate-700/30 rounded mb-4" />
      </div>
      <div>
        <div className="h-px w-full bg-slate-700/10 mb-3" />
        <div className="h-2.5 w-8 bg-slate-700/20 rounded mb-1" />
        <div className="h-4 w-16 bg-slate-700/35 rounded mb-3" />
        <div className="h-8 w-full bg-slate-700/40 rounded-xl" />
      </div>
    </div>
  );
}

function ProductCardsGrid({ content, streaming, darkMode, jarvisMode, isLoading, onCheckout }) {
  const [products, setProducts] = useState([]);

  useEffect(() => {
    // If not streaming, parse immediately
    if (!streaming) {
      setProducts(extractProductCards(content) || []);
      return;
    }

    // While streaming, debounce parsing to 300ms to optimize rendering and prevent flicker
    const timer = setTimeout(() => {
      setProducts(extractProductCards(content) || []);
    }, 300);

    return () => clearTimeout(timer);
  }, [content, streaming]);

  // Render skeleton loaders when searching/loading and no products parsed yet
  const isSearching = streaming && 
    /(?:buy|purchase|order|shop|looking for|catalog|xbox|playstation|switch|oled|tv|phone|laptop|macbook)/i.test(content) &&
    (products.length === 0);

  if (isSearching) {
    return (
      <div className="mt-5 w-full border-t border-white/5 pt-4">
        <div className="flex items-center gap-2 mb-3">
          <span className="flex-shrink-0 h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-xs font-bold text-slate-400 uppercase tracking-widest skeleton-pulse">
            Searching Stores...
          </span>
        </div>
        <div className={`grid gap-4 ${jarvisMode ? 'grid-cols-1 xl:grid-cols-2' : 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3'}`}>
          <ProductCardSkeleton />
          <ProductCardSkeleton />
          <ProductCardSkeleton />
        </div>
      </div>
    );
  }

  if (products.length === 0) return null;

  // Define platform style maps with high contrast for both light and dark modes
  const isDark = darkMode || jarvisMode;
  const platformStyles = {
    Amazon: {
      bg: isDark 
        ? "bg-amber-500/5 hover:bg-amber-500/10 border-amber-500/25" 
        : "bg-amber-50/60 hover:bg-amber-100/60 border-amber-200/80",
      badge: isDark 
        ? "bg-amber-500/25 text-amber-200 border-amber-500/40 text-[10px]" 
        : "bg-amber-100 text-amber-950 border-amber-300 text-[10px]",
      accent: isDark ? "text-amber-400" : "text-amber-700",
      shadow: isDark ? "shadow-amber-500/5 hover:shadow-amber-500/10" : "shadow-sm hover:shadow-md",
      btn: isDark 
        ? "bg-amber-600 hover:bg-amber-500 text-white shadow-amber-600/20" 
        : "bg-amber-600 hover:bg-amber-700 text-white shadow-md shadow-amber-600/10"
    },
    Flipkart: {
      bg: isDark 
        ? "bg-blue-500/5 hover:bg-blue-500/10 border-blue-500/25" 
        : "bg-blue-50/60 hover:bg-blue-100/60 border-blue-200/80",
      badge: isDark 
        ? "bg-blue-500/25 text-blue-200 border-blue-500/40 text-[10px]" 
        : "bg-blue-100 text-blue-950 border-blue-300 text-[10px]",
      accent: isDark ? "text-blue-400" : "text-blue-700",
      shadow: isDark ? "shadow-blue-500/5 hover:shadow-blue-500/10" : "shadow-sm hover:shadow-md",
      btn: isDark 
        ? "bg-blue-600 hover:bg-blue-500 text-white shadow-blue-600/20" 
        : "bg-blue-600 hover:bg-blue-700 text-white shadow-md shadow-blue-600/10"
    },
    Croma: {
      bg: isDark 
        ? "bg-teal-500/5 hover:bg-teal-500/10 border-teal-500/25" 
        : "bg-teal-50/60 hover:bg-teal-100/60 border-teal-200/80",
      badge: isDark 
        ? "bg-teal-500/25 text-teal-200 border-teal-500/40 text-[10px]" 
        : "bg-teal-100 text-teal-950 border-teal-300 text-[10px]",
      accent: isDark ? "text-teal-400" : "text-teal-700",
      shadow: isDark ? "shadow-teal-500/5 hover:shadow-teal-500/10" : "shadow-sm hover:shadow-md",
      btn: isDark 
        ? "bg-teal-600 hover:bg-teal-500 text-white shadow-teal-600/20" 
        : "bg-teal-600 hover:bg-teal-700 text-white shadow-md shadow-teal-600/10"
    }
  };

  return (
    <div className="mt-5 w-full border-t border-white/5 pt-4">
      <div className="flex items-center gap-2 mb-3">
        <span className="flex-shrink-0 h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
        <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">
          Live Store Matches
        </span>
      </div>
      
      <div className={`grid gap-4 ${jarvisMode ? 'grid-cols-1 xl:grid-cols-2' : 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3'}`}>
        {products.map((prod, idx) => {
          const style = platformStyles[prod.platform] || platformStyles.Amazon;
          
          return (
            <div 
              key={idx}
              className={cn(
                "flex flex-col justify-between p-4 rounded-2xl border transition-all duration-300 group hover:-translate-y-1 hover:border-white/10",
                style.bg, style.shadow
              )}
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className={cn(
                    "px-2 py-0.5 rounded-full text-[9px] font-extrabold uppercase tracking-wider border flex items-center justify-center",
                    style.badge
                  )}>
                    {prod.platform}
                  </span>
                  <span className="text-[10px] text-slate-500 group-hover:text-slate-400 transition-colors">
                    #{idx + 1}
                  </span>
                </div>
                
                <h4 className={cn(
                  "text-xs font-semibold line-clamp-3 transition-colors mb-4 min-h-[44px] leading-snug",
                  isDark ? "text-slate-200 group-hover:text-white" : "text-slate-800 group-hover:text-slate-950"
                )}>
                  {prod.name}
                </h4>
              </div>
              
              <div>
                <div className="flex flex-col items-start gap-1 mb-3 border-t border-white/5 pt-3">
                  <span className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">
                    Price
                  </span>
                  <span className={cn("text-sm font-black tracking-tight", style.accent)}>
                    {prod.price}
                  </span>
                </div>
                
                <button
                  onClick={() => onCheckout(`I choose the ${prod.platform} option: "${prod.name}" at price "${prod.price}"`)}
                  disabled={isLoading}
                  aria-label={`Checkout ${prod.name} from ${prod.platform}`}
                  className={cn(
                    "w-full py-2 rounded-xl text-xs font-bold transition-all duration-200 shadow-md flex items-center justify-center gap-1.5 focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:ring-offset-1 focus:ring-offset-slate-900",
                    style.btn
                  )}
                >
                  <ShoppingCart className="w-3.5 h-3.5" />
                  Checkout
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function extractProductCards(text) {
  if (!text) return null;
  const platforms = ['Amazon', 'Flipkart', 'Croma'];
  const results = [];
  const lines = text.split('\n');
  let currentPlatform = null;
  let pendingProductName = null;
  
  for (let line of lines) {
    let trimmed = line.trim();
    if (!trimmed) continue;
    
    // Clean bold asterisks immediately to prevent parsed names from containing them
    trimmed = trimmed.replace(/\*\*/g, '');
    
    // 1. Detect platform headers (e.g. "### Amazon", "Amazon:", "Amazon", etc.)
    const platformClean = trimmed.replace(/[\*#_\-:\s]/g, '').trim().toLowerCase();
    // Only treat it as a platform if the ENTIRE cleaned string is the platform name (or very close),
    // not if the platform word appears inside a longer sentence (e.g. "...from Amazon:")
    const foundPlatform = platforms.find(p => {
      const pLower = p.toLowerCase();
      // Must equal the cleaned line OR be the only non-trivial word in it (length check)
      return platformClean === pLower || 
             (platformClean.includes(pLower) && platformClean.length <= pLower.length + 8);
    });
    if (foundPlatform) {
      currentPlatform = foundPlatform;
      pendingProductName = null;
      continue;
    }
    
    // Only strip list numbers (e.g., "1. ") or bullet markers (e.g., "- ") to preserve numbers in product names (e.g., "4K TV")
    let cleanedLine = trimmed.replace(/^(?:\d+\.\s*|[-*\+\u2022]\s*)/, '').trim();
    // Strip markdown links [Text](URL) to just Text to prevent URL digits from being parsed as prices
    cleanedLine = cleanedLine.replace(/\[([^\]]+)\]\([^\)]+\)/g, '$1');
    
    // Robust pattern to catch the price separator and currency/digits
    // Option A: Explicitly preceded by "Price:" (currency is optional) — handles both "Price: ₹X" and "Estimated Price: ₹X"
    // Option B: Preceded by a hyphen " - " with a mandatory currency symbol (or "Unknown")
    const priceSeparatorRegex = /(?:[A-Za-z]+\s+)?(?:Price:\s*)((?:₹|Rs\.?|INR|\$|USD|EUR|GBP|£|¥|￥|JPY|CNY|AED|د\.إ)?\s*\d[\d,.]*|Unknown)|(?:\s+-\s+)((?:₹|Rs\.?|INR|\$|USD|EUR|GBP|£|¥|￥|JPY|CNY|AED|د\.إ)\s*\d[\d,.]*|Unknown)/i;
    
    // Check if it explicitly has "Price:" OR " - " OR "Estimated Price:" indicating it contains a price
    const hasPriceContext = /price:/i.test(cleanedLine) || cleanedLine.includes(' - ') || cleanedLine.toLowerCase().includes('unknown');
    const match = cleanedLine.match(priceSeparatorRegex);
    
    if (match && hasPriceContext && currentPlatform) {
      let name = '';
      
      // For single-line format: find the FIRST " - " separator to cleanly split name from price part
      // e.g. "Samsung Galaxy S25 - Estimated Price: ￥129,000" → name = "Samsung Galaxy S25"
      const firstDashIdx = cleanedLine.indexOf(' - ');
      if (firstDashIdx > 0) {
        name = cleanedLine.substring(0, firstDashIdx).trim();
      } else if (pendingProductName) {
        // Multi-line format: "Price: ￥299" (product name was on previous line)
        name = pendingProductName;
        pendingProductName = null;
      } else {
        name = "Unknown Product";
      }
      
      name = name.replace(/[\*]+$/, '').trim(); // Remove trailing bold asterisks
      let price = (match[1] || match[2] || '').trim();
      
      // Auto-standardize raw numbers
      const lowerPrice = price.toLowerCase();
      // Safety-net: convert ISO currency codes to symbols so cards always display symbols
      if (/^jpy\s+[\d,]+/i.test(price)) {
        price = '￥' + price.replace(/^jpy\s+/i, '');
      } else if (/^cny\s+[\d,]+/i.test(price)) {
        price = '¥' + price.replace(/^cny\s+/i, '');
      } else if (/^inr\s+[\d,]+/i.test(price)) {
        price = '₹' + price.replace(/^inr\s+/i, '');
      } else if (/^usd\s+[\d,]+/i.test(price)) {
        price = '$' + price.replace(/^usd\s+/i, '');
      } else if (/^gbp\s+[\d,]+/i.test(price)) {
        price = '£' + price.replace(/^gbp\s+/i, '');
      } else if (/^eur\s+[\d,]+/i.test(price)) {
        price = '€' + price.replace(/^eur\s+/i, '');
      } else if (/^aed\s+[\d,]+/i.test(price)) {
        price = 'AED ' + price.replace(/^aed\s+/i, '');
      }
      if (price && !price.startsWith('₹') && !price.startsWith('$') && !price.startsWith('¥') && !price.startsWith('￥') && !price.startsWith('£') && !lowerPrice.includes('inr') && !lowerPrice.includes('usd') && !lowerPrice.includes('eur') && !lowerPrice.includes('gbp') && !lowerPrice.includes('jpy') && !lowerPrice.includes('cny') && !lowerPrice.includes('aed') && !lowerPrice.includes('unknown')) {
        price = '₹' + price;
      }
      
      if (name && !lowerPrice.includes('unknown') && !lowerPrice.includes('not listed') && !lowerPrice.includes('not_listed') && !lowerPrice.includes('n/a')) {
        results.push({
          platform: currentPlatform,
          name: name,
          price: price
        });
      }
    } else {
      // If it's not a platform, not a link, and not a price, it's likely a product name
      pendingProductName = cleanedLine;
    }
  }
  return results.length > 0 ? results : null;
}


function App() {
  const [threadId, setThreadId] = useState('')
  const [userInput, setUserInput] = useState('')
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(true)
  const [darkMode, setDarkMode] = useState(false)
  const [isListening, setIsListening] = useState(false)
  const [voiceError, setVoiceError] = useState('')
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

  const voiceEnabledRef = useRef(true)
  const toggleJarvisModeRef = useRef(null)
  const togglingJarvisRef = useRef(false)
  const micManuallyStoppedRef = useRef(false)
  const userInputRef = useRef('')
  const finalizedTranscriptRef = useRef('')

  // Keep refs in sync with state (avoids stale closures in event handlers)
  useEffect(() => { jarvisModeRef.current = jarvisMode }, [jarvisMode])
  useEffect(() => { jarvisStateRef.current = jarvisState }, [jarvisState])
  useEffect(() => { isLoadingRef.current = isLoading }, [isLoading])
  useEffect(() => { voiceEnabledRef.current = voiceEnabled }, [voiceEnabled])
  useEffect(() => { userInputRef.current = userInput }, [userInput])

  
  // Keep refs updated on every render
  useEffect(() => {
    sendMessageRef.current = sendMessage
    toggleJarvisModeRef.current = toggleJarvisMode
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

  // ═══ Speech Recognition — Stable Singleton Pattern ═══
  // IMPORTANT: We do NOT put this in a [threadId] useEffect.
  // Recreating recognition on every thread reset was causing the engine
  // to silently fail because the old recognizer was destroyed mid-flight.
  // Instead we create ONE recognition instance on mount and reuse it.

  const createRecognition = () => {
    const SpeechRecognition = window.webkitSpeechRecognition || window.SpeechRecognition
    if (!SpeechRecognition) return null

    const rec = new SpeechRecognition()
    // continuous=false is MORE reliable in Chrome — it fires a clean onend
    // after each utterance, and we restart it manually to keep it alive.
    rec.continuous = false
    rec.interimResults = true
    rec.lang = 'en-US'
    rec.maxAlternatives = 1

    rec.onresult = (event) => {
      let finalTranscript = ''
      let interimTranscript = ''

      for (let i = 0; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          finalTranscript += event.results[i][0].transcript
        } else {
          interimTranscript += event.results[i][0].transcript
        }
      }

      const fullTranscript = finalTranscript || interimTranscript
      if (!fullTranscript.trim()) return

      const combined = (finalizedTranscriptRef.current + ' ' + fullTranscript).trim()

      // Check for wake word "jarvis" or "activate jarvis"
      const cleanTranscript = combined.toLowerCase().trim().replace(/[.,?!]/g, '')
      if (!jarvisModeRef.current && (
        cleanTranscript === 'jarvis' ||
        cleanTranscript === 'activate jarvis' ||
        cleanTranscript.includes('activate jarvis')
      )) {
        if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current)
        silenceTimerRef.current = null
        setUserInput('')
        finalizedTranscriptRef.current = ''
        try { recognitionRef.current?.stop() } catch (e) {}
        if (toggleJarvisModeRef.current) toggleJarvisModeRef.current()
        return
      }

      // Update the visible input box with what we heard
      setUserInput(combined)

      // Auto-send on silence
      if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current)
      const isCurrentFinal = event.results[event.results.length - 1].isFinal
      const timeoutDuration = isCurrentFinal ? 1500 : 3500

      silenceTimerRef.current = setTimeout(() => {
        const textToSend = combined.trim()
        if (textToSend && sendMessageRef.current) {
          sendMessageRef.current(textToSend)
          try { recognitionRef.current?.stop() } catch (e) {}
          setIsListening(false)
          if (jarvisModeRef.current) setJarvisState('processing')
        }
        silenceTimerRef.current = null
      }, timeoutDuration)

    }

    rec.onerror = (err) => {
      console.warn('Speech recognition error:', err.error)

      // 'no-speech' is normal — browser timed out waiting for voice.
      if (err.error === 'no-speech') {
        setIsListening(false)
        return
      }

      if (err.error === 'not-allowed' || err.error === 'service-not-allowed') {
        setVoiceError('Microphone access denied. Please enable it in browser settings.')
        setTimeout(() => setVoiceError(''), 5000)
        setIsListening(false)
        if (jarvisModeRef.current) setJarvisState('idle')
        return
      }

      if (err.error === 'aborted') {
        // We called abort() intentionally — not an error
        return
      }

      setIsListening(false)
      if (jarvisModeRef.current && jarvisStateRef.current !== 'speaking' && jarvisStateRef.current !== 'processing') {
        setJarvisState('idle')
      }
    }

    rec.onend = () => {
      // Save current voice transcript session context before restarting mic
      if (userInputRef.current) {
        finalizedTranscriptRef.current = userInputRef.current
      }
      
      // Restart mic unless manually stopped or currently loading/speaking/processing
      if (!micManuallyStoppedRef.current &&
          !isLoadingRef.current &&
          jarvisStateRef.current !== 'speaking' &&
          jarvisStateRef.current !== 'processing') {
        setTimeout(() => {
          if (!micManuallyStoppedRef.current &&
              !isLoadingRef.current &&
              jarvisStateRef.current !== 'speaking' &&
              jarvisStateRef.current !== 'processing') {
            try {
              startListening(false) // Auto-restart without clearing input!
            } catch (e) {
              // Already running or failed to start
            }
          }
        }, 200)
      } else {
        setIsListening(false)
      }
    }


    return rec
  }

  // Initialize speech recognition ONCE on mount (not on threadId change)
  useEffect(() => {
    // Auto-start mic so the user can just start speaking immediately
    const autoMicTimer = setTimeout(() => {
      startListening()
    }, 800)

    return () => {
      clearTimeout(autoMicTimer)
      if (recognitionRef.current) {
        try { recognitionRef.current.abort() } catch (e) {}
      }
    }
  }, []) // ← Empty deps: run ONCE on mount, never again

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
  const ttsCacheRef = useRef({})  // TTS AudioBuffer Cache (LRU)
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
    if (!voiceEnabled) {
      if (jarvisModeRef.current) {
        setJarvisState('idle')
        setTimeout(() => { if (jarvisModeRef.current) startListening() }, 400)
      } else {
        setTimeout(() => { if (!jarvisModeRef.current && !isLoadingRef.current) startListening() }, 400)
      }
      return
    }
    stopAudio()
    stopMic()  // Kill the mic FIRST to prevent OS audio ducking

    const cleanedText = cleanTextForSpeech(text).trim()
    if (!cleanedText) {
      if (jarvisModeRef.current) {
        setJarvisState('idle')
        setTimeout(() => { if (jarvisModeRef.current) startListening() }, 400)
      } else {
        setTimeout(() => { if (!jarvisModeRef.current && !isLoadingRef.current) startListening() }, 400)
      }
      return
    }

    const BASE_URL = import.meta.env.VITE_API_URL || 'https://ecommerce-support-agent-93337753347.asia-south1.run.app'
    const isJarvis = jarvisModeRef.current
    if (isJarvis) setJarvisState('speaking')

    // Wait 300ms for the OS to fully release the mic device
    await new Promise(r => setTimeout(r, 300))

    const abortCtrl = new AbortController()
    const cacheKey = cleanedText.slice(0, 200).toLowerCase().trim()

    try {
      let audioBuffer = ttsCacheRef.current[cacheKey]

      if (audioBuffer) {
        // Cache Hit: Bump freshness to the end in the Map-like object
        delete ttsCacheRef.current[cacheKey]
        ttsCacheRef.current[cacheKey] = audioBuffer
      } else {
        // Cache Miss: Fetch & Decode
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
        audioBuffer = await ctx.decodeAudioData(arrayBuffer)

        // Store in cache
        ttsCacheRef.current[cacheKey] = audioBuffer

        // LRU Eviction: Max 20 entries to prevent memory leak
        const keys = Object.keys(ttsCacheRef.current)
        if (keys.length > 20) {
          delete ttsCacheRef.current[keys[0]] // Delete the oldest key (first in insertion order)
        }
      }

      // Create a source node → GainNode (3x amplification) → speakers
      const ctx = getAudioContext()
      if (ctx.state === 'suspended') await ctx.resume()
      const source = ctx.createBufferSource()
      source.buffer = audioBuffer
      source.connect(gainNodeRef.current)
      currentSourceRef.current = source
      currentAudioRef.current = null  // No longer in fetch phase

      await new Promise((resolve) => {
        source.onended = resolve
        source.start(0)
      })

      // Audio finished — restart mic regardless of mode
      currentSourceRef.current = null
      if (isJarvis && jarvisModeRef.current) {
        setJarvisState('idle')
        setTimeout(() => { if (jarvisModeRef.current) startListening() }, 400)
      } else if (!isJarvis) {
        // Normal mode: also restart listening after agent speaks
        setTimeout(() => { if (!jarvisModeRef.current && !isLoadingRef.current) startListening() }, 400)
      }
    } catch (e) {
      if (e.name === 'AbortError') return
      console.error('TTS playback error:', e)
      currentSourceRef.current = null
      if (isJarvis && jarvisModeRef.current) {
        setJarvisState('idle')
        setTimeout(() => { if (jarvisModeRef.current) startListening() }, 400)
      } else if (!isJarvis) {
        setTimeout(() => { if (!jarvisModeRef.current && !isLoadingRef.current) startListening() }, 400)
      }
    }
  }

  // ═══ Mic controls ═══
  const startListening = (clearInput = true) => {
    if (isLoadingRef.current) return
    micManuallyStoppedRef.current = false
    
    // Abort the old instance if it exists to release microphone before starting a new one
    if (recognitionRef.current) {
      try {
        recognitionRef.current.abort()
      } catch (e) {
        // Already stopped or aborted
      }
    }

    // With continuous=false we must create a fresh instance each time
    // because a stopped recognizer cannot be restarted (it throws InvalidStateError)
    recognitionRef.current = createRecognition()
    if (!recognitionRef.current) return
    if (clearInput) {
      setUserInput('')
      finalizedTranscriptRef.current = ''
    }
    try {
      recognitionRef.current.start()
      setIsListening(true)
      if (jarvisModeRef.current) setJarvisState('listening')
    } catch (e) {
      console.warn('startListening failed:', e)
    }

  }

  const stopListening = () => {
    micManuallyStoppedRef.current = true
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
    if (togglingJarvisRef.current) return
    togglingJarvisRef.current = true
    setTimeout(() => { togglingJarvisRef.current = false }, 1500)

    if (jarvisMode) {
      // Exit JARVIS mode
      jarvisModeRef.current = false
      stopListening()
      stopAudio()
      setJarvisState('idle')
      setJarvisMode(false)
    } else {
      // Enter JARVIS mode
      jarvisModeRef.current = true
      setJarvisMode(true)
      setDrawerOpen(false)
      setJarvisState('idle')
      
      // Speak the welcome greeting to establish standard speaking -> listening flow
      const welcomeText = "J.A.R.V.I.S online. How may I assist you?"
      setMessages(prev => [...prev, {
        role: 'agent',
        content: welcomeText,
        timestamp: now()
      }])
      if (voiceEnabled) {
        speak(welcomeText)
      } else {
        startListening()
      }
    }
  }

  const newSession = () => {
    const newId = generateId()
    setThreadId(newId)
    const welcome = jarvisMode 
      ? "J.A.R.V.I.S online. How may I assist you?"
      : "Hi! I'm your e-commerce support agent. Ask me about order status, returns, refunds, or cancellations."
    
    setMessages([{
      role: 'agent',
      content: welcome,
      timestamp: now()
    }])

    stopListening()
    stopAudio()
    setJarvisState('idle')

    if (jarvisMode) {
      if (voiceEnabled) {
        speak(welcome)
      } else {
        startListening()
      }
    }
  }

  // ═══ DEMO MODE ═══
  const triggerDemoMode = () => {
    if (jarvisMode) toggleJarvisMode()
    newSession()
    setUserInput("I am Chan, looking for a PlayStation 5 in Japan.")
  }
  // ═══ Send message (shared by both modes) ═══
  const sendMessage = async (overrideText = null) => {
    const textVal = (typeof overrideText === 'string' ? overrideText : userInput) || ''
    const text = normalizeOrderIdInText(textVal.trim())
    if (!text) return

    // Allow typing "jarvis" or "activate jarvis" to trigger Jarvis mode
    const cleanLower = text.toLowerCase().trim().replace(/[.,?!]/g, "");
    if (cleanLower === 'jarvis' || cleanLower === 'activate jarvis' || cleanLower === 'activate jarvis mode') {
      setUserInput('')
      if (!jarvisMode) {
        toggleJarvisMode()
      }
      return
    }

    if (isLoading) return

    stopMic()
    setUserInput('')
    finalizedTranscriptRef.current = ''
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
      const BASE_URL = import.meta.env.VITE_API_URL || 'https://ecommerce-support-agent-93337753347.asia-south1.run.app'
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

    // Trigger confetti on successful order placement
    if (metadata && metadata.order_id && metadata.intent === 'new_order') {
      confetti({
        particleCount: 150,
        spread: 70,
        origin: { y: 0.6 }
      });
    }
  }

  // ═══ JARVIS status label ═══
  const getJarvisStatusText = () => {
    switch (jarvisState) {
      case 'idle': return ''
      case 'listening': 
        // Suppress "Listening..." if user hasn't spoken anything yet to prevent visual irritation
        return userInput ? 'Listening...' : ''
      case 'processing': return 'Processing...'
      case 'speaking': return 'Speaking...'
      default: return ''
    }
  }

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
            <div className={cn(
              "prose prose-sm max-w-none",
              (isJarvis || darkMode) ? "prose-invert" : "prose-slate"
            )}>
              <ReactMarkdown 
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
            </div>
            {msg.streaming && <span className="cursor-blink" />}

            <ProductCardsGrid 
              content={msg.content}
              streaming={msg.streaming}
              darkMode={darkMode}
              jarvisMode={isJarvis}
              isLoading={isLoading}
              onCheckout={(text) => {
                if (sendMessageRef.current) {
                  sendMessageRef.current(text);
                }
              }}
            />
            
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
  return (
    <div className={cn(
      "min-h-screen min-h-[100dvh] flex items-center justify-center p-2 sm:p-4 md:p-8 overflow-hidden font-inter w-full transition-colors duration-500",
      jarvisMode 
        ? "bg-[#060608] text-slate-200" 
        : (darkMode ? "bg-slate-950 text-slate-200" : "bg-slate-50 text-slate-900")
    )}>

      {/* Voice Error Notification Toast */}
      <AnimatePresence>
        {voiceError && (
          <motion.div 
            initial={{ opacity: 0, y: -20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -20, scale: 0.95 }}
            className="absolute top-5 left-1/2 -translate-x-1/2 px-4 py-2.5 rounded-2xl bg-slate-900/90 backdrop-blur-md border border-rose-500/30 text-rose-300 text-xs font-semibold shadow-lg shadow-rose-950/20 z-50 flex items-center gap-2"
          >
            <div className="w-1.5 h-1.5 rounded-full bg-rose-400 animate-ping" />
            {voiceError}
          </motion.div>
        )}
      </AnimatePresence>

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
                      {getJarvisStatusText()}
                    </span>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button 
                  onClick={newSession}
                  aria-label="Start new session"
                  className="p-2 rounded-lg hover:bg-white/5 text-slate-500 hover:text-red-400 transition-all focus:outline-none focus:ring-2 focus:ring-red-500/50" 
                  title="New Session"
                >
                  <RefreshCw className="w-5 h-5" />
                </button>
                <button 
                  onClick={toggleJarvisMode}
                  aria-label="Exit JARVIS mode"
                  className="flex items-center gap-2 px-3 py-2 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 transition-all text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-red-500/50"
                >
                  <X className="w-4 h-4" />
                  <span className="hidden sm:inline">Exit</span>
                </button>
              </div>
            </header>

            {/* JARVIS Avatar Section */}
            <div className="flex-1 flex flex-col items-center justify-center py-6 sm:py-10 flex-shrink-0 relative">
              <div 
                className={cn("jarvis-avatar cursor-pointer", `jarvis-${jarvisState}`)}
                onClick={() => {
                  if (jarvisState === 'idle') {
                    startListening()
                  } else if (jarvisState === 'listening') {
                    stopListening()
                  }
                }}
                role="button"
                aria-label={jarvisState === 'listening' ? "Stop listening" : "Start listening"}
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    if (jarvisState === 'idle') startListening()
                    else if (jarvisState === 'listening') stopListening()
                  }
                }}
              >
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
                {getJarvisStatusText()}
              </motion.p>
              {jarvisState === 'listening' && userInput && (
                <motion.div 
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="mt-4 max-w-md text-center px-6 py-2.5 rounded-2xl bg-red-500/5 border border-red-500/10 text-red-300/80 text-xs sm:text-sm italic font-medium shadow-inner shadow-red-950/20"
                >
                  "{userInput}"
                </motion.div>
              )}
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
                  onClick={() => {
                    const newVal = !voiceEnabled;
                    setVoiceEnabled(newVal);
                    if (!newVal) {
                      stopAudio();
                    }
                  }}
                  aria-label={voiceEnabled ? "Disable voice responses" : "Enable voice responses"}
                  className={cn(
                    "p-2 rounded-lg transition-all group focus:outline-none focus:ring-2 focus:ring-violet-500/50",
                    darkMode ? "hover:bg-white/10 text-slate-400" : "hover:bg-slate-100 text-slate-500",
                    voiceEnabled && "text-violet-500"
                  )}
                  title={voiceEnabled ? "Disable Voice Responses" : "Enable Voice Responses"}
                >
                  {voiceEnabled ? <Volume2 className="w-5 h-5" /> : <VolumeX className="w-5 h-5" />}
                </button>
                <button 
                  onClick={() => setDarkMode(!darkMode)}
                  aria-label={darkMode ? "Switch to light mode" : "Switch to dark mode"}
                  className={cn(
                    "p-2 rounded-lg transition-all group focus:outline-none focus:ring-2 focus:ring-violet-500/50",
                    darkMode ? "hover:bg-white/10 text-slate-400" : "hover:bg-slate-100 text-slate-500"
                  )}
                  title={darkMode ? "Switch to Light Mode" : "Switch to Dark Mode"}
                >
                  {darkMode ? <Sun className="w-5 h-5 group-hover:text-amber-400" /> : <Moon className="w-5 h-5 group-hover:text-indigo-600" />}
                </button>
                {/* ★ JARVIS Mode Button */}
                <button 
                  onClick={toggleJarvisMode}
                  aria-label="Activate JARVIS mode"
                  className={cn(
                    "p-2 rounded-lg transition-all group relative focus:outline-none focus:ring-2 focus:ring-violet-500/50",
                    darkMode ? "hover:bg-white/10 text-slate-400" : "hover:bg-slate-100 text-slate-500"
                  )}
                  title="Activate JARVIS Mode"
                >
                  <Bot className="w-5 h-5 group-hover:text-red-500 transition-colors" />
                </button>
                <button 
                  onClick={newSession}
                  aria-label="Start new session"
                  className={cn(
                    "p-2 rounded-lg transition-all group focus:outline-none focus:ring-2 focus:ring-violet-500/50",
                    darkMode ? "hover:bg-white/10 text-slate-400" : "hover:bg-slate-100 text-slate-500"
                  )} 
                  title="New Session"
                >
                  <RefreshCw className="w-5 h-5 group-hover:text-indigo-400 transition-all" />
                </button>
                <button 
                  onClick={triggerDemoMode}
                  aria-label="Load Demo Scenario"
                  className={cn(
                    "p-2 rounded-lg transition-all group focus:outline-none focus:ring-2 focus:ring-emerald-500/50",
                    darkMode ? "hover:bg-white/10 text-slate-400" : "hover:bg-slate-100 text-slate-500"
                  )} 
                  title="Load Demo Scenario"
                >
                  <Play className="w-5 h-5 group-hover:text-emerald-500 transition-all" />
                </button>
                <button 
                  onClick={() => setDrawerOpen(!drawerOpen)}
                  aria-label="Toggle details sidebar"
                  className={cn(
                    "flex items-center gap-2 px-4 py-2 rounded-xl border transition-all focus:outline-none focus:ring-2 focus:ring-violet-500/50",
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
            <main role="main" className="flex-1 overflow-y-auto p-3 sm:p-4 md:p-6 space-y-4 sm:space-y-6">
              {renderMessages(false)}
              <div ref={messagesEndRef} />
            </main>

            {/* Input Area */}
            <footer className={cn(
              "p-3 sm:p-4 md:p-6 border-t transition-colors duration-500",
              darkMode ? "border-white/5 bg-white/5" : "border-slate-100 bg-slate-50/50"
            )}>
              <div className="flex gap-2 sm:gap-4 max-w-3xl mx-auto items-center">
                <div className="relative flex-1">
                  <input 
                    type="text" 
                    value={userInput}
                    onChange={(e) => setUserInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
                    onFocus={() => stopMic()}
                    onBlur={() => { if (!micManuallyStoppedRef.current) startListening() }}
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
                    aria-label={isListening ? "Stop listening to voice input" : "Start voice input"}
                    className={cn(
                      "absolute right-4 top-1/2 -translate-y-1/2 p-2 rounded-xl transition-all flex items-center justify-center min-w-[36px] min-h-[36px]",
                      isListening ? "bg-rose-500 text-white shadow-lg shadow-rose-500/25" : "text-slate-400 hover:text-violet-500"
                    )}
                  >
                    {isListening ? (
                      <div className="flex items-center gap-0.5 h-4 px-0.5 items-end justify-center">
                        <span className="voice-wave-bar" />
                        <span className="voice-wave-bar" />
                        <span className="voice-wave-bar" />
                      </div>
                    ) : (
                      <MicOff className="w-5 h-5" />
                    )}
                  </button>
                </div>
                <button 
                  onClick={() => sendMessage()}
                  disabled={isLoading || !userInput.trim()}
                  aria-label="Send message"
                  className="bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 disabled:from-slate-300 disabled:to-slate-300 dark:disabled:from-slate-800 dark:disabled:to-slate-800 text-white px-4 sm:px-8 py-2 rounded-2xl text-sm font-bold transition-all flex items-center gap-1 sm:gap-2 shadow-lg shadow-violet-600/20 whitespace-nowrap focus:outline-none focus:ring-2 focus:ring-violet-500/50"
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
                role="complementary"
                aria-label="Session context sidebar"
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
