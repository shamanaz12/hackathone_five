import SupportForm from "@/components/SupportForm";

export default function SupportPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-100 py-12 px-4">
      <div className="max-w-2xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900">TaskFlow Support</h1>
          <p className="text-gray-600 mt-2 text-lg">Get instant help from our AI agent</p>
        </div>
        <SupportForm />
      </div>
    </div>
  );
}
