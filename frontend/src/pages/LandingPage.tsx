import React, { useEffect } from 'react';
import { ArrowRight, LayoutDashboard } from 'lucide-react';

interface LandingPageProps {
  onLaunchConsole?: () => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({ onLaunchConsole }) => {
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (
        (event.data?.type === 'LAUNCH_DASHBOARD' || event.data === 'LAUNCH_DASHBOARD') &&
        onLaunchConsole
      ) {
        onLaunchConsole();
      }
    };
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [onLaunchConsole]);

  return (
    <div className="relative w-full h-screen overflow-hidden bg-[#07060B] flex flex-col">
      {/* Embedded High-Fidelity Landing Page View */}
      <iframe
        src="/landing.html"
        title="CopyCop Landing Page"
        className="w-full h-full flex-1 border-none"
      />
    </div>
  );
};
