import { useEffect, useRef } from "react";
import api from "@/api/interceptor";
import useAuthStore from "@/store/auth";

const DEFAULT_IDLE_MINUTES = 30;
const LAST_ACTIVITY_KEY = "hmm-last-activity-at";
const ACTIVITY_WRITE_INTERVAL_MS = 1000;
const SERVER_HEARTBEAT_INTERVAL_MS = 60_000;

function idleLimitMs() {
  const configured = Number(import.meta.env.VITE_IDLE_LOGIN_MINUTES ?? DEFAULT_IDLE_MINUTES);
  const minutes = Number.isFinite(configured) && configured > 0 ? configured : DEFAULT_IDLE_MINUTES;
  return minutes * 60 * 1000;
}

export default function IdleLoginGuard() {
  const authenticated = useAuthStore((state) => state.authenticated);
  const timerRef = useRef<number | null>(null);
  const lastWriteRef = useRef(0);
  const lastHeartbeatRef = useRef(0);

  useEffect(() => {
    if (!authenticated) {
      return;
    }

    const limit = idleLimitMs();

    const clearAndRedirect = () => {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      localStorage.removeItem("user");
      localStorage.removeItem(LAST_ACTIVITY_KEY);
      window.location.replace("/login?reason=idle");
    };

    const expire = () => {
      const last = Number(localStorage.getItem(LAST_ACTIVITY_KEY) || 0);
      if (!last) {
        if (!localStorage.getItem("access_token")) {
          clearAndRedirect();
          return;
        }
        touch();
        return;
      }
      if (Date.now() - last < limit) {
        schedule();
        return;
      }
      void api.post("/auth/logout").catch(() => undefined).finally(clearAndRedirect);
    };

    const schedule = () => {
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
      const last = Number(localStorage.getItem(LAST_ACTIVITY_KEY) || Date.now());
      const remaining = Math.max(0, limit - (Date.now() - last));
      timerRef.current = window.setTimeout(expire, remaining);
    };

    const heartbeat = (now: number) => {
      if (now - lastHeartbeatRef.current < SERVER_HEARTBEAT_INTERVAL_MS) return;
      lastHeartbeatRef.current = now;
      void api.post("/auth/activity").catch(() => undefined);
    };

    const touch = () => {
      const now = Date.now();
      heartbeat(now);
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
    } else {
      heartbeat(Date.now());
    }

    const events: Array<keyof WindowEventMap> = ["pointerdown", "keydown", "scroll", "touchstart"];
    events.forEach((event) => window.addEventListener(event, touch, { passive: true }));
    const onVisibility = () => {
      if (document.visibilityState === "visible") expire();
    };
    const onStorage = (event: StorageEvent) => {
      if (event.key === LAST_ACTIVITY_KEY) {
        heartbeat(Date.now());
        expire();
      }
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
