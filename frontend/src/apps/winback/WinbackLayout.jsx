import React, { useState } from 'react';
import WinbackSidebar from './WinbackSidebar';
import WinbackNavbar from './WinbackNavbar';
import WinbackMobileNav from './WinbackMobileNav';

export default function WinbackLayout({ activeTab, onSelectTab, children }) {
  const [drawerOpen, setDrawerOpen] = useState(false);

  return (
    <div className="flex h-screen h-[100dvh] bg-slate-950 text-slate-100 overflow-hidden" dir="rtl">
      {/* Standalone Desktop Sidebar */}
      <WinbackSidebar 
        activeTab={activeTab} 
        onSelectTab={onSelectTab} 
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-full overflow-hidden min-w-0">
        {/* Standalone Top Navbar */}
        <WinbackNavbar 
          onOpenDrawer={() => setDrawerOpen(true)} 
        />

        {/* Scrollable Viewport */}
        <main className="flex-1 overflow-y-auto overflow-x-hidden p-3 sm:p-5 md:p-6 pb-24 md:pb-6 bg-slate-950/70">
          <div className="max-w-7xl mx-auto w-full">
            {children}
          </div>
        </main>

        {/* Mobile Navigation Drawer & Bottom Bar */}
        <WinbackMobileNav 
          isOpen={drawerOpen} 
          onClose={() => setDrawerOpen(false)} 
          activeTab={activeTab} 
          onSelectTab={onSelectTab} 
        />
      </div>
    </div>
  );
}
