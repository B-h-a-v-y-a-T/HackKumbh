import React, { useState, useEffect } from 'react';
import { Users, AlertTriangle, Info, Zap } from 'lucide-react';
import type { GroupInteraction } from '../../types';
import { fetchGroups, fetchTrackTimeline } from '../../services/api';

export const GroupGraphViewer: React.FC = () => {
  const [selectedGroup, setSelectedGroup] = useState<GroupInteraction | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedTrackId, setSelectedTrackId] = useState<string>('T17');
  const [trackTimeline, setTrackTimeline] = useState<any>(null);
  const [loadingTimeline, setLoadingTimeline] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        const data = await fetchGroups();
        if (data.length > 0) {
          setSelectedGroup(data[0]);
        }
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  useEffect(() => {
    if (!selectedTrackId) return;
    async function loadTimeline() {
      try {
        setLoadingTimeline(true);
        const data = await fetchTrackTimeline(selectedTrackId);
        setTrackTimeline(data);
      } catch (err) {
        console.error(err);
        setTrackTimeline(null);
      } finally {
        setLoadingTimeline(false);
      }
    }
    loadTimeline();
  }, [selectedTrackId]);

  if (loading) {
    return (
      <div className="glass-card p-8 text-center text-[#5E6962] text-sm font-medium">
        Loading group intelligence nodes...
      </div>
    );
  }

  return (
    <div className="glass-panel-white p-6 space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#D9DDD8] pb-3.5">
        <div>
          <h2 className="text-base font-extrabold text-[#171C18] flex items-center gap-2">
            <Users className="w-5 h-5 text-[#718277]" />
            SPATIAL & GROUP BEHAVIOURAL INTELLIGENCE
          </h2>
          <p className="text-xs text-[#3D4741]">
            Correlated temporal movement & spatial proximity cluster detection. Anonymous track nodes.
          </p>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Group Topology Visualizer */}
        <div className="lg:col-span-2 glass-section-grey p-6 relative flex flex-col items-center justify-center min-h-[360px]">
          <div className="absolute top-3.5 left-4 text-xs font-bold text-[#171C18] flex items-center gap-1.5 glass-pill px-3 py-1">
            <Zap className="w-3.5 h-3.5 text-[#FF7A2A]" />
            CORRELATED CLUSTER TOPOLOGY (CLICK NODES TO INSPECT)
          </div>

          {selectedGroup ? (
            <div className="w-full flex flex-col items-center justify-center py-6 relative">
              {/* Connected Lines SVG */}
              <svg className="absolute inset-0 w-full h-full pointer-events-none" xmlns="http://www.w3.org/2000/svg">
                <line x1="30%" y1="50%" x2="50%" y2="25%" stroke="#F6B28A" strokeWidth="2.5" strokeDasharray="4" />
                <line x1="50%" y1="25%" x2="70%" y2="50%" stroke="#F6B28A" strokeWidth="2.5" strokeDasharray="4" />
                <line x1="30%" y1="50%" x2="70%" y2="50%" stroke="#FF7A2A" strokeWidth="2.5" />
              </svg>

              {/* Node Cluster */}
              <div className="flex items-center justify-around w-full max-w-md z-10 my-8">
                {/* Node T17 */}
                <button
                  onClick={() => setSelectedTrackId('T17')}
                  className={`glass-card rounded-full w-20 h-20 flex flex-col items-center justify-center text-center shadow-xs transition-all focus:outline-none ${
                    selectedTrackId === 'T17'
                      ? 'border-[#FF7A2A] ring-2 ring-[#FF7A2A]/40 scale-105 bg-white'
                      : 'hover:border-[#718277]'
                  }`}
                >
                  <span className={`font-extrabold text-sm ${selectedTrackId === 'T17' ? 'text-[#FF7A2A]' : 'text-[#171C18]'}`}>T17</span>
                  <span className="text-[10px] text-[#3D4741] font-bold">Seat B4</span>
                </button>

                {/* Node T18 */}
                <button
                  onClick={() => setSelectedTrackId('T18')}
                  className={`glass-card rounded-full w-20 h-20 flex flex-col items-center justify-center text-center shadow-xs transition-all focus:outline-none ${
                    selectedTrackId === 'T18'
                      ? 'border-[#FF7A2A] ring-2 ring-[#FF7A2A]/40 scale-105 bg-white'
                      : 'hover:border-[#718277]'
                  }`}
                >
                  <span className={`font-extrabold text-sm ${selectedTrackId === 'T18' ? 'text-[#FF7A2A]' : 'text-[#171C18]'}`}>T18</span>
                  <span className="text-[10px] text-[#3D4741] font-bold">Seat B5</span>
                </button>

                {/* Node T19 */}
                <button
                  onClick={() => setSelectedTrackId('T19')}
                  className={`glass-card rounded-full w-20 h-20 flex flex-col items-center justify-center text-center shadow-xs transition-all focus:outline-none ${
                    selectedTrackId === 'T19'
                      ? 'border-[#718277] ring-2 ring-[#718277]/40 scale-105 bg-white'
                      : 'hover:border-[#718277]'
                  }`}
                >
                  <span className={`font-extrabold text-sm ${selectedTrackId === 'T19' ? 'text-[#718277]' : 'text-[#171C18]'}`}>T19</span>
                  <span className="text-[10px] text-[#3D4741] font-bold">Seat B6</span>
                </button>
              </div>

              <div className="glass-pill text-[#FF7A2A] text-xs px-4 py-1.5 z-10 flex items-center gap-2 font-extrabold shadow-2xs">
                <AlertTriangle className="w-3.5 h-3.5 text-[#FF7A2A]" />
                <span>Synchronized Gaze & Torso Turn Correlation (Time Window: 10:42:18 – 10:42:27)</span>
              </div>
            </div>
          ) : (
            <div className="text-[#5E6962] text-xs italic font-medium">Select a group cluster to inspect nodes.</div>
          )}
        </div>

        {/* Right 1 Col: Cluster Dossier Card (Orange-Tinted Glass Card) */}
        <div className="glass-card-orange p-5 space-y-4 shadow-2xs">
          <h3 className="text-sm font-extrabold text-[#171C18] flex items-center justify-between border-b border-[#FF7A2A]/30 pb-2">
            <span>CLUSTER DOSSIER</span>
            <span className="bg-[#FF7A2A] text-white text-xs px-2.5 py-0.5 rounded-full font-bold">
              Group {selectedGroup?.group_id || 'G3'}
            </span>
          </h3>

          {selectedGroup && (
            <div className="space-y-3 text-xs">
              <div className="glass-card p-3 flex justify-between items-center">
                <span className="text-[#3D4741]">Group Risk Score:</span>
                <span className="text-[#FF7A2A] font-extrabold text-base">{selectedGroup.group_risk} / 100</span>
              </div>

              <div className="glass-card p-3 space-y-1">
                <span className="text-[#171C18] block font-bold">Member Track Nodes:</span>
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {selectedGroup.member_tracks.map((member) => (
                    <button
                      key={member}
                      onClick={() => setSelectedTrackId(member)}
                      className={`px-3 py-1 rounded-lg font-bold transition-all text-xs ${
                        selectedTrackId === member
                          ? 'bg-[#171C18] text-white'
                          : 'glass-control text-[#3D4741]'
                      }`}
                    >
                      {member}
                    </button>
                  ))}
                </div>
              </div>

              {/* Selected Node Details */}
              <div className="glass-card p-3 space-y-2">
                <div className="flex items-center justify-between border-b border-[#D9DDD8] pb-1.5">
                  <span className="font-bold text-[#171C18]">NODE: <span className="text-[#718277] font-extrabold">{selectedTrackId}</span></span>
                  <span className="glass-pill px-2 py-0.5 font-bold text-[#171C18]">
                    Seat {trackTimeline?.seat_id || 'B4'}
                  </span>
                </div>
                
                {loadingTimeline ? (
                  <div className="text-[#5E6962] text-[11px] italic">Loading node timeline...</div>
                ) : trackTimeline ? (
                  <div className="space-y-2">
                    <div className="flex justify-between items-center text-[11px] text-[#3D4741] glass-pill p-1.5">
                      <span>Risk: <strong className="text-[#FF7A2A]">{trackTimeline.current_risk}</strong></span>
                      <span>Peak Risk: <strong className="text-[#FF7A2A]">{trackTimeline.peak_risk}</strong></span>
                    </div>
                    {trackTimeline.timeline && trackTimeline.timeline.length > 0 ? (
                      <div className="space-y-1.5 max-h-[160px] overflow-y-auto pr-1">
                        {trackTimeline.timeline.map((evt: any, i: number) => (
                          <div key={i} className="glass-card p-2 text-[11px] space-y-0.5">
                            <div className="flex justify-between font-bold">
                              <span className="text-[#171C18]">{evt.event_type}</span>
                              <span className="text-[#5E6962] text-[10px]">{evt.timestamp}</span>
                            </div>
                            <p className="text-[10px] text-[#3D4741] font-medium">
                              {typeof evt.details === 'string' ? evt.details : (evt.details?.details || evt.details?.reason || JSON.stringify(evt.details))}
                            </p>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-[#5E6962] italic text-[11px]">No events logged for this node.</div>
                    )}
                  </div>
                ) : (
                  <div className="text-[#5E6962] italic text-[11px]">Failed to load timeline.</div>
                )}
              </div>

              <div className="glass-card p-3 space-y-1">
                <span className="text-[#171C18] block font-bold">Detected Pattern:</span>
                <p className="text-[#3D4741] leading-relaxed font-medium">{selectedGroup.pattern_description}</p>
              </div>

              <div className="glass-card-sage p-3 text-[#171C18] space-y-1">
                <div className="font-bold flex items-center gap-1">
                  <Info className="w-3.5 h-3.5 text-[#718277]" /> Language Guardrail Notice
                </div>
                <p className="text-[11px] leading-normal text-[#3D4741] font-medium">
                  The system never claims students are cheating together. It flags possible coordinated behavioural patterns requiring human invigilator review.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
