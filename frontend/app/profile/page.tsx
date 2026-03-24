"use client";

import Script from "next/script";
import { useEffect, useRef, useState } from "react";
import AppLayout from "../../components/AppLayout";
import {
  register,
  login,
  loginWithGoogle,
  logout,
  getMe,
  getProfile,
  updateProfile,
  enrichProfile
} from "../../lib/api";

export default function ProfilePage() {
  const googleClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID?.trim() ?? "";
  const [user, setUser] = useState<{ id: number; email: string } | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [programName, setProgramName] = useState("");
  const [institution, setInstitution] = useState("");
  const [context, setContext] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [googleScriptReady, setGoogleScriptReady] = useState(false);
  const googleButtonRef = useRef<HTMLDivElement | null>(null);

  const loadProfile = async () => {
    try {
      const profile = await getProfile();
      setFullName(profile.full_name ?? "");
      setProgramName(profile.program_name ?? "");
      setInstitution(profile.institution ?? "");
      setContext(profile.context_summary ?? null);
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Failed to load profile");
    }
  };

  useEffect(() => {
    const init = async () => {
      const me = await getMe();
      if (me) {
        setUser(me);
        await loadProfile();
      } else {
        setUser(null);
      }
    };
    init();
  }, []);

  useEffect(() => {
    if (!googleClientId || !googleScriptReady || user || !googleButtonRef.current || !window.google) {
      return;
    }

    googleButtonRef.current.innerHTML = "";
    window.google.accounts.id.initialize({
      client_id: googleClientId,
      callback: async ({ credential }) => {
        if (!credential) {
          setStatus("Google sign-in did not return a credential");
          return;
        }

        setStatus(null);
        try {
          const me = await loginWithGoogle(credential);
          setUser(me);
          await loadProfile();
        } catch (err) {
          setStatus(err instanceof Error ? err.message : "Google sign-in failed");
        }
      }
    });
    window.google.accounts.id.renderButton(googleButtonRef.current, {
      theme: "outline",
      size: "large",
      shape: "pill",
      text: "continue_with",
      width: 320
    });
  }, [googleClientId, googleScriptReady, user]);

  const handleRegister = async () => {
    setStatus(null);
    try {
      const me = await register(email, password);
      setUser(me);
      await loadProfile();
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Register failed");
    }
  };

  const handleLogin = async () => {
    setStatus(null);
    try {
      const me = await login(email, password);
      setUser(me);
      await loadProfile();
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Login failed");
    }
  };

  const handleLogout = async () => {
    setStatus(null);
    await logout();
    if (window.google) {
      window.google.accounts.id.cancel();
    }
    if (googleButtonRef.current) {
      googleButtonRef.current.innerHTML = "";
    }
    setUser(null);
    setContext(null);
    setFullName("");
    setProgramName("");
    setInstitution("");
  };

  const handleSave = async () => {
    setStatus(null);
    try {
      const profile = await updateProfile({ full_name: fullName, program_name: programName, institution });
      setFullName(profile.full_name ?? "");
      setProgramName(profile.program_name ?? "");
      setInstitution(profile.institution ?? "");
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Save failed");
    }
  };

  const handleEnrich = async () => {
    setStatus(null);
    try {
      const profile = await enrichProfile();
      setContext(profile.context_summary ?? null);
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Enrich failed");
    }
  };

  return (
    <AppLayout>
      <main className="page-shell">
        <div className="page-card">
          <div className="page-header">
            <h1>Student Profile</h1>
            {user && (
              <button className="ghost-btn" type="button" onClick={handleLogout}>
                Log out
              </button>
            )}
          </div>

          {!user && (
            <div className="form-section">
              <h2>Sign in</h2>
              <p className="signin-helper">
                Use your LectureLens account, or continue with the Google account tied to your school email.
              </p>
              <div className="form-row">
                <label>Email</label>
                <input
                  className="input"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@school.edu"
                />
              </div>
              <div className="form-row">
                <label>Password</label>
                <input
                  className="input"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                />
              </div>
              <div className="form-actions">
                <button className="primary-btn" type="button" onClick={handleLogin}>
                  Log in
                </button>
                <button className="secondary-btn" type="button" onClick={handleRegister}>
                  Create account
                </button>
              </div>
              {googleClientId && (
                <>
                  <div className="signin-divider" aria-hidden="true">
                    <span>or continue with Google</span>
                  </div>
                  <div className="google-signin-wrap">
                    <div ref={googleButtonRef} />
                  </div>
                </>
              )}
            </div>
          )}

          {user && (
            <div className="form-section">
              <h2>Profile details</h2>
              <div className="form-row">
                <label>Full name</label>
                <input
                  className="input"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Your name"
                />
              </div>
              <div className="form-row">
                <label>Program name</label>
                <input
                  className="input"
                  value={programName}
                  onChange={(e) => setProgramName(e.target.value)}
                  placeholder="Computer Science / Psychology"
                />
              </div>
              <div className="form-row">
                <label>Institution</label>
                <input
                  className="input"
                  value={institution}
                  onChange={(e) => setInstitution(e.target.value)}
                  placeholder="University / College"
                />
              </div>
              <div className="form-actions">
                <button className="primary-btn" type="button" onClick={handleSave}>
                  Save profile
                </button>
                <button className="secondary-btn" type="button" onClick={handleEnrich}>
                  Enrich with AI
                </button>
              </div>
            </div>
          )}

          {context && (
            <div className="context-card">
              <h3>Profile context</h3>
              <pre>{context}</pre>
            </div>
          )}

          {status && <div className="inline-error">{status}</div>}
        </div>
      </main>
      {googleClientId && (
        <Script
          src="https://accounts.google.com/gsi/client"
          strategy="afterInteractive"
          onLoad={() => setGoogleScriptReady(true)}
          onError={() => setStatus("Failed to load Google sign-in")}
        />
      )}
    </AppLayout>
  );
}
