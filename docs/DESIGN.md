# E-Commerce Agent Frontend Design Specification

## Overview
A premium, modern, and highly interactive interface for the AI Support Agent. The design focuses on "Glassmorphism" aesthetics, subtle micro-animations, and a highly responsive layout using a utility-first CSS approach.

---

## 🛠 Tech Stack
- **Framework**: [React](https://react.dev/) (Vite-powered for speed)
- **Styling**: [Tailwind CSS](https://tailwindcss.com/) (PostCSS build step for production optimization)
- **State Management**: React Hooks (`useState`, `useEffect`, `useContext`)
- **Icons**: [Lucide React](https://lucide.dev/guide/packages/lucide-react) (SVG components)
- **Typography**: `Inter` or `Outfit` from Google Fonts

---

## 🎨 Visual Identity & Palette

### **Color System (Dark Mode Focused)**
- **Surface**: `bg-slate-950` (Deep midnight)
- **Primary**: `bg-indigo-600` / `text-indigo-400` (Electric Indigo)
- **Secondary**: `bg-fuchsia-600` (Vibrant Pink for CTAs)
- **Glass**: `bg-white/5` with `backdrop-blur-xl` and `border-white/10`
- **Success/Error**: `emerald-500` / `rose-500`

### **Typography**
- **Headings**: Semibold, tight tracking (`tracking-tight`)
- **Body**: Regular/Medium, wide leading (`leading-relaxed`)

---

## 🏗 Layout Architecture

### **1. The Main Chat Interface (Center Stage)**
- **Input Area**: A floating "Command Bar" at the bottom with a subtle glow effect (`shadow-indigo-500/20`).
- **Messages**: 
    - **User**: Clean, right-aligned, slate bubbles.
    - **AI**: Glassmorphic, left-aligned with a gradient border or side-accent color.
    - **Markdown Support**: Rendered via `react-markdown`.

### **2. The Interactive Drawer (Sliding Sidebar)**
- **Trigger**: A "Session Details" or "Cart" button in the header.
- **State**: Controlled via a global React state or Context.
- **Content**:
    - **Live Session Data**: Current Order IDs, Tracking numbers discovered by the AI.
    - **Customer Profile**: Display name and email once registered.
    - **Cart/Refund Preview**: Visual cards showing items being processed.

### **3. Animations (Framer Motion)**
- **Sidebar Slide**: Smooth entrance using `AnimatePresence`.
- **Message Entry**: Spring-based layout transitions for a "bouncy" premium feel.
- **Button Hover**: Sophisticated hover states with scale and depth.

---

## 🕹 Interactive Components (React Logic)

### **Chat Streaming State**
```tsx
const [messages, setMessages] = useState<Message[]>([]);
const [isStreaming, setIsStreaming] = useState(false);
```

### **Focus States**
- All inputs should have a `ring-2 ring-indigo-500 ring-offset-2 ring-offset-slate-950` focus state.
- Interactive cards should lift (`-translate-y-1`) and glow on hover.

---

## 📱 Responsiveness
- **Mobile**: The sidebar becomes a full-screen overlay.
- **Desktop**: The sidebar can be pinned or floating.
- **Safe Areas**: Proper padding for mobile "notches" and bottom navigation bars.

---

## 🚀 Future Goals
- **Dark/Light Mode Toggle**: System-preference based.
- **Sound Effects**: Subtle "pops" for message delivery (can be toggled).
- **Confetti**: Triggered on successful order placement (`canvas-confetti`).
