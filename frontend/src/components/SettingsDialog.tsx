import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getAdminToken, setAdminToken, clearAdminToken } from "@/lib/auth";

export default function SettingsDialog() {
  const [open, setOpen] = useState(false);
  const [token, setToken] = useState("");
  const hasToken = !!getAdminToken();

  function handleSave() {
    if (token.trim()) {
      setAdminToken(token.trim());
      setToken("");
      setOpen(false);
    }
  }

  function handleClear() {
    clearAdminToken();
    setToken("");
    setOpen(false);
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button
          className="p-2 text-muted-foreground hover:text-foreground transition-colors"
          aria-label="Settings"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="square"
            strokeLinejoin="miter"
          >
            <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
        </button>
      </DialogTrigger>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Admin Credentials</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-4 pt-2">
          {hasToken ? (
            <>
              <p className="text-sm text-muted-foreground">
                Admin token is set.
              </p>
              <div className="flex gap-2">
                <Button variant="destructive" onClick={handleClear} className="flex-1">
                  Clear Token
                </Button>
                <Button variant="secondary" onClick={() => setOpen(false)} className="flex-1">
                  Close
                </Button>
              </div>
            </>
          ) : (
            <>
              <Input
                type="password"
                placeholder="Enter admin credentials"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSave()}
              />
              <Button onClick={handleSave} disabled={!token.trim()}>
                Save
              </Button>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
