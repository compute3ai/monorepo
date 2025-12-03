"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useTurnkey } from "@turnkey/react-wallet-kit";
import ContactModal from "./ContactModal";
import { WalletAuth } from "./WalletAuth";
import { useAuth } from "../providers/AuthProvider";
import { cookieUtils } from "../utils/cookies";
import { NAV_URLS } from "../utils/navigation";

export default function Header() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [isContactModalOpen, setIsContactModalOpen] = useState(false);
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false);
  const { logout } = useTurnkey();
  const { isAuthenticated } = useAuth();

  const openContactModal = () => {
    setIsContactModalOpen(true);
    setMobileMenuOpen(false);
  };

  const openLoginModal = () => {
    setIsLoginModalOpen(true);
    setMobileMenuOpen(false);
  };

  const handleLogoutClick = async () => {
    // Clear auth cookie
    cookieUtils.remove('auth_token')

    // Call Turnkey logout
    if (logout) {
      await logout()
    }

    setMobileMenuOpen(false);

    // Reload page to reset state
    window.location.href = '/';
  };

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 10);
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled ? "glassmorphism shadow-md" : ""
      }`}
    >
      <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8">
        <nav className="flex items-center justify-between h-20">
          {/* Logo */}
          <Link href={NAV_URLS.home} className="flex items-center space-x-2">
            <img
              src="/favicon.svg"
              alt="Compute3.AI Logo"
              className="h-8 w-auto"
            />
            <span className="text-2xl font-bold text-gray-900">
              Compute3.<span className="text-[var(--color-primary)]">AI</span>
            </span>
          </Link>

          {/* Desktop Nav Links */}
          <div className="hidden md:!flex items-center space-x-8">
            <a href={NAV_URLS.chat} className="text-gray-600 hover:text-gray-900 nav-link-underline">
              Chat
            </a>
            <a href={NAV_URLS.console} className="text-gray-600 hover:text-gray-900 nav-link-underline">
              Console
            </a>
            <a href={NAV_URLS.gpus} className="text-gray-600 hover:text-gray-900 nav-link-underline">
              GPUs
            </a>
            <a href={NAV_URLS.models} className="text-gray-600 hover:text-gray-900 nav-link-underline">
              Models
            </a>
            <a href={NAV_URLS.launch} className="text-gray-600 hover:text-gray-900 nav-link-underline">
              Launch
            </a>
            <a href={NAV_URLS.docs} target="_blank" rel="noopener noreferrer" className="text-gray-600 hover:text-gray-900 nav-link-underline">
              Docs
            </a>
            <button onClick={openContactModal} className="text-gray-600 hover:text-gray-900 nav-link-underline">
              Contact
            </button>
          </div>

          {/* Desktop CTAs - Only show on medium screens and up */}
          <div className="hidden md:!flex items-center space-x-4">
            {isAuthenticated ? (
              <button onClick={handleLogoutClick} className="btn-secondary font-semibold py-2 px-4 rounded-lg">
                Logout
              </button>
            ) : (
              <button onClick={openLoginModal} className="btn-primary text-white font-semibold py-2 px-4 rounded-lg">
                Login
              </button>
            )}
          </div>

          {/* Mobile Menu Button - Only show on small screens */}
          <div className="block md:!hidden">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="text-gray-800 hover:text-[var(--color-primary)] focus:outline-none"
              aria-label="Toggle mobile menu"
            >
              <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 6h16M4 12h16m-7 6h7"
                />
              </svg>
            </button>
          </div>
        </nav>
      </div>

      {/* Mobile Menu - Only show on small screens when hamburger is clicked */}
      <div
        className={`bg-white shadow-lg md:!hidden ${
          mobileMenuOpen ? "block" : "hidden"
        }`}
      >
        <div className="px-2 pt-2 pb-3 space-y-1 sm:px-3">
          <a
            href={NAV_URLS.chat}
            className="block px-3 py-2 rounded-md text-base font-medium text-gray-700 hover:text-gray-900 hover:bg-gray-50"
            onClick={() => setMobileMenuOpen(false)}
          >
            Chat
          </a>
          <a
            href={NAV_URLS.console}
            className="block px-3 py-2 rounded-md text-base font-medium text-gray-700 hover:text-gray-900 hover:bg-gray-50"
            onClick={() => setMobileMenuOpen(false)}
          >
            Console
          </a>
          <a
            href={NAV_URLS.gpus}
            className="block px-3 py-2 rounded-md text-base font-medium text-gray-700 hover:text-gray-900 hover:bg-gray-50"
            onClick={() => setMobileMenuOpen(false)}
          >
            GPUs
          </a>
          <a
            href={NAV_URLS.models}
            className="block px-3 py-2 rounded-md text-base font-medium text-gray-700 hover:text-gray-900 hover:bg-gray-50"
            onClick={() => setMobileMenuOpen(false)}
          >
            Models
          </a>
          <a
            href={NAV_URLS.launch}
            className="block px-3 py-2 rounded-md text-base font-medium text-gray-700 hover:text-gray-900 hover:bg-gray-50"
            onClick={() => setMobileMenuOpen(false)}
          >
            Launch
          </a>
          <a
            href={NAV_URLS.docs}
            target="_blank"
            rel="noopener noreferrer"
            className="block px-3 py-2 rounded-md text-base font-medium text-gray-700 hover:text-gray-900 hover:bg-gray-50"
            onClick={() => setMobileMenuOpen(false)}
          >
            Docs
          </a>
          <button
            onClick={openContactModal}
            className="block w-full text-left px-3 py-2 rounded-md text-base font-medium text-gray-700 hover:text-gray-900 hover:bg-gray-50"
          >
            Contact
          </button>
          <div className="border-t border-gray-200 mt-4 pt-4">
            {isAuthenticated ? (
              <button
                onClick={handleLogoutClick}
                className="block w-full text-center btn-secondary font-semibold py-2 px-4 rounded-lg"
              >
                Logout
              </button>
            ) : (
              <button
                onClick={openLoginModal}
                className="block w-full text-center btn-primary text-white font-semibold py-2 px-4 rounded-lg"
              >
                Login
              </button>
            )}
          </div>
        </div>
      </div>

      <ContactModal isOpen={isContactModalOpen} onClose={() => setIsContactModalOpen(false)} source="header-talk-to-sales" />

      {/* Login Modal */}
      {isLoginModalOpen && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl p-8 max-w-md w-full relative">
            {/* Close button */}
            <button
              onClick={() => setIsLoginModalOpen(false)}
              className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>

            {/* WalletAuth component */}
            <WalletAuth
              showTitle={true}
              title="Sign In"
              description="Choose how you want to sign in"
              onAuthSuccess={() => {
                setIsLoginModalOpen(false);
                window.location.reload();
              }}
            />
          </div>
        </div>
      )}
    </header>
  );
}