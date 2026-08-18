import { useEffect, useRef } from "react";
import useAuthStore from "@/store/auth";

const DEFAULT_IDLE_MINUTES = 30;
const LAST_ACTIVITY_KEY = "hmm-last-activity-at";
const ACTIVITY_WRITE_INTERVAL_MS = 1000;

function idleLimitMs() {
  const configured = Number(import.meta.env.VITE_IDLE_LOGIN_MINUTES ?? DEFAULT_IDLE_MINUTES);
  const minutes = Number.isFinite(configured) && configured > 0 ? configured : DEFAULT_IDLE_MINUTES;
  return minutes * 60 * 1000;
}

export default function IdleLoginGuard() {
  const authenticated = useAuthStore((state) => state.authenticated);
  const timerRef = useRef<number | null>(null);
  const lastWriteRef = useRef(0);

  useEffect(() => {
    if (!authenticated) {
      return;
    }

    const limit = idleLimitMs();

    const expire = () => {
      const last = Number(localStorage.getItem(LAST_ACTIVITY_KEY) || 0);
      if (!last) {
        if (!localStorage.getItem("access_token")) {
          window.location.replace("/login?reason=idle");
          return;
        }
        touch();
        return;
      }
      if (Date.now() - last < limit) {
        schedule();
        return;
      }
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      localStorage.removeItem("user");
      localStorage.removeItem(LAST_ACTIVITY_KEY);
      window.location.replace("/login?reason=idle");
    };

    const schedule = () => {
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
      const last = Number(localStorage.getItem(LAST_ACTIVITY_KEY) || Date.now());
      const remaining = Math.max(0, limit - (Date.now() - last));
      timerRef.current = window.setTimeout(expire, remaining);
    };

    const touch = () => {
      const now = Date.now();
      if (now - lastWriteRef.current < ACTIVITY_WRITE_INTERVAL_MS) return;
      lastWriteRef.current = now;
      localStorage.setItem(LAST_ACTIVITY_KEY, String(now));
      schedule();
    };

    const existing = Number(localStorage.getItem(LAST_ACTIVITY_KEY) || 0);
    if (!existing) touch();
    else if (Date.now() - existing >= limit) {
      expire();
      return;
    }

    const events: Array<keyof WindowEventMap> = ["pointerdown", "keydown", "scroll", "touchstart"];
    events.forEach((event) => window.addEventListener(event, touch, { passive: true }));
    const onVisibility = () => {
      if (document.visibilityState === "visible") expire();
    };
    const onStorage = (event: StorageEvent) => {
      if (event.key === LAST_ACTIVITY_KEY) expire();
    };
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("storage", onStorage);
    schedule();

    return () => {
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
      events.forEach((event) => window.removeEventListener(event, touch));
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("storage", onStorage);
    };
  }, [authenticated]);

  return null;
}
