import React from 'react';
import { Network, Users, ShieldAlert, CheckCircle2 } from 'lucide-react';
import type { GroupSummaryItem } from '../../types/report';

interface GroupIntelligenceCardProps {
  groups: GroupSummaryItem[];
  onSelectGroup?: (groupId: string) => void;
}

export const GroupIntelligenceCard: React.FC<GroupIntelligenceCardProps> = ({
  groups,
  onSelectGroup,
}) => {
  if (!groups || groups.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-[#D5D8D3] shadow-xs p-5 space-y-3">
        <div className="flex items-center gap-2 border-b border-[#E5E7E2] pb-3">
          <Network className="w-4 h-4 text-[#F59E0B]" />
          <h3 className="text-sm font-black text-[#171C18]">Group & Spatial Coordination Intelligence</h3>
        </div>
        <div className="py-8 text-center text-xs text-[#5E6962] bg-[#F8F9F7] rounded-xl border border-dashed border-[#CBD0C8]">
          <Users className="w-6 h-6 text-[#10B981] mx-auto mb-1.5" />
          <span className="font-bold text-[#171C18] block">No Multi-Person Coordination Clusters</span>
          <span className="text-[11px] text-[#5E6962]">All candidates exhibited isolated, independent seating behavior.</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-[#D5D8D3] shadow-xs p-5 space-y-5">
      <div className="flex items-center justify-between border-b border-[#E5E7E2] pb-3">
        <div className="flex items-center gap-2">
          <Network className="w-4 h-4 text-[#F59E0B]" />
          <h3 className="text-sm font-black text-[#171C18]">Group & Spatial Coordination Intelligence</h3>
        </div>
        <span className="text-[11px] font-bold text-[#5E6962]">
          {groups.length} Spatial Cluster{groups.length !== 1 ? 's' : ''} Flagged
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Group Summary Table */}
        <div className="lg:col-span-2 overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-[#E5E7E2] text-[10px] uppercase font-black tracking-wider text-[#5E6962]">
                <th className="pb-2.5">Group ID</th>
                <th className="pb-2.5">Participating Tracks</th>
                <th className="pb-2.5">Events</th>
                <th className="pb-2.5">Group Risk</th>
                <th className="pb-2.5">Interaction Pattern</th>
                <th className="pb-2.5">Review</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#F2F4F0]">
              {groups.map((grp) => (
                <tr
                  key={grp.group_id}
                  onClick={() => onSelectGroup && onSelectGroup(grp.group_id)}
                  className="hover:bg-[#F8F9F7] cursor-pointer transition-colors"
                >
                  <td className="py-3 font-black text-[#171C18]">
                    <span className="px-2 py-1 bg-[#FFFBEB] text-[#D97706] border border-[#FDE68A] rounded-lg">
                      {grp.group_id}
                    </span>
                  </td>
                  <td className="py-3 font-extrabold text-[#171C18]">
                    {grp.tracks_formatted}
                  </td>
                  <td className="py-3 font-bold text-[#5E6962]">
                    {grp.events_count}
                  </td>
                  <td className="py-3 font-black">
                    <span className={`px-2 py-0.5 rounded-full text-[11px] ${
                      grp.peak_risk >= 80 ? 'bg-[#FEE2E2] text-[#DC2626]' : 'bg-[#FEF3C7] text-[#D97706]'
                    }`}>
                      {grp.peak_risk}/100
                    </span>
                  </td>
                  <td className="py-3 text-[11px] text-[#3D4741] max-w-xs truncate" title={grp.main_pattern}>
                    {grp.main_pattern}
                  </td>
                  <td className="py-3">
                    <span className="inline-flex items-center gap-1 text-[10px] font-bold text-[#10B981] bg-[#F0FDF4] px-2 py-0.5 rounded-md border border-[#BBF7D0]">
                      <CheckCircle2 className="w-3 h-3" />
                      {grp.review_status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Right Col: Simple Network Visualization */}
        <div className="bg-[#F8F9F7] border border-[#D5D8D3] rounded-xl p-4 flex flex-col justify-between items-center text-center">
          <div className="w-full">
            <span className="text-[10px] font-extrabold uppercase tracking-wider text-[#5E6962] block mb-2">
              Spatial Network Topology
            </span>
            <div className="relative w-full h-36 bg-white border border-[#CBD0C8] rounded-xl flex items-center justify-center overflow-hidden">
              <svg className="w-full h-full" viewBox="0 0 200 120">
                {/* Connecting Lines */}
                <line x1="50" y1="60" x2="150" y2="40" stroke="#F59E0B" strokeWidth="2" strokeDasharray="4 2" />
                <line x1="50" y1="60" x2="100" y2="90" stroke="#F59E0B" strokeWidth="2" strokeDasharray="4 2" />
                <line x1="150" y1="40" x2="100" y2="90" stroke="#F59E0B" strokeWidth="2" strokeDasharray="4 2" />

                {/* Nodes */}
                <g>
                  <circle cx="50" cy="60" r="14" fill="#171C18" />
                  <text x="50" y="64" fill="#FFF" fontSize="9" fontWeight="bold" textAnchor="middle">T1</text>
                </g>
                <g>
                  <circle cx="150" cy="40" r="14" fill="#FF7A2A" />
                  <text x="150" y="44" fill="#FFF" fontSize="9" fontWeight="bold" textAnchor="middle">T2</text>
                </g>
                <g>
                  <circle cx="100" cy="90" r="14" fill="#3B82F6" />
                  <text x="100" y="94" fill="#FFF" fontSize="9" fontWeight="bold" textAnchor="middle">T3</text>
                </g>
              </svg>
            </div>
          </div>
          <span className="text-[10px] text-[#5E6962] mt-2 font-medium">
            Mutual gaze vectors and synchronized turn co-occurrence.
          </span>
        </div>
      </div>
    </div>
  );
};
