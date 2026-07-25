import SupportForm from "@/components/SupportForm";

export default function SupportPage() {
  return (
    <div className="min-h-screen relative overflow-hidden flex items-center justify-center py-12 px-4">
      {/* Animated Background Elements */}
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-blue-600 opacity-20 blur-[120px] rounded-full animate-pulse"></div>
      <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-purple-600 opacity-20 blur-[120px] rounded-full animate-pulse delay-700"></div>

      <div className="max-w-4xl w-full z-10 grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
        {/* Left Side: Hero Text */}
        <div className="text-left space-y-6">
          <div className="inline-block px-3 py-1 rounded-full border border-blue-500/30 bg-blue-500/10 text-blue-400 text-xs font-bold tracking-widest uppercase mb-2">
            24/7 Digital FTE Pipeline
          </div>
          <h1 className="text-5xl lg:text-6xl font-extrabold tracking-tight">
            TaskFlow <span className="text-gradient">AI Support</span>
          </h1>
          <p className="text-gray-400 text-lg leading-relaxed max-w-md">
            The next generation of customer success. Our autonomous agent handles Tier-1 support with human-like precision and instant response.
          </p>
          
          <div className="flex gap-4 pt-4">
            <div className="glass p-4 rounded-2xl flex flex-col">
              <span className="text-2xl font-bold text-white">99.9%</span>
              <span className="text-xs text-gray-500 uppercase tracking-tighter">Uptime</span>
            </div>
            <div className="glass p-4 rounded-2xl flex flex-col">
              <span className="text-2xl font-bold text-white">&lt; 10s</span>
              <span className="text-xs text-gray-500 uppercase tracking-tighter">Response Time</span>
            </div>
            <div className="glass p-4 rounded-2xl flex flex-col">
              <span className="text-2xl font-bold text-white">Live</span>
              <span className="text-xs text-gray-500 uppercase tracking-tighter">Real Base</span>
            </div>
          </div>
        </div>

        {/* Right Side: Support Form Card */}
        <div className="glass-dark rounded-3xl p-1 shadow-2xl relative">
            {/* Inner Glow */}
            <div className="absolute inset-0 bg-gradient-to-br from-blue-500/10 to-transparent rounded-3xl pointer-events-none"></div>
            <div className="p-8 relative">
                <SupportForm />
            </div>
        </div>
      </div>

      {/* Footer Info */}
      <div className="absolute bottom-8 left-0 right-0 text-center">
          <p className="text-gray-600 text-xs tracking-widest uppercase">
              Built for CRM Digital FTE Factory — Hackathon 5
          </p>
      </div>
    </div>
  );
}
