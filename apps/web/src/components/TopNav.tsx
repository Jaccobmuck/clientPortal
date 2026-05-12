import Link from "next/link";
import { FreelioLogo } from "@/components/FreelioLogo";

const navItems = ["Home", "Invoices", "Reports", "Clients", "Settings"];

export function TopNav() {
  return (
    <header className="top-nav">
      <Link className="top-nav__brand" href="/" aria-label="Freelio dashboard">
        <FreelioLogo />
      </Link>

      <nav className="top-nav__links" aria-label="Primary navigation">
        {navItems.map((item) => (
          <Link
            className={item === "Home" ? "top-nav__link is-active" : "top-nav__link"}
            href={item === "Home" ? "/" : "#"}
            key={item}
          >
            {item}
          </Link>
        ))}
      </nav>

      <div className="top-nav__tools">
        <label className="search-box">
          <span>Search</span>
          <input aria-label="Search Freelio" placeholder="Search invoices" type="search" />
        </label>
        <Link className="top-nav__login" href="/login">
          Login
        </Link>
        <div className="profile-chip" aria-label="Signed in as Maya Chen">
          MC
        </div>
      </div>
    </header>
  );
}
