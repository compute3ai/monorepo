"use client";

import { useState } from "react";
import Link from "next/link";
import ContactModal from "./ContactModal";

export default function Footer() {
  const [isContactModalOpen, setIsContactModalOpen] = useState(false);

  const openContactModal = () => {
    setIsContactModalOpen(true);
  };
  return (
    <footer className="bg-[var(--color-bg-light)] border-t border-gray-200">
      <div className="max-w-[1400px] mx-auto py-12 px-4 sm:px-6 lg:py-16 lg:px-8">
        <div className="xl:grid xl:grid-cols-4 xl:gap-8">
          <div className="space-y-8 xl:col-span-1">
            <Link href="/" className="flex items-center space-x-2">
              <img
                src="/favicon.svg"
                alt="Compute3.AI Logo"
                className="h-8 w-auto"
              />
              <span className="text-2xl font-bold text-gray-900">
                Compute3.<span className="text-[var(--color-primary)]">AI</span>
              </span>
            </Link>
            <p className="text-gray-500 text-base">
              Enterprise <span className="text-[var(--color-primary)]">AI</span>. Zero Vendor Lock-In.
            </p>
            <div className="flex space-x-6">
              {/* Social Icons */}
              <Link href="https://x.com/compute3ai" target="_blank" className="text-gray-400 hover:text-gray-500">
                <span className="sr-only">Twitter</span>
                <svg className="h-6 w-6" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M8.29 20.251c7.547 0 11.675-6.253 11.675-11.675 0-.178 0-.355-.012-.53A8.348 8.348 0 0022 5.92a8.19 8.19 0 01-2.357.646 4.118 4.118 0 001.804-2.27 8.224 8.224 0 01-2.605.996 4.107 4.107 0 00-6.993 3.743 11.65 11.65 0 01-8.457-4.287 4.106 4.106 0 001.27 5.477A4.072 4.072 0 012.8 9.71v.052a4.105 4.105 0 003.292 4.022 4.095 4.095 0 01-1.853.07 4.108 4.108 0 003.834 2.85A8.233 8.233 0 012 18.407a11.616 11.616 0 006.29 1.84" />
                </svg>
              </Link>
              <Link href="https://github.com/compute3ai" target="_blank" className="text-gray-400 hover:text-gray-500">
                <span className="sr-only">GitHub</span>
                <svg className="h-6 w-6" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path
                    fillRule="evenodd"
                    d="M12 2C6.477 2 2 6.477 2 12c0 4.418 2.865 8.168 6.839 9.49.5.092.682-.217.682-.482 0-.237-.009-.868-.014-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.031-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.203 2.398.1 2.651.64.7 1.03 1.595 1.03 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.001 10.001 0 0022 12c0-5.523-4.477-10-10-10z"
                    clipRule="evenodd"
                  />
                </svg>
              </Link>
            </div>
          </div>
          <div className="mt-12 grid grid-cols-1 gap-8 md:grid-cols-3 xl:mt-0 xl:col-span-3">
            <div>
              <h3 className="text-sm font-semibold text-gray-900 tracking-wider uppercase">Product</h3>
              <ul className="mt-4 space-y-4">
                <li>
                  <Link href="https://console.compute3.ai/jobs" target="_blank" className="text-base text-gray-500 hover:text-gray-900">
                    Deployments
                  </Link>
                </li>
                {/* <li>
                  <Link href="#" className="text-base text-gray-500 hover:text-gray-900">
                    Fine-Tuning
                  </Link>
                </li> */}
                <li>
                  <Link href="/gpus" className="text-base text-gray-500 hover:text-gray-900">
                    Pricing
                  </Link>
                </li>
              </ul>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-gray-900 tracking-wider uppercase">Resources</h3>
              <ul className="mt-4 space-y-4">
                <li>
                  <Link href="https://docs.compute3.ai" target="_blank" className="text-base text-gray-500 hover:text-gray-900">
                    Documentation
                  </Link>
                </li>
                <li>
                  <Link href="https://docs.compute3.ai/api-reference/introduction" target="_blank" className="text-base text-gray-500 hover:text-gray-900">
                    API Reference
                  </Link>
                </li>
                {/* <li>
                  <Link href="#" className="text-base text-gray-500 hover:text-gray-900">
                    Guides
                  </Link>
                </li>
                <li>
                  <Link href="#" className="text-base text-gray-500 hover:text-gray-900">
                    Support
                  </Link>
                </li>
                <li>
                  <Link href="#" className="text-base text-gray-500 hover:text-gray-900">
                    Status
                  </Link>
                </li> */}
              </ul>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-gray-900 tracking-wider uppercase">Company</h3>
              <ul className="mt-4 space-y-4">
                {/* <li>
                  <Link href="#" className="text-base text-gray-500 hover:text-gray-900">
                    About
                  </Link>
                </li>
                <li>
                  <Link href="#" className="text-base text-gray-500 hover:text-gray-900">
                    Blog
                  </Link>
                </li>
                <li>
                  <Link href="#" className="text-base text-gray-500 hover:text-gray-900">
                    Careers
                  </Link>
                </li> */}
                <li>
                  <button onClick={openContactModal} className="text-base text-gray-500 hover:text-gray-900">
                    Contact
                  </button>
                </li>
              </ul>
            </div>

            {/* <div>
              <h3 className="text-sm font-semibold text-gray-900 tracking-wider uppercase">Legal</h3>
              <ul className="mt-4 space-y-4">
                <li>
                  <Link href="#" className="text-base text-gray-500 hover:text-gray-900">
                    Privacy
                  </Link>
                </li>
                <li>
                  <Link href="#" className="text-base text-gray-500 hover:text-gray-900">
                    Terms
                  </Link>
                </li>
                <li>
                  <Link href="#" className="text-base text-gray-500 hover:text-gray-900">
                    Security
                  </Link>
                </li>
              </ul>
            </div> */}
          </div>
        </div>
        <div className="mt-12 border-t border-gray-200 pt-8">
          <p className="text-base text-gray-400 text-center">&copy; {new Date().getFullYear()} Compute3.AI. All rights reserved.</p>
        </div>
      </div>

      <ContactModal isOpen={isContactModalOpen} onClose={() => setIsContactModalOpen(false)} source="footer-contact" />
    </footer>
  );
}