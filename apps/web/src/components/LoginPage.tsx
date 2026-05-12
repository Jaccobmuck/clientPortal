"use client";

import { FormEvent } from "react";
import { useRouter } from "next/navigation";
import { FreelioLogo } from "@/components/FreelioLogo";

const previewBars = [54, 72, 46, 82, 64, 91, 76];

export function LoginPage() {
  const router = useRouter();

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    router.push("/");
  }

  return (
    <main className="freelio-page login-page">
      <section className="login-shell" aria-label="Freelio login">
        <div className="login-copy">
          <FreelioLogo />
          <div>
            <p className="eyebrow">Freelance finance workspace</p>
            <h1>Simple invoicing for freelancers who want to move faster.</h1>
            <p>
              Invoices, payments, and client work in one calm dashboard built
              for solo operators and small studios.
            </p>
          </div>

          <div className="login-preview" aria-label="Monthly payment summary">
            <div className="login-preview__header">
              <span>May revenue</span>
              <strong>$12,856.14</strong>
            </div>
            <div className="mini-bars" aria-hidden="true">
              {previewBars.map((height, index) => (
                <span
                  className="mini-bars__bar"
                  key={height + index}
                  style={{ height: `${height}%` }}
                />
              ))}
            </div>
            <div className="login-preview__stats">
              <span>
                <strong>42</strong>
                Paid invoices
              </span>
              <span>
                <strong>5</strong>
                Overdue
              </span>
            </div>
          </div>
        </div>

        <form className="login-card" onSubmit={handleSubmit}>
          <div className="login-card__header">
            <p className="eyebrow">Welcome back</p>
            <h2>Log in to Freelio</h2>
            <p>Use the mock credentials below to view the dashboard prototype.</p>
          </div>

          <label className="field">
            <span>Email</span>
            <input
              autoComplete="email"
              defaultValue="demo@freelio.app"
              name="email"
              placeholder="you@example.com"
              type="email"
            />
          </label>

          <label className="field">
            <span>Password</span>
            <input
              autoComplete="current-password"
              defaultValue="freelio-demo"
              name="password"
              placeholder="Enter your password"
              type="password"
            />
          </label>

          <div className="login-options">
            <label className="remember-me">
              <input defaultChecked name="remember" type="checkbox" />
              <span>Remember me</span>
            </label>
            <a href="#">Forgot password?</a>
          </div>

          <button className="primary-button login-submit" type="submit">
            Open dashboard
          </button>

          <p className="demo-hint">
            Demo only: no auth token is stored and no backend request is made.
          </p>
        </form>
      </section>
    </main>
  );
}
