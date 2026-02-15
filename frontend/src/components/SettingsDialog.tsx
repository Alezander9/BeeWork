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
import beeImg from "@/assets/bee.png";

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
          className="hover:opacity-70 transition-opacity"
          aria-label="Settings"
        >
          <img src={beeImg} alt="Settings" className="w-8 h-8" draggable={false} />
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
