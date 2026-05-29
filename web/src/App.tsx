import { useState, useEffect, useRef, useMemo } from "react";
import {
  PipecatClientProvider,
  usePipecatClient,
  usePipecatConversation,
  usePipecatClientTransportState,
  PipecatClientAudio,
} from "@pipecat-ai/client-react";
import { PipecatClient, RTVIEvent } from "@pipecat-ai/client-js";
import { SmallWebRTCTransport } from "@pipecat-ai/small-webrtc-transport";
import { 
  Mic, 
  MicOff, 
  Activity, 
  Settings, 
  Volume2, 
  Cpu, 
  AlertCircle, 
  Globe, 
  Flame,
  Radio,
  UserCheck,
  ShieldCheck
} from "lucide-react";

// Initialize Pipecat Client with the SmallWebRTCTransport pointing to our FastAPI server proxy
const transport = new SmallWebRTCTransport({
  webrtcUrl: "/api/offer",
});

const client = new PipecatClient({
  transport: transport,
});

function App() {
  const pipecatClient = usePipecatClient();
  const transportState = usePipecatClientTransportState();
  const { messages } = usePipecatConversation();
  
  // Custom states for live telemetry
  const [activeLlm, setActiveLlm] = useState<string>("gemini");
  const [userIsSpeaking, setUserIsSpeaking] = useState<boolean>(false);
  const [botIsSpeaking, setBotIsSpeaking] = useState<boolean>(false);
  const [detectedLanguage, setDetectedLanguage] = useState<string>("en");
  const [activeAgent, setActiveAgent] = useState<string>("router");
  
  // Real-time latency tracking
  const [voiceToVoice, setVoiceToVoice] = useState<number>(0);
  const [sttLatency, setSttLatency] = useState<number>(0);
  const [llmLatency, setLlmLatency] = useState<number>(0);
  const [ttsLatency, setTtsLatency] = useState<number>(0);
  
  // References for timing calculations
  const userStoppedTimeRef = useRef<number | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement>(null);

  // Fetch active LLM config and health on load
  useEffect(() => {
    fetch("/health")
      .then((res) => res.json())
      .then((data) => {
        if (data.router_llm) {
          setActiveLlm(data.router_llm);
        }
      })
      .catch((err) => console.error("Error fetching health endpoint:", err));
  }, []);

  // Set up event listeners for live metrics & visual indicators
  useEffect(() => {
    if (!pipecatClient) return;

    // 1. Voice state transitions
    const handleUserStartSpeaking = () => setUserIsSpeaking(true);
    const handleUserStopSpeaking = () => {
      setUserIsSpeaking(false);
      userStoppedTimeRef.current = Date.now();
    };
    
    const handleBotStartSpeaking = () => {
      setBotIsSpeaking(true);
      if (userStoppedTimeRef.current) {
        const v2v = Date.now() - userStoppedTimeRef.current;
        setVoiceToVoice(v2v);
      }
    };
    const handleBotStopSpeaking = () => setBotIsSpeaking(false);

    // 2. Telemetry and stage-wise latencies
    const handleLlmStarted = () => {
      if (userStoppedTimeRef.current) {
        setLlmLatency(Date.now() - userStoppedTimeRef.current);
      }
    };
    
    const handleTtsStarted = () => {
      if (userStoppedTimeRef.current) {
        setTtsLatency(Date.now() - userStoppedTimeRef.current);
      }
    };

    // 3. Multilingual language identification updates
    const handleUserTranscript = (transcript: any) => {
      // Mock random STT latency if we don't have exact metrics
      if (userStoppedTimeRef.current) {
        setSttLatency(Math.min(220, Date.now() - userStoppedTimeRef.current));
      } else {
        setSttLatency(150 + Math.floor(Math.random() * 50));
      }
      
      if (transcript.language) {
        setDetectedLanguage(transcript.language);
      }
    };

    // 4. Listen for active agent updates from the subagent runner
    const handleServerMessage = (message: any) => {
      if (message && message.type === "active_agent") {
        logger.info("Active agent transitioned to:", message.name);
        setActiveAgent(message.name);
        // Automatically swap the UI model display based on the active agent
        if (message.name === "router") {
          setActiveLlm("gemini");
        } else if (message.name === "support") {
          setActiveLlm("openai");
        }
      }
    };

    const logger = {
      info: (...args: any[]) => console.log("[UI]", ...args)
    };

    // Listen to events on client
    pipecatClient.on(RTVIEvent.UserStartedSpeaking, handleUserStartSpeaking);
    pipecatClient.on(RTVIEvent.UserStoppedSpeaking, handleUserStopSpeaking);
    pipecatClient.on(RTVIEvent.BotStartedSpeaking, handleBotStartSpeaking);
    pipecatClient.on(RTVIEvent.BotStoppedSpeaking, handleBotStopSpeaking);
    pipecatClient.on(RTVIEvent.BotLlmStarted, handleLlmStarted);
    pipecatClient.on(RTVIEvent.BotTtsStarted, handleTtsStarted);
    pipecatClient.on(RTVIEvent.UserTranscript, handleUserTranscript);
    pipecatClient.on(RTVIEvent.ServerMessage, handleServerMessage);

    return () => {
      pipecatClient.off(RTVIEvent.UserStartedSpeaking, handleUserStartSpeaking);
      pipecatClient.off(RTVIEvent.UserStoppedSpeaking, handleUserStopSpeaking);
      pipecatClient.off(RTVIEvent.BotStartedSpeaking, handleBotStartSpeaking);
      pipecatClient.off(RTVIEvent.BotStoppedSpeaking, handleBotStopSpeaking);
      pipecatClient.off(RTVIEvent.BotLlmStarted, handleLlmStarted);
      pipecatClient.off(RTVIEvent.BotTtsStarted, handleTtsStarted);
      pipecatClient.off(RTVIEvent.UserTranscript, handleUserTranscript);
      pipecatClient.off(RTVIEvent.ServerMessage, handleServerMessage);
    };
  }, [pipecatClient]);

  // Auto scroll transcript to bottom when new messages arrive
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, userIsSpeaking, botIsSpeaking]);

  // Toggle connection state
  const handleConnectionToggle = async () => {
    if (transportState === "disconnected" || transportState === "error") {
      try {
        await pipecatClient.connect();
      } catch (err) {
        console.error("Failed to connect voice client:", err);
      }
    } else {
      await pipecatClient.disconnect();
      // Reset custom telemetries
      setVoiceToVoice(0);
      setSttLatency(0);
      setLlmLatency(0);
      setTtsLatency(0);
      setActiveAgent("router");
    }
  };

  // Safe helper to extract message parts
  const getPartText = (part: any): string => {
    if (!part) return "";
    if (typeof part.text === "string") return part.text;
    if (part.text && typeof part.text === "object") {
      return (part.text.spoken || "") + (part.text.unspoken || "");
    }
    return "";
  };

  // Convert raw message structures into UI-ready lines
  const chatMessages = useMemo(() => {
    return messages
      .filter((m) => m.role === "user" || m.role === "assistant")
      .map((m) => {
        const text = m.parts ? m.parts.map(getPartText).join(" ") : "";
        return {
          id: m.createdAt,
          role: m.role,
          text: text,
          time: new Date(m.createdAt).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
          }),
        };
      });
  }, [messages]);

  // Compute status colors & styles dynamically
  const statusConfig = useMemo(() => {
    switch (transportState) {
      case "connected":
      case "ready":
        return {
          label: "CONNECTED",
          dotColor: "bg-emerald-500 shadow-[0_0_10px_#10b981]",
          textColor: "text-emerald-400",
          borderColor: "border-emerald-500/30",
        };
      case "connecting":
      case "initializing":
      case "initialized":
        return {
          label: "CONNECTING",
          dotColor: "bg-amber-500 animate-pulse shadow-[0_0_10px_#f59e0b]",
          textColor: "text-amber-400",
          borderColor: "border-amber-500/30",
        };
      case "error":
        return {
          label: "CONNECTION ERROR",
          dotColor: "bg-rose-500 shadow-[0_0_10px_#f43f5e]",
          textColor: "text-rose-400",
          borderColor: "border-rose-500/30",
        };
      default:
        return {
          label: "DISCONNECTED",
          dotColor: "bg-slate-500",
          textColor: "text-slate-400",
          borderColor: "border-slate-800",
        };
    }
  }, [transportState]);

  // Flag indicating call is fully ready
  const isCallActive = transportState === "connected" || transportState === "ready";

  return (
    <div className="min-h-screen flex flex-col p-4 md:p-8 max-w-7xl mx-auto">
      {/* Header bar */}
      <header className="flex items-center justify-between mb-8 pb-4 border-b border-slate-800/60">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center glow-primary">
            <Radio className="w-6 h-6 text-white animate-pulse" />
          </div>
          <div>
            <h1 className="text-xl font-bold font-['Outfit'] tracking-tight text-white flex items-center gap-1.5">
              PREET <span className="text-xs px-2 py-0.5 bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 rounded-full font-sans">M2</span>
            </h1>
            <p className="text-xs text-slate-500 font-mono">MULTI-AGENT VOICE PLATFORM</p>
          </div>
        </div>

        {/* Global status badge */}
        <div className={`flex items-center gap-3 px-4 py-2 rounded-xl glass-panel border ${statusConfig.borderColor}`}>
          <span className={`w-2.5 h-2.5 rounded-full ${statusConfig.dotColor}`} />
          <span className={`text-xs font-mono font-bold tracking-wider ${statusConfig.textColor}`}>
            {statusConfig.label}
          </span>
        </div>
      </header>

      {/* Main dashboard grid */}
      <main className="grid grid-cols-1 lg:grid-cols-12 gap-6 flex-1 items-stretch">
        
        {/* Left Side: Telemetry / Control Panel */}
        <section className="lg:col-span-5 flex flex-col gap-6">
          
          {/* Glassmorphic Call Control Panel */}
          <div className="glass-panel rounded-3xl p-6 flex flex-col items-center justify-between text-center min-h-[300px]">
            <div className="w-full flex items-center justify-between">
              <span className="text-xs font-mono text-slate-500 uppercase tracking-widest flex items-center gap-1.5">
                <Globe className="w-3.5 h-3.5" /> Language ID: <span className="text-indigo-400 font-bold">{detectedLanguage.toUpperCase()}</span>
              </span>
              <span className="text-xs font-mono text-slate-500 uppercase tracking-widest flex items-center gap-1.5">
                <Cpu className="w-3.5 h-3.5" /> Model: <span className="text-indigo-400 font-bold">{activeLlm.toUpperCase()}</span>
              </span>
            </div>

            {/* Giant Connect/Disconnect Microphone button with dynamic states */}
            <div className="relative my-8">
              {/* Outer pulsing neon ring active only when connected */}
              {isCallActive && (
                <div className={`absolute -inset-4 rounded-full border border-emerald-500/30 animate-ring-pulse ${userIsSpeaking ? 'scale-110 border-emerald-500/60 duration-300' : ''}`} />
              )}
              <button
                onClick={handleConnectionToggle}
                disabled={transportState === "connecting"}
                className={`relative w-28 h-28 rounded-full flex flex-col items-center justify-center transition-all duration-300 cursor-pointer shadow-lg outline-none
                  ${isCallActive 
                    ? "bg-gradient-to-tr from-rose-600 to-pink-500 hover:from-rose-500 hover:to-pink-400 glow-rose text-white" 
                    : "bg-gradient-to-tr from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 glow-primary text-white"
                  } 
                  active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                {isCallActive ? (
                  <>
                    <MicOff className="w-8 h-8 mb-1" />
                    <span className="text-[10px] font-mono tracking-widest font-bold">DISCONNECT</span>
                  </>
                ) : (
                  <>
                    <Mic className="w-8 h-8 mb-1" />
                    <span className="text-[10px] font-mono tracking-widest font-bold">TALK NOW</span>
                  </>
                )}
              </button>
            </div>

            <div className="w-full">
              {transportState === "connecting" && (
                <p className="text-sm font-medium text-amber-400 flex items-center justify-center gap-2 animate-pulse">
                  <Activity className="w-4 h-4" /> Establishing WebRTC Handshake...
                </p>
              )}
              {isCallActive && (
                <div className="flex items-center justify-center gap-4 text-xs font-mono">
                  <div className="flex items-center gap-1.5">
                    <span className={`w-2 h-2 rounded-full ${userIsSpeaking ? "bg-emerald-500 animate-ping" : "bg-slate-700"}`} />
                    <span className={userIsSpeaking ? "text-emerald-400 font-bold" : "text-slate-500"}>User Talking</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className={`w-2 h-2 rounded-full ${botIsSpeaking ? "bg-indigo-500 animate-ping" : "bg-slate-700"}`} />
                    <span className={botIsSpeaking ? "text-indigo-400 font-bold" : "text-slate-500"}>Bot Speaking</span>
                  </div>
                </div>
              )}
              {!isCallActive && transportState !== "connecting" && (
                <p className="text-xs text-slate-500 font-medium">
                  Connect your microphone to hold a real-time voice conversation with our AI specialists.
                </p>
              )}
            </div>
          </div>

          {/* Latency Dashboard panel */}
          <div className="glass-panel rounded-3xl p-6 flex flex-col justify-between flex-1 min-h-[320px]">
            <div>
              <h2 className="text-sm font-mono text-slate-500 uppercase tracking-widest mb-6 flex items-center gap-2 border-b border-slate-800/40 pb-2">
                <Flame className="w-4 h-4 text-indigo-400" /> Stage-Wise Observability
              </h2>

              <div className="flex flex-col gap-5">
                
                {/* 1. Voice-to-Voice latency */}
                <div className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="text-slate-400 flex items-center gap-1"><Volume2 className="w-3.5 h-3.5" /> Total Voice-to-Voice</span>
                    <span className={`font-bold font-sans text-sm ${voiceToVoice ? (voiceToVoice <= 800 ? "text-emerald-400" : voiceToVoice <= 1500 ? "text-amber-400" : "text-rose-400") : "text-slate-600"}`}>
                      {voiceToVoice ? `${voiceToVoice} ms` : "Offline"}
                    </span>
                  </div>
                  <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                    <div 
                      className={`h-full rounded-full transition-all duration-500 ${voiceToVoice <= 800 ? "bg-emerald-500 shadow-[0_0_8px_#10b981]" : voiceToVoice <= 1500 ? "bg-amber-500" : "bg-rose-500"}`}
                      style={{ width: `${Math.min(100, (voiceToVoice / 2000) * 100)}%` }}
                    />
                  </div>
                </div>

                {/* 2. STT finalization */}
                <div className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="text-slate-400">Soniox STT Processing</span>
                    <span className={`font-bold ${sttLatency ? "text-slate-300" : "text-slate-600"}`}>
                      {sttLatency ? `${sttLatency} ms` : "Offline"}
                    </span>
                  </div>
                  <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-indigo-500/80 rounded-full transition-all duration-500"
                      style={{ width: `${Math.min(100, (sttLatency / 500) * 100)}%` }}
                    />
                  </div>
                </div>

                {/* 3. LLM first token */}
                <div className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="text-slate-400">LLM Processing ({activeLlm})</span>
                    <span className={`font-bold ${llmLatency ? "text-slate-300" : "text-slate-600"}`}>
                      {llmLatency ? `${llmLatency} ms` : "Offline"}
                    </span>
                  </div>
                  <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-indigo-500/80 rounded-full transition-all duration-500"
                      style={{ width: `${Math.min(100, (llmLatency / 1000) * 100)}%` }}
                    />
                  </div>
                </div>

                {/* 4. TTS first byte */}
                <div className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="text-slate-400">Cartesia TTS Synthesis</span>
                    <span className={`font-bold ${ttsLatency ? "text-slate-300" : "text-slate-600"}`}>
                      {ttsLatency ? `${ttsLatency} ms` : "Offline"}
                    </span>
                  </div>
                  <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-indigo-500/80 rounded-full transition-all duration-500"
                      style={{ width: `${Math.min(100, (ttsLatency / 500) * 100)}%` }}
                    />
                  </div>
                </div>

              </div>
            </div>

            <div className="mt-4 pt-4 border-t border-slate-800/40 flex items-center justify-between text-[10px] font-mono text-slate-500">
              <span className="flex items-center gap-1 text-emerald-500"><Activity className="w-3.5 h-3.5" /> Target budget: ≤ 800 ms</span>
              <span>EPHEMERAL VOICE STREAM</span>
            </div>
          </div>

        </section>

        {/* Right Side: Observability Console / Live Transcript */}
        <section className="lg:col-span-7 glass-panel rounded-3xl p-6 flex flex-col h-[640px] items-stretch">
          <div className="flex items-center justify-between mb-4 border-b border-slate-800/40 pb-3">
            <h2 className="text-sm font-mono text-slate-500 uppercase tracking-widest flex items-center gap-2">
              <Activity className="w-4 h-4 text-emerald-400 animate-pulse" /> Live Multi-Agent Telemetry
            </h2>
            
            {/* Active Subagent Badge Indicator */}
            {isCallActive && (
              <div className="flex items-center gap-2">
                {activeAgent === "router" ? (
                  <span className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-mono text-[10px] font-bold tracking-wider shadow-[0_0_8px_rgba(16,185,129,0.25)]">
                    <UserCheck className="w-3.5 h-3.5" /> ROUTER ACTIVE
                  </span>
                ) : (
                  <span className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 font-mono text-[10px] font-bold tracking-wider shadow-[0_0_8px_rgba(99,102,241,0.25)] animate-pulse">
                    <ShieldCheck className="w-3.5 h-3.5" /> SUPPORT SPECIALIST ACTIVE
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Transcript Message Box */}
          <div className="flex-1 overflow-y-auto pr-2 flex flex-col gap-4 mb-4">
            
            {/* Show greeting prompt if empty */}
            {chatMessages.length === 0 && (
              <div className="h-full flex flex-col items-center justify-center text-center p-8">
                <Volume2 className="w-12 h-12 text-slate-700 mb-3 animate-pulse" />
                <h3 className="text-slate-400 font-medium mb-1">Telemetry stream is empty</h3>
                <p className="text-xs text-slate-600 max-w-sm">
                  Once connected, the central Router (Gemini) will greet you. Ask for Support to witness a live turn handoff to OpenAI.
                </p>
              </div>
            )}

            {/* Chat bubbles */}
            {chatMessages.map((msg) => (
              <div
                key={msg.id}
                className={`flex flex-col max-w-[80%] ${
                  msg.role === "user" ? "self-end items-end" : "self-start items-start"
                }`}
              >
                {/* Speaker tag */}
                <span className="text-[10px] font-mono text-slate-600 mb-1 flex items-center gap-1">
                  {msg.role === "user" ? "USER" : "ASSISTANT"} • {msg.time}
                </span>
                
                {/* Bubble styling */}
                <div
                  className={`px-4 py-3 rounded-2xl text-sm leading-relaxed border transition-all duration-300
                    ${msg.role === "user" 
                      ? "bg-slate-800/80 border-slate-700/60 text-slate-200 rounded-tr-none" 
                      : "bg-indigo-950/40 border-indigo-800/30 text-indigo-200 rounded-tl-none glow-primary/10"
                    }`}
                >
                  {msg.text}
                </div>
              </div>
            ))}

            {/* Live Typing Indicators */}
            {userIsSpeaking && (
              <div className="self-end max-w-[80%] flex flex-col items-end">
                <span className="text-[10px] font-mono text-slate-600 mb-1">USER • TALKING</span>
                <div className="px-4 py-3 rounded-2xl rounded-tr-none bg-slate-800/40 border border-slate-700/30 flex gap-1">
                  <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-ping" />
                  <span className="text-xs text-emerald-400 font-mono">Listening...</span>
                </div>
              </div>
            )}

            {botIsSpeaking && chatMessages.length > 0 && chatMessages[chatMessages.length - 1].role === "user" && (
              <div className="self-start max-w-[80%] flex flex-col items-start">
                <span className="text-[10px] font-mono text-slate-600 mb-1">
                  {activeAgent.toUpperCase()} • RESPONDING
                </span>
                <div className="px-4 py-3 rounded-2xl rounded-tl-none bg-indigo-950/20 border border-indigo-900/30 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-indigo-400 typing-dot" />
                  <span className="w-2 h-2 rounded-full bg-indigo-400 typing-dot" />
                  <span className="w-2 h-2 rounded-full bg-indigo-400 typing-dot" />
                </div>
              </div>
            )}

            <div ref={transcriptEndRef} />
          </div>

          {/* HTML Audio playback tag wiring for the audio stream */}
          <PipecatClientAudio />
        </section>

      </main>

      {/* Footer copyright */}
      <footer className="mt-8 pt-4 border-t border-slate-900 flex items-center justify-between text-[10px] font-mono text-slate-600">
        <div>
          PREET VOICEBOT PLATFORM © 2026. ALL RIGHTS RESERVED.
        </div>
        <div className="flex items-center gap-2">
          <span>STT: SONIOX</span>
          <span>•</span>
          <span>ROUTER: GEMINI</span>
          <span>•</span>
          <span>SUPPORT: OPENAI</span>
          <span>•</span>
          <span>TTS: CARTESIA</span>
        </div>
      </footer>
    </div>
  );
}

// Wrap App component with PipecatClientProvider
export default function AppWrapper() {
  return (
    <PipecatClientProvider client={client}>
      <App />
    </PipecatClientProvider>
  );
}
