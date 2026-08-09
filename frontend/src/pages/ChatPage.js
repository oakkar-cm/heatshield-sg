import { useEffect, useRef, useState } from "react";
import api from "../lib/api";
import { useApp } from "../context/AppContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Sparkles, Send, Loader2, Flame } from "lucide-react";

const SUGGESTIONS = [
  "What should I do right now?",
  "Is it safe to jog this afternoon?",
  "Signs of heat exhaustion?",
  "Best way to keep my elderly parent cool?",
];

export default function ChatPage() {
  const { location } = useApp();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [live, setLive] = useState(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    api.get("/chat/history?session_id=default").then((r) => setMessages(r.data.messages || [])).catch(() => {});
  }, []);

  // Refresh live NEA snapshot for the AI context banner
  useEffect(() => {
    let cancelled = false;
    const load = () => {
      api
        .get("/conditions", { params: { lat: location.lat, lng: location.lng } })
        .then((r) => {
          if (!cancelled) setLive(r.data);
        })
        .catch(() => {});
    };
    load();
    const id = setInterval(load, 60_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [location.lat, location.lng]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, streaming]);

  const send = async (text) => {
    const msg = (text ?? input).trim();
    if (!msg || streaming) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: msg }, { role: "assistant", content: "" }]);
    setStreaming(true);
    try {
      const { data } = await api.post(
        "/chat",
        { message: msg, session_id: "default", lat: location.lat, lng: location.lng },
        { timeout: 90000 }
      );
      const reply = data?.reply || data?.message || "I couldn't form a reply. Please try again.";
      setMessages((m) => {
        const copy = [...m];
        copy[copy.length - 1] = { role: "assistant", content: reply };
        return copy;
      });
    } catch (e) {
      const detail = e?.response?.data?.detail;
      const errText = typeof detail === "string" ? detail : "Sorry, I couldn't respond just now. Please try again.";
      setMessages((m) => {
        const copy = [...m];
        copy[copy.length - 1] = { role: "assistant", content: errText };
        return copy;
      });
    } finally {
      setStreaming(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto h-[calc(100vh-64px)] md:h-screen flex flex-col px-4 sm:px-6">
      <div className="py-5 flex items-center gap-3 border-b border-border">
        <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center">
          <Sparkles className="w-5 h-5 text-white" />
        </div>
        <div className="min-w-0">
          <h1 className="font-heading font-bold text-xl leading-none">HeatShield AI</h1>
          <p className="text-xs text-muted-foreground mt-1">
            Live NEA conditions + Groq · updates every message
          </p>
          {live && (
            <p className="text-xs text-primary mt-1.5 font-medium truncate" data-testid="chat-live-banner">
              {live.condition || "Weather"} · {live.air_temperature?.value != null ? Math.round(live.air_temperature.value) : "—"}°
              {live.feels_like?.value != null ? ` (feels ${Math.round(live.feels_like.value)}°)` : ""}
              {" · "}Heat stress: {live.heat_meta?.label || live.heat_level || "—"}
            </p>
          )}
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto no-scrollbar py-6 space-y-4" data-testid="chat-messages">
        {messages.length === 0 && (
          <div className="text-center py-10">
            <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto">
              <Flame className="w-8 h-8 text-primary" />
            </div>
            <h3 className="font-heading font-semibold text-lg mt-4">Ask me anything about the heat</h3>
            <p className="text-muted-foreground text-sm mt-1">Personalised, Singapore-grounded advice.</p>
            <div className="flex flex-wrap gap-2 justify-center mt-6">
              {SUGGESTIONS.map((s) => (
                <button key={s} onClick={() => send(s)} data-testid="chat-suggestion" className="text-sm px-4 py-2 rounded-full border border-border bg-white hover:border-primary hover:text-primary transition-colors">
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] px-4 py-3 rounded-2xl whitespace-pre-wrap ${
              m.role === "user" ? "bg-primary text-white rounded-br-md" : "bg-white border border-border rounded-bl-md"
            }`}>
              {m.content || (streaming && i === messages.length - 1 ? <Loader2 className="w-4 h-4 animate-spin" /> : "")}
            </div>
          </div>
        ))}
      </div>

      <div className="py-4 border-t border-border">
        <form onSubmit={(e) => { e.preventDefault(); send(); }} className="flex gap-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about heat safety…"
            className="h-12 rounded-xl"
            data-testid="chat-input"
          />
          <Button type="submit" disabled={streaming || !input.trim()} className="h-12 w-12 rounded-xl shrink-0" data-testid="chat-send-btn">
            {streaming ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
          </Button>
        </form>
      </div>
    </div>
  );
}
