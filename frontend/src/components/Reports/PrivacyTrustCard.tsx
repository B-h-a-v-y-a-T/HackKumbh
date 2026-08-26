import React from 'react';
import { ShieldCheck, Lock, EyeOff, UserCheck, CheckCircle2 } from 'lucide-react';
import type { PrivacyStatusData } from '../../types/report';

interface PrivacyTrustCardProps {
  privacy: PrivacyStatusData;
}

export const PrivacyTrustCard: React.FC<PrivacyTrustCardProps> = ({ privacy }) => {
  const privacyPillars = [
    { label: 'Privacy Mode', value: 'ENABLED', icon: ShieldCheck, color: 'text-[#10B981]' },
    { label: 'Identity Recognition', value: 'DISABLED', icon: EyeOff, color: 'text-[#5E6962]' },
    { label: 'Face / Biometric Storage', value: 'DISABLED', icon: Lock, color: 'text-[#5E6962]' },
    { label: 'Anonymous Tracking', value: 'ENABLED (T1..T120)', icon: UserCheck, color: 'text-[#FF7A2A]' },
    { label: 'Human Review Mandatory', value: 'ENFORCED', icon: CheckCircle2, color: 'text-[#10B981]' },
  ];

  return (
    <div className="bg-white rounded-2xl border border-[#D5D8D3] shadow-xs p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-[#E5E7E2] pb-3">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-[#10B981]" />
          <h3 className="text-sm font-black text-[#171C18]">Privacy & Ethical AI Compliance Assurance</h3>
        </div>
        <span className="text-[10px] font-black bg-[#DCFCE7] text-[#16A34A] px-2.5 py-1 rounded-full border border-[#86EFAC]">
          Strict Compliance Guaranteed
        </span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {privacyPillars.map((p) => {
          const Icon = p.icon;
          return (
            <div key={p.label} className="bg-[#F8F9F7] border border-[#D5D8D3] p-3 rounded-xl space-y-1 shadow-2xs">
              <div className="flex items-center gap-1.5 text-[#5E6962]">
                <Icon className={`w-3.5 h-3.5 ${p.color}`} />
                <span className="text-[9px] uppercase font-bold truncate">{p.label}</span>
              </div>
              <span className="text-xs font-black text-[#171C18] block truncate">{p.value}</span>
            </div>
          );
        })}
      </div>

      <p className="text-xs text-[#3D4741] font-medium bg-[#F0FDF4] border border-[#BBF7D0] p-3 rounded-xl leading-relaxed">
        <strong>Privacy Assurance:</strong> {privacy.compliance_declaration}
      </p>
    </div>
  );
};
