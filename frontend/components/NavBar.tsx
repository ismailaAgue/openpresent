"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getSessionToken, logout } from "@/lib/api-client";

export default function NavBar() {
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    setLoggedIn(!!getSessionToken());
  }, []);

  return (
    <header style={{ borderBottom: "1px solid var(--ink-soft)" }}>
      <nav
        className="container"
        style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "18px 24px" }}
      >
        <Link href="/" style={{ fontFamily: "var(--font-display)", fontWeight: 600, fontSize: 20, textDecoration: "none" }}>
          OpenPresent
        </Link>
        <div style={{ display: "flex", gap: 20, alignItems: "center", fontSize: 14 }}>
          {loggedIn ? (
            <>
              <Link href="/dashboard">Your projects</Link>
              <button
                className="btn btn-secondary"
                onClick={() => {
                  logout();
                  setLoggedIn(false);
                  window.location.href = "/";
                }}
              >
                Log out
              </button>
            </>
          ) : (
            <>
              <Link href="/login">Log in</Link>
              <Link href="/register" className="btn btn-primary" style={{ textDecoration: "none" }}>
                Sign up free
              </Link>
            </>
          )}
        </div>
      </nav>
    </header>
  );
}
