import { useNavigate } from "react-router-dom";

export default function Buy() {
  const navigate = useNavigate();

  return (
    <div className="h-screen flex items-center justify-center bg-background/50">
      <div className="max-w-md text-center px-6">
        <h1 className="text-3xl font-bold mb-6">Buy a Knowledgebase</h1>
        <p className="text-lg mb-2">
          Email <a href="mailto:alexyue@stanford.edu" className="underline font-medium">alexyue@stanford.edu</a> and
          send us <span className="font-bold">$100</span>.
        </p>
        <p className="text-lg mb-8">
          We will make any knowledgebase for you and send it back in 1-2 business days.
        </p>
        <button
          onClick={() => navigate("/")}
          className="text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          Back to home
        </button>
      </div>
    </div>
  );
}
